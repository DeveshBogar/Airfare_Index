from __future__ import annotations

import datetime as dt

import pytest

from app.auth.passwords import hash_password, verify_password
from app.auth.roles import ROLE_OPERATOR, ROLE_REGULATOR, validate_role_carrier_pairing
from app.auth.service import AccountError, authenticate, create_user, normalise_username
from app.auth.tokens import SECRET_ENV_VAR, TokenError, decode_token, issue_token
from app.db.models import Carrier


@pytest.fixture(autouse=True)
def _fixed_secret(monkeypatch):
    """Pin the signing key so tokens are stable across a test, and so the
    rotation test can change it deliberately rather than racing the
    per-process fallback."""
    monkeypatch.setenv(SECRET_ENV_VAR, "test-signing-secret")


@pytest.fixture()
def carriers(session):
    session.add(Carrier(code="SG", name="SpiceJet"))
    session.add(Carrier(code="QP", name="Akasa Air"))
    session.commit()
    return session


# --- password hashing -------------------------------------------------


def test_password_roundtrip():
    stored = hash_password("correct horse battery")
    assert verify_password("correct horse battery", stored)
    assert not verify_password("wrong horse battery", stored)


def test_same_password_hashes_differently_each_time():
    """Distinct salts, so two accounts sharing a password are not visibly
    identical in the table."""
    assert hash_password("same-password") != hash_password("same-password")


def test_short_passwords_are_rejected():
    """The floor is low (this prototype ships a shared demo password so the
    logins can be typed on a projector), but it is not absent."""
    with pytest.raises(ValueError):
        hash_password("short")
    hash_password("123456")  # exactly at the floor, must be accepted


@pytest.mark.parametrize(
    "stored",
    ["", "not-a-hash", "scrypt$bad$8$1$abc$def", "md5$1$1$1$abc$def", "scrypt$16384$8$1$abc"],
)
def test_malformed_hashes_return_false_rather_than_raising(stored):
    """A corrupted row should fail that one login, not 500 the endpoint and
    advertise that the row is corrupt."""
    assert verify_password("anything", stored) is False


# --- session tokens ---------------------------------------------------


def _issue(**overrides):
    payload = dict(user_id=7, username="dgca.officer", role=ROLE_REGULATOR, carrier_code=None)
    payload.update(overrides)
    return issue_token(**payload)


def test_token_roundtrip_carries_the_claims():
    token, expires_at = _issue()
    claims = decode_token(token)
    assert claims.user_id == 7
    assert claims.username == "dgca.officer"
    assert claims.role == ROLE_REGULATOR
    assert claims.carrier_code is None
    assert claims.expires_at == expires_at.replace(microsecond=0)


def test_token_carries_the_operator_carrier_binding():
    token, _ = _issue(role=ROLE_OPERATOR, carrier_code="SG")
    assert decode_token(token).carrier_code == "SG"


def test_a_tampered_payload_is_rejected():
    """The signature covers the payload, so editing the role inside a token
    invalidates it rather than escalating it."""
    import base64
    import json

    token, _ = _issue()
    payload_b64, signature = token.split(".")
    payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=="))
    payload["role"] = ROLE_REGULATOR
    payload["sub"] = 1
    forged = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")

    with pytest.raises(TokenError):
        decode_token(f"{forged}.{signature}")


@pytest.mark.parametrize("bad", ["", "nodot", "a.b.c", "!!!.???"])
def test_malformed_tokens_are_rejected(bad):
    with pytest.raises(TokenError):
        decode_token(bad)


def test_an_expired_token_is_rejected():
    issued = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    token, expires_at = _issue(now=issued)
    assert decode_token(token, now=issued + dt.timedelta(minutes=5)).user_id == 7
    with pytest.raises(TokenError):
        decode_token(token, now=expires_at + dt.timedelta(seconds=1))


def test_rotating_the_secret_invalidates_existing_tokens(monkeypatch):
    token, _ = _issue()
    monkeypatch.setenv(SECRET_ENV_VAR, "a-different-secret")
    with pytest.raises(TokenError):
        decode_token(token)


# --- role/carrier invariant -------------------------------------------


def test_an_operator_must_be_bound_to_a_carrier():
    with pytest.raises(ValueError):
        validate_role_carrier_pairing(ROLE_OPERATOR, None)
    validate_role_carrier_pairing(ROLE_OPERATOR, "SG")


def test_a_regulator_must_not_be_bound_to_a_carrier():
    """A stray carrier on a regulator account would be ignored by every
    query — the kind of misconfiguration that later reads as a broken
    permission filter."""
    with pytest.raises(ValueError):
        validate_role_carrier_pairing(ROLE_REGULATOR, "SG")
    validate_role_carrier_pairing(ROLE_REGULATOR, None)


def test_an_unknown_role_is_rejected():
    with pytest.raises(ValueError):
        validate_role_carrier_pairing("admin", None)


# --- account creation and sign-in -------------------------------------


def test_usernames_are_normalised_and_matched_case_insensitively(carriers):
    create_user(carriers, username="  DGCA.Officer ", password="a-good-password", role=ROLE_REGULATOR)
    assert normalise_username("  DGCA.Officer ") == "dgca.officer"
    assert authenticate(carriers, username="DGCA.OFFICER", password="a-good-password") is not None


def test_duplicate_usernames_are_refused(carriers):
    create_user(carriers, username="dupe", password="a-good-password", role=ROLE_REGULATOR)
    with pytest.raises(AccountError):
        create_user(carriers, username="DUPE", password="another-password", role=ROLE_REGULATOR)


def test_an_operator_for_an_unknown_carrier_is_refused(carriers):
    """It would pass the pairing check and then match nothing at query
    time, which reads as a broken filter rather than a bad account."""
    with pytest.raises(AccountError):
        create_user(
            carriers, username="ghost.ops", password="a-good-password",
            role=ROLE_OPERATOR, carrier_code="ZZ",
        )


def test_authenticate_rejects_a_wrong_password(carriers):
    create_user(carriers, username="someone", password="a-good-password", role=ROLE_REGULATOR)
    assert authenticate(carriers, username="someone", password="not-it") is None


def test_authenticate_rejects_an_unknown_username(carriers):
    assert authenticate(carriers, username="nobody", password="a-good-password") is None


def test_authenticate_rejects_a_deactivated_account(carriers):
    user = create_user(carriers, username="retired", password="a-good-password", role=ROLE_REGULATOR)
    user.is_active = False
    carriers.commit()
    assert authenticate(carriers, username="retired", password="a-good-password") is None


def test_authenticate_stamps_the_last_login(carriers):
    create_user(carriers, username="active", password="a-good-password", role=ROLE_REGULATOR)
    user = authenticate(carriers, username="active", password="a-good-password")
    assert user is not None and user.last_login_at is not None
