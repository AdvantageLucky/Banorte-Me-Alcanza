import jwt
import pytest
from fastapi import HTTPException, Request

from me_alcanza.backend import auth

SECRET = "test-secret-that-is-long-enough-for-pyjwt-hs256"


def test_create_and_decode_token_roundtrip():
    token = auth.create_token("ana", SECRET, expires_minutes=30)
    assert auth.decode_token(token, SECRET) == "ana"


def test_decode_token_expirado_lanza_error():
    token = auth.create_token("ana", SECRET, expires_minutes=-1)
    with pytest.raises(jwt.ExpiredSignatureError):
        auth.decode_token(token, SECRET)


def test_decode_token_secreto_incorrecto_lanza_error():
    token = auth.create_token("ana", SECRET, expires_minutes=30)
    with pytest.raises(jwt.InvalidTokenError):
        auth.decode_token(token, "otro-secreto-that-is-long-enough-for-pyjwt")


def _make_request(headers: dict, jwt_secret: str = SECRET) -> Request:
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "app": type("App", (), {"state": type("State", (), {"jwt_secret": jwt_secret})()})(),
    }
    return Request(scope)


def test_get_current_account_id_ok():
    token = auth.create_token("luis", SECRET)
    request = _make_request({"authorization": f"Bearer {token}"})
    assert auth.get_current_account_id(request) == "luis"


def test_get_current_account_id_sin_header_lanza_401():
    request = _make_request({})
    with pytest.raises(HTTPException) as exc_info:
        auth.get_current_account_id(request)
    assert exc_info.value.status_code == 401


def test_get_current_account_id_token_invalido_lanza_401():
    request = _make_request({"authorization": "Bearer no-es-un-jwt"})
    with pytest.raises(HTTPException) as exc_info:
        auth.get_current_account_id(request)
    assert exc_info.value.status_code == 401
