from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.regulator.auth import TOKEN_ENV_VAR, configured_token, require_regulator_token


def test_unconfigured_token_fails_closed_with_503(monkeypatch):
    # Fail closed, same posture as ComplianceGate on an unreachable
    # robots.txt: a misconfigured server locks itself rather than quietly
    # publishing the regulator surface to everyone.
    monkeypatch.delenv(TOKEN_ENV_VAR, raising=False)
    assert configured_token() is None
    with pytest.raises(HTTPException) as exc:
        require_regulator_token(x_regulator_token="anything")
    assert exc.value.status_code == 503


def test_blank_token_env_var_is_treated_as_unconfigured(monkeypatch):
    monkeypatch.setenv(TOKEN_ENV_VAR, "   ")
    assert configured_token() is None
    with pytest.raises(HTTPException) as exc:
        require_regulator_token(x_regulator_token="x")
    assert exc.value.status_code == 503


def test_missing_header_is_401_when_a_token_is_configured(monkeypatch):
    monkeypatch.setenv(TOKEN_ENV_VAR, "s3cret")
    with pytest.raises(HTTPException) as exc:
        require_regulator_token(x_regulator_token=None)
    assert exc.value.status_code == 401


def test_wrong_token_is_401(monkeypatch):
    monkeypatch.setenv(TOKEN_ENV_VAR, "s3cret")
    with pytest.raises(HTTPException) as exc:
        require_regulator_token(x_regulator_token="not-it")
    assert exc.value.status_code == 401


def test_correct_token_passes(monkeypatch):
    monkeypatch.setenv(TOKEN_ENV_VAR, "s3cret")
    assert require_regulator_token(x_regulator_token="s3cret") is None


def test_token_is_read_fresh_so_rotation_needs_no_restart(monkeypatch):
    monkeypatch.setenv(TOKEN_ENV_VAR, "old")
    assert require_regulator_token(x_regulator_token="old") is None
    monkeypatch.setenv(TOKEN_ENV_VAR, "new")
    assert require_regulator_token(x_regulator_token="new") is None
    with pytest.raises(HTTPException):
        require_regulator_token(x_regulator_token="old")
