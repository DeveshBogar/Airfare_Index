"""Password hashing for the three role logins.

Uses scrypt from the standard library (``hashlib.scrypt``, an OpenSSL
binding) rather than bcrypt or argon2. The default advice is "never
hand-roll auth", so the choice is worth stating plainly:

  - The KDF is not hand-rolled. scrypt is memory-hard by design, and the
    parameters below (n=2**14, r=8, p=1) are the interactive-login set
    from RFC 7914 section 11. What lives in this module is the salt,
    encode and constant-time-compare wrapper around it.
  - It adds no dependency. This project is started from start.bat against
    a committed venv; a login surface that fails at import because someone
    skipped a ``pip install bcrypt`` step is a worse outcome than the
    marginal difference between scrypt and argon2id at prototype scale.

The stored format is self-describing, so the cost parameters can be raised
later without invalidating hashes written today:

    scrypt$<n>$<r>$<p>$<salt_b64>$<derived_b64>

Limitations, stated rather than glossed: this stores passwords correctly,
but it is not an identity provider. There is no password-reset flow, no
account-lockout after repeated failures, and no second factor. A
deployment holding real regulator credentials needs all three, and should
put a real IdP in front of this module.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

ALGORITHM = "scrypt"

# RFC 7914 section 11 interactive-login parameters. n is the CPU/memory
# cost, r the block size, p the parallelisation factor.
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SALT_BYTES = 16
DERIVED_KEY_BYTES = 32

# scrypt needs roughly 128 * n * r bytes. At the parameters above that is
# ~16 MB; OpenSSL's default ceiling is 32 MB, which leaves no headroom if
# the cost is ever raised. Setting it explicitly means a future bump to
# n=2**15 fails loudly here rather than mysteriously inside OpenSSL.
SCRYPT_MAXMEM = 128 * 1024 * 1024

# 6 rather than a realistic minimum, because this prototype ships with a
# shared demo password so the three role logins can actually be typed during
# a demonstration. The hashing above is unchanged and sound; what is weak
# here is the password itself, which is a deliberate demo concession. A
# deployment must raise this and stop issuing a shared credential.
MIN_PASSWORD_LENGTH = 6


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _derive(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        dklen=DERIVED_KEY_BYTES,
        maxmem=SCRYPT_MAXMEM,
    )


def hash_password(password: str) -> str:
    """Hash a plaintext password with a fresh random salt."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")

    salt = secrets.token_bytes(SALT_BYTES)
    derived = _derive(password, salt, SCRYPT_N, SCRYPT_R, SCRYPT_P)
    return f"{ALGORITHM}${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64encode(salt)}${_b64encode(derived)}"


def verify_password(password: str, stored: str) -> bool:
    """Check a plaintext password against a stored hash.

    Returns False for malformed or unknown-algorithm hashes rather than
    raising: a corrupted row in the users table should fail that one login,
    not 500 the whole endpoint and reveal that the row is corrupt.
    """
    if not stored:
        return False

    parts = stored.split("$")
    if len(parts) != 6:
        return False

    algorithm, n_raw, r_raw, p_raw, salt_b64, expected_b64 = parts
    if algorithm != ALGORITHM:
        return False

    try:
        n, r, p = int(n_raw), int(r_raw), int(p_raw)
        salt = _b64decode(salt_b64)
        expected = _b64decode(expected_b64)
        candidate = _derive(password, salt, n, r, p)
    except (ValueError, TypeError, MemoryError):
        return False

    # compare_digest rather than ==, so a near-miss cannot be narrowed down
    # by timing how far the comparison got before it failed.
    return hmac.compare_digest(candidate, expected)
