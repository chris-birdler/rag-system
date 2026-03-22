# backend/app/api/routes/auth.py
from fastapi import APIRouter, HTTPException
from backend.app.core.auth import authenticate_user, create_token
from backend.app.models.user import LoginRequest, Token

router = APIRouter()

@router.post("/login", response_model=Token)
def login(request: LoginRequest):
    """
    Login mit Username/Password.
    Gibt JWT Token zurück der 24h gültig ist.
    """
    user = authenticate_user(request.username, request.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password"
        )
    token = create_token(user["username"], user["role"])
    return Token(access_token=token)