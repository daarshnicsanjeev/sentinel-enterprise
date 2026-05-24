"""
JWT authentication for Project Sentinel.
Simple in-memory user store — suitable for demo/single-tenant deployment.
"""
import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "sentinel-demo-secret-key-change-in-production")
_ALGORITHM = "HS256"
_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "480"))  # 8 hours

_pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

# In-memory user store: username → {hashed_password, role}
_USERS: dict[str, dict] = {
    "admin": {
        "hashed_password": _pwd_context.hash(os.environ.get("ADMIN_PASSWORD", "sentinel123")),
        "role": "admin",
    },
    "analyst": {
        "hashed_password": _pwd_context.hash(os.environ.get("ANALYST_PASSWORD", "analyst123")),
        "role": "analyst",
    },
}

_bearer_scheme = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def _verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def authenticate_user(username: str, password: str) -> dict | None:
    user = _USERS.get(username)
    if not user:
        return None
    if not _verify_password(password, user["hashed_password"]):
        return None
    return {"username": username, "role": user["role"]}


def create_access_token(username: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": username, "role": role, "exp": expire}
    return jwt.encode(payload, _SECRET_KEY, algorithm=_ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
    except JWTError:
        return None


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"username": payload["sub"], "role": payload["role"]}


def require_role(role: str):
    """Return a callable dependency that enforces the given minimum role."""
    def _guard(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' required.",
            )
        return current_user
    return _guard


# Pre-built guards for the two roles
require_admin = require_role("admin")
