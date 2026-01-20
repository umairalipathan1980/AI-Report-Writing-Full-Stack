import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24
bearer_scheme = HTTPBearer()


def _get_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"{name} not found in environment variables.")
    return value.strip()


def verify_credentials(username: str, password: str) -> bool:
    return username.strip() == _get_env("ADMIN_USER") and password.strip() == _get_env("ADMIN_PASSWORD")


def create_access_token(username: str) -> str:
    secret = _get_env("JWT_SECRET")
    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def require_auth(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> str:
    secret = _get_env("JWT_SECRET")
    token = credentials.credentials
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        return payload.get("sub", "")
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
