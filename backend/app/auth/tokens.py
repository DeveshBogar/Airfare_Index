"""Signed session tokens for the role logins.

Format is ``<payload_b64url>.<signature_b64url>`` where the payload is
compact JSON and the signature is HMAC-SHA256 over the exact payload
string that was transmitted. That is deliberately JWT-shaped without
claiming to be a JWT: there is no JOSE header, so there is no ``alg``
field for an attacker to set to ``none`` - the algorithm is fixed in code
and cannot be negotiated by the token itself.

The signing key is resolved in three steps, and never falls back to a
fixed development secret at any of them:

  1. ``APIX_AUTH_SECRET`` if it is set. A deployment, or anything running
     more than one worker process, should use this.
  2. Otherwise a random key generated once and kept in ``data/.auth_secret``
     (gitignored). This is what makes ``start.bat`` work with no setup
     while still keeping people signed in across a restart.
  3. Only if that file cannot be read or written - a read-only checkout,
     say - a random per-process key, with a warning. Sessions then end when
     the process does.

This deliberately does not fail closed the way
``app.scraper.compliance.ComplianceGate`` does. Failing closed there
prevents scraping a site that has not permitted it; there is no equivalent
exposure here, because every fallback is a strong random key rather than a
guessable default.

What a valid token proves: that this server issued it for that user id,
and that it has not expired or been altered. It is not by itself an access
decision — ``app.auth.deps`` re-loads the account on every request and
reads the role from the database, so deactivating an account or changing
its role takes effect on the next request rather than at token expiry.

The gap that remains is per-token revocation: there is no way to invalidate
one issued token while leaving the account usable, because nothing
server-side records which tokens exist. The default lifetime is therefore
kept to a working day rather than a week, so a leaked token expires on its
own within a shift. A deployment needing immediate per-session revocation
needs a server-side session store, which is stated here rather than
pretended away.
"""
from __future__ import annotations

import base64
import binascii
import datetime as dt
import hmac
import json
import logging
import os
import secrets
from dataclasses import dataclass

from app.config import DATA_DIR

logger = logging.getLogger("airfare_idex.auth")

SECRET_ENV_VAR = "APIX_AUTH_SECRET"
TTL_ENV_VAR = "APIX_AUTH_TTL_SECONDS"

DEFAULT_TTL_SECONDS = 12 * 60 * 60  # one working day
MIN_TTL_SECONDS = 60
MAX_TTL_SECONDS = 7 * 24 * 60 * 60

SECRET_FILE = DATA_DIR / ".auth_secret"

_CACHED_FILE_SECRET: str | None = None
_EPHEMERAL_SECRET: str | None = None


class TokenError(Exception):
    """Raised when a token is absent, malformed, mis-signed or expired.

    Deliberately one exception type for every failure mode: the caller
    turns this into a single 401, so that a probe cannot distinguish
    "signature wrong" from "expired" from "not base64" and learn something
    about the key from which error came back.
    """


@dataclass(frozen=True)
class TokenClaims:
    user_id: int
    username: str
    role: str
    carrier_code: str | None
    issued_at: dt.datetime
    expires_at: dt.datetime


def signing_secret() -> str:
    """Resolve the signing key. See this module's docstring for the order.

    The environment variable is re-read on every call rather than captured
    at import, so rotating it does not need a restart and tests can set a
    key per case. The file-backed key is cached after the first read, since
    it cannot change underneath a running process.
    """
    global _CACHED_FILE_SECRET, _EPHEMERAL_SECRET

    configured = os.environ.get(SECRET_ENV_VAR, "").strip()
    if configured:
        return configured

    if _CACHED_FILE_SECRET is not None:
        return _CACHED_FILE_SECRET

    try:
        if SECRET_FILE.exists():
            stored = SECRET_FILE.read_text(encoding="utf-8").strip()
            if stored:
                _CACHED_FILE_SECRET = stored
                return stored

        generated = secrets.token_urlsafe(48)
        SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
        SECRET_FILE.write_text(generated, encoding="utf-8")
        logger.info(
            "generated a new session signing key at %s (gitignored) - set %s to override it",
            SECRET_FILE,
            SECRET_ENV_VAR,
        )
        _CACHED_FILE_SECRET = generated
        return generated
    except OSError as exc:
        if _EPHEMERAL_SECRET is None:
            _EPHEMERAL_SECRET = secrets.token_urlsafe(48)
            logger.warning(
                "could not read or write %s (%s) - signing session tokens with a random "
                "per-process key instead. Logins work, but everyone is signed out when this "
                "process restarts. Set %s to fix that.",
                SECRET_FILE,
                exc,
                SECRET_ENV_VAR,
            )
        return _EPHEMERAL_SECRET


