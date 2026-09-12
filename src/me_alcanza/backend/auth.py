from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException, Request

ALGORITHM = "HS256"


def create_token(account_id: str, secret: str, expires_minutes: int = 30) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": account_id,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_token(token: str, secret: str) -> str:
    payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
    return payload["sub"]


def get_current_account_id(request: Request) -> str:
    header = request.headers.get("authorization")
    if not header or not header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Falta el header Authorization")

    token = header.removeprefix("Bearer ")
    try:
        return decode_token(token, request.app.state.jwt_secret)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
