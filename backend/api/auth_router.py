"""
FastAPI router for authentication endpoints.
"""
from fastapi import APIRouter, HTTPException, status

from api.auth import LoginRequest, TokenResponse, authenticate_user, create_access_token

auth_router = APIRouter(tags=["auth"])


@auth_router.post("/auth/token", response_model=TokenResponse)
async def login(body: LoginRequest):
    user = authenticate_user(body.username, body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(user["username"], user["role"])
    return TokenResponse(access_token=token)
