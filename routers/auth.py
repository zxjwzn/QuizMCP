"""认证路由 — 登录端点。"""

from fastapi import APIRouter, HTTPException, status

from auth import create_access_token
from config import settings
from schemas import LoginRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest) -> TokenResponse:
    if body.password != settings.quiz_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
        )
    token = create_access_token()
    return TokenResponse(access_token=token)
