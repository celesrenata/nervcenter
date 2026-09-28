"""Authentication endpoints for the NerveCenter API."""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import secrets

router = APIRouter(prefix="/auth", tags=["authentication"])

security = HTTPBearer()

# Configuration
SECRET_KEY = secrets.token_urlsafe(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7


class TokenSettings(BaseModel):
    """Token settings."""
    access_token_expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES
    refresh_token_expires_days: int = REFRESH_TOKEN_EXPIRE_DAYS


# In-memory token store (in production, use Redis)
token_store: dict = {}
user_store: dict = {"admin": {"password": "password", "roles": ["admin"]}}


def verify_credentials(username: str, password: str) -> Optional[dict]:
    """Verify user credentials."""
    user = user_store.get(username)
    if user and user["password"] == password:
        return {"username": username, "roles": user.get("roles", [])}
    return None


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create an access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire, "type": "access"})
    token = secrets.token_urlsafe(32)
    token_store[token] = to_encode
    return token


def create_refresh_token(data: dict) -> str:
    """Create a refresh token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    token = secrets.token_urlsafe(32)
    token_store[token] = to_encode
    return token


def validate_token(token: str) -> dict:
    """Validate a token."""
    token_data = token_store.get(token)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if token_data.get("exp") < datetime.utcnow():
        del token_store[token]
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token_data


@router.post("/login")
async def login(username: str, password: str):
    """Authenticate user and return tokens."""
    user = verify_credentials(username, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": username, "username": username},
        expires_delta=access_token_expires,
    )
    refresh_token = create_refresh_token(data={"sub": username})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": {"username": username, "roles": user.get("roles", [])},
    }


@router.post("/refresh")
async def refresh_token(refresh_token: str):
    """Refresh access token using refresh token."""
    payload = validate_token(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    new_access_token = create_access_token(
        data={"sub": payload["sub"], "username": payload.get("username", payload["sub"])},
        expires_delta=access_token_expires,
    )

    return {
        "access_token": new_access_token,
        "token_type": "Bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.get("/me")
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated user."""
    token = credentials.credentials
    payload = validate_token(token)
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"username": payload.get("sub"), "iat": payload.get("iat")}


@router.post("/logout")
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Logout user and invalidate token."""
    token = credentials.credentials
    if token in token_store:
        del token_store[token]
    return {"message": "Logged out successfully"}