"""认证相关 API 端点"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    RefreshRequest,
    LogoutRequest,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """邮箱注册"""
    user, access_token, refresh_token, expires_at = await AuthService.register(
        db, req.email, req.password, req.display_name
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """邮箱登录"""
    user, access_token, refresh_token, expires_at = await AuthService.login(
        db, req.email, req.password
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(req: RefreshRequest):
    """刷新令牌"""
    access_token, refresh_token, expires_at = await AuthService.refresh(req.refresh_token)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
    )


@router.post("/logout", status_code=204)
async def logout(req: LogoutRequest):
    """登出"""
    import json
    from app.core.security import decode_token
    try:
        payload = decode_token(req.refresh_token)
        user_id = payload.get("sub", "")
        await AuthService.logout(user_id, req.refresh_token)
    except Exception:
        pass
    return None
