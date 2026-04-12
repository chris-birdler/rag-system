# backend/app/core/auth.py

"""
JWT Authentication.

Funktionsweise:
1. Password wird gehasht gespeichert (bcrypt)
   → niemand kann Passwörter lesen, auch nicht wir
2. Login → JWT Token generiert
3. Token bei jedem Request validiert
"""

import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.app.core.config import settings
import bcrypt

# Token Extraktion aus Header
security = HTTPBearer()


# Startup-Guard: ohne starken SECRET_KEY dürfen KEINE JWTs signiert werden,
# sonst wären Tokens trivial fälschbar. Bricht den Import hart ab.
if len(settings.secret_key) < 32:
    raise RuntimeError(
        "SECRET_KEY must be set in .env and be at least 32 characters long. "
        "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(48))'"
    )


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(
        plain.encode('utf-8'),
        hashed.encode('utf-8')
    )


# Dummy-Hash für nicht-existierende User.
# Wird verglichen, wenn der User nicht existiert – so läuft bcrypt immer
# gleich lange und ein Angreifer kann nicht per Laufzeit herausfinden,
# ob ein Username existiert.
_DUMMY_HASH = hash_password("not-a-real-password-used-only-for-timing-defense")

# In-Memory User-Store.
# Admin-Credentials kommen aus .env (ADMIN_USERNAME / ADMIN_PASSWORD).
# Weitere User können hier per Code ergänzt oder später persistent gespeichert werden.
USERS_DB: dict = {}

if settings.admin_username and settings.admin_password:
    USERS_DB[settings.admin_username] = {
        "username": settings.admin_username,
        "hashed_password": hash_password(settings.admin_password),
        "role": "admin",
    }

# --- Simple In-Memory Rate-Limit für Login ---
# Kein externer Store nötig, ein Prozess reicht uns. Hinter Traefik greift
# das per Proxy-IP – in diesem Single-Host-Setup genug, um Brute-Force zu stoppen.
LOGIN_RATE_WINDOW_SEC = 60
LOGIN_RATE_MAX_ATTEMPTS = 5
# Obergrenze für verfolgte IPs – Schutz gegen Memory-Flood
# durch Angreifer mit rotierenden Source-IPs.
LOGIN_RATE_MAX_KEYS = 10_000
_login_attempts: dict[str, list[float]] = defaultdict(list)


def check_login_rate_limit(client_ip: str) -> None:
    """429 werfen, wenn zu viele Login-Versuche aus derselben IP kamen."""
    now = time.time()
    cutoff = now - LOGIN_RATE_WINDOW_SEC

    # Wenn der Tracking-Dict zu groß wird, abgelaufene Einträge aufräumen;
    # hilft das nicht, komplett leeren (akzeptabel gegen Flood).
    if len(_login_attempts) > LOGIN_RATE_MAX_KEYS:
        for k in list(_login_attempts.keys()):
            _login_attempts[k] = [t for t in _login_attempts[k] if t > cutoff]
            if not _login_attempts[k]:
                del _login_attempts[k]
        if len(_login_attempts) > LOGIN_RATE_MAX_KEYS:
            _login_attempts.clear()

    attempts = _login_attempts[client_ip]
    attempts[:] = [t for t in attempts if t > cutoff]
    if len(attempts) >= LOGIN_RATE_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Too many login attempts. "
                f"Try again in {LOGIN_RATE_WINDOW_SEC} seconds."
            ),
        )
    attempts.append(now)


def get_user(username: str) -> Optional[dict]:
    """User aus DB holen."""
    return USERS_DB.get(username)

def authenticate_user(username: str, password: str) -> Optional[dict]:
    """
    Username + Password prüfen.
    Läuft auch bei unbekanntem User durch einen bcrypt-Vergleich, damit die
    Laufzeit konstant ist – verhindert Username-Enumeration per Timing.
    """
    user = get_user(username)
    if not user:
        verify_password(password, _DUMMY_HASH)  # constant-time defense
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    return user

def create_token(username: str, role: str) -> str:
    """
    JWT Token erstellen.
    Enthält: username, rolle, ablaufzeit.
    Signiert mit SECRET_KEY – kann nicht gefälscht werden.
    """
    expire = datetime.utcnow() + timedelta(
        hours=settings.token_expire_hours
    )
    payload = {
        "sub": username,
        "role": role,
        "exp": expire
    }
    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm="HS256"
    )

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    FastAPI Dependency – wird bei jedem geschützten Endpoint aufgerufen.
    Extrahiert und validiert den JWT Token.

    Verwendung:
        @router.get("/protected")
        def protected(user = Depends(get_current_user)):
            return {"hello": user["username"]}
    """
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"]
        )
        username = payload.get("sub")
        if not username:
            raise HTTPException(401, "Invalid token")
        return {"username": username, "role": payload.get("role")}

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )

def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """
    Dependency für Admin-only Endpoints.
    Nur Admins dürfen Paper löschen etc.
    """
    if user["role"] != "admin":
        raise HTTPException(403, "Admin access required")
    return user