def token_ttl_seconds() -> int:
    """Session lifetime, clamped to a sane band.

    An unparseable or out-of-range value falls back to the default rather
    than raising, because the failure mode of a typo'd env var should be a
    normal-length session plus a warning, not a server that cannot issue
    any login at all.
    """
    raw = os.environ.get(TTL_ENV_VAR, "").strip()
    if not raw:
        return DEFAULT_TTL_SECONDS

    try:
        value = int(raw)
    except ValueError:
        logger.warning("%s=%r is not an integer - using %ds", TTL_ENV_VAR, raw, DEFAULT_TTL_SECONDS)
        return DEFAULT_TTL_SECONDS

    if not (MIN_TTL_SECONDS <= value <= MAX_TTL_SECONDS):
        logger.warning(
            "%s=%d is outside %d-%d - using %ds",
            TTL_ENV_VAR,
            value,
            MIN_TTL_SECONDS,
            MAX_TTL_SECONDS,
            DEFAULT_TTL_SECONDS,
        )
        return DEFAULT_TTL_SECONDS

    return value


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _sign(payload_b64: str, secret: str) -> str:
    digest = hmac.digest(secret.encode("utf-8"), payload_b64.encode("ascii"), "sha256")
    return _b64encode(digest)


def issue_token(
    *,
    user_id: int,
    username: str,
    role: str,
    carrier_code: str | None,
    now: dt.datetime | None = None,
) -> tuple[str, dt.datetime]:
    """Mint a signed token. Returns (token, expires_at)."""
    issued = now or dt.datetime.now(dt.timezone.utc)
    expires = issued + dt.timedelta(seconds=token_ttl_seconds())

    payload = {
        "sub": user_id,
        "usr": username,
        "role": role,
        "car": carrier_code,
        "iat": int(issued.timestamp()),
        "exp": int(expires.timestamp()),
    }
    # sort_keys and tight separators so the same claims always produce the
    # same bytes - the signature is over the transmitted string, so this is
    # only about keeping tokens stable and compact, not correctness.
    payload_b64 = _b64encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    return f"{payload_b64}.{_sign(payload_b64, signing_secret())}", expires


def decode_token(token: str, *, now: dt.datetime | None = None) -> TokenClaims:
    """Verify a token's signature and expiry, then return its claims.

    Raises TokenError on any failure. The signature is checked *before* the
    payload is parsed, so malformed JSON inside an unsigned token is never
    interpreted.
    """
    if not token:
        raise TokenError("no token supplied")

    parts = token.split(".")
    if len(parts) != 2:
        raise TokenError("malformed token")

    payload_b64, signature = parts
    expected_signature = _sign(payload_b64, signing_secret())
    if not hmac.compare_digest(signature, expected_signature):
        raise TokenError("bad signature")

    try:
        payload = json.loads(_b64decode(payload_b64))
    except (ValueError, binascii.Error) as exc:
        raise TokenError("unreadable payload") from exc

    if not isinstance(payload, dict):
        raise TokenError("unreadable payload")

    try:
        user_id = int(payload["sub"])
        username = str(payload["usr"])
        role = str(payload["role"])
        issued_at = dt.datetime.fromtimestamp(int(payload["iat"]), dt.timezone.utc)
        expires_at = dt.datetime.fromtimestamp(int(payload["exp"]), dt.timezone.utc)
    except (KeyError, TypeError, ValueError, OSError, OverflowError) as exc:
        raise TokenError("incomplete payload") from exc

    carrier_raw = payload.get("car")
    carrier_code = str(carrier_raw) if carrier_raw else None

    moment = now or dt.datetime.now(dt.timezone.utc)
    if moment >= expires_at:
        raise TokenError("token expired")

    return TokenClaims(
        user_id=user_id,
        username=username,
        role=role,
        carrier_code=carrier_code,
        issued_at=issued_at,
        expires_at=expires_at,
    )
