"""Authentication utilities and JWT helpers."""

from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import settings

try:
    from jose import JWTError, jwt
except ImportError:  # pragma: no cover
    raise

_ALGORITHM = "HS256"
_bearer = HTTPBearer(auto_error=True)


def create_access_token() -> str:
    """Issue a signed JWT valid for `jwt_expire_hours` hours."""
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    payload = {"sub": "user", "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> None:
    """FastAPI dependency: validate Bearer JWT token."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[_ALGORITHM])
        if payload.get("sub") != "user":
            raise JWTError("invalid subject")
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
