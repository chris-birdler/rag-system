# backend/app/api/routes/auth.py
from fastapi import APIRouter, HTTPException, Request
from backend.app.core.auth import (
    authenticate_user,
    create_token,
    check_login_rate_limit,
)
from backend.app.models.user import LoginRequest, Token

router = APIRouter()

@router.post("/login", response_model=Token)
def login(payload: LoginRequest, request: Request):
    """
    Login mit Username/Password.
    Gibt JWT Token zurück der 24h gültig ist.
    """
    client_ip = request.client.host if request.client else "unknown"
    check_login_rate_limit(client_ip)

    user = authenticate_user(payload.username, payload.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password"
        )
    token = create_token(user["username"], user["role"])
    return Token(access_token=token)