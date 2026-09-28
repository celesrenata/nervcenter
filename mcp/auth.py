"""Authentication module for the MCP (Model Control Protocol)."""
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
import secrets


# In-memory token store (in production, use Redis)
token_store: Dict[str, Dict[str, Any]] = {}
user_store: Dict[str, Dict[str, Any]] = {"admin": {"password": "password", "roles": ["admin"]}}


def verify_credentials(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Verify user credentials."""
    user = user_store.get(username)
    if user and user["password"] == password:
        return {"username": username, "roles": user.get("roles", [])}
    return None


def create_token(data: Dict[str, Any], expires_minutes: int = 30) -> str:
    """Create an authentication token."""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(minutes=expires_minutes)
    token_store[token] = {
        "data": data,
        "expires_at": expires_at,
        "type": "access"
    }
    return token


def validate_token(token: str) -> Optional[Dict[str, Any]]:
    """Validate an authentication token."""
    token_data = token_store.get(token)
    if not token_data:
        return None
    expires_at = token_data.get("expires_at")
    if expires_at and expires_at < datetime.utcnow():
        del token_store[token]
        return None
    return token_data["data"]


def authenticate(auth: Optional[Dict[str, str]]) -> bool:
    """Authenticate a request."""
    if not auth:
        return False
    
    token = auth.get("token")
    if not token:
        return False
    
    return validate_token(token) is not None