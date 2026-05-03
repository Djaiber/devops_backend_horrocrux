"""Unit tests for security._validate_claims — auth gate logic."""
import pytest
from fastapi import HTTPException
from unittest.mock import patch

from app.core.security import _validate_claims


VALID_ISSUER = "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_abc"
VALID_CLIENT = "client123"


def _claims(token_use="access", iss=VALID_ISSUER, client_id=VALID_CLIENT, aud=None):
    base = {"iss": iss, "token_use": token_use, "sub": "user-sub"}
    if token_use == "access":
        base["client_id"] = client_id
    elif token_use == "id":
        base["aud"] = aud or client_id
    return base


@pytest.fixture(autouse=True)
def patch_settings():
    with patch("app.core.security.settings") as mock:
        mock.cognito_issuer = VALID_ISSUER
        mock.COGNITO_CLIENT_ID = VALID_CLIENT
        yield mock


def test_valid_access_token_passes():
    _validate_claims(_claims(token_use="access"))  # should not raise


def test_valid_id_token_passes():
    _validate_claims(_claims(token_use="id"))  # should not raise


def test_wrong_issuer_raises_401():
    with pytest.raises(HTTPException) as exc:
        _validate_claims(_claims(iss="https://evil.com"))
    assert exc.value.status_code == 401
    assert "issuer" in exc.value.detail


def test_invalid_token_use_raises_401():
    with pytest.raises(HTTPException) as exc:
        _validate_claims(_claims(token_use="unknown"))
    assert exc.value.status_code == 401


def test_access_token_wrong_client_id_raises_401():
    claims = _claims(token_use="access")
    claims["client_id"] = "wrong-client"
    with pytest.raises(HTTPException) as exc:
        _validate_claims(claims)
    assert exc.value.status_code == 401


def test_id_token_wrong_audience_raises_401():
    claims = _claims(token_use="id", aud="wrong-audience")
    with pytest.raises(HTTPException) as exc:
        _validate_claims(claims)
    assert exc.value.status_code == 401


def test_fallback_no_token_use_valid_aud_passes():
    claims = {"iss": VALID_ISSUER, "sub": "u", "aud": VALID_CLIENT}
    _validate_claims(claims)  # should not raise


def test_fallback_no_token_use_wrong_aud_raises_401():
    claims = {"iss": VALID_ISSUER, "sub": "u", "aud": "wrong"}
    with pytest.raises(HTTPException) as exc:
        _validate_claims(claims)
    assert exc.value.status_code == 401
