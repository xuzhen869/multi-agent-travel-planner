"""OAuth 认证端点 — Google / GitHub

V1 实现 Google OAuth 基础流程。GitHub OAuth 可通过同样模式扩展。
"""

import httpx
from fastapi import APIRouter, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import RedirectResponse

from app.config import settings
from app.core.database import get_db, async_session_factory
from app.core.security import create_access_token, create_refresh_token, hash_password
from app.core.exceptions import BadRequestError
from app.models.user import User
from app.models.preference import UserPreference
from app.schemas.auth import TokenResponse

router = APIRouter(prefix="/api/auth/oauth", tags=["OAuth"])

# Google OAuth 端点
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

REDIRECT_URI = "http://localhost:3000/auth/callback/google"


@router.get("/google/url")
async def google_auth_url():
    """获取 Google OAuth 授权链接"""
    if not settings.GOOGLE_CLIENT_ID:
        return {"url": None, "error": "Google OAuth 未配置"}

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return {"url": f"{GOOGLE_AUTH_URL}?{query}"}


@router.post("/google/callback", response_model=TokenResponse)
async def google_callback(
    code: str = Query(..., description="授权码"),
    state: str | None = Query(default=None),
):
    """Google OAuth 回调 — 用授权码换 token，创建或登录用户"""
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise BadRequestError("Google OAuth 未配置")

    # 用授权码换 access token
    async with httpx.AsyncClient(timeout=15.0) as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": REDIRECT_URI,
            },
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()
        access_token = token_data.get("access_token")

        if not access_token:
            raise BadRequestError("无法获取 Google access token")

        # 获取用户信息
        user_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user_resp.raise_for_status()
        user_info = user_resp.json()

    google_id = user_info.get("id", "")
    email = user_info.get("email", "")
    name = user_info.get("name", "")
    picture = user_info.get("picture", "")

    if not email:
        raise BadRequestError("无法获取 Google 账号邮箱")

    # 查找或创建用户
    async with async_session_factory() as db:
        # 先按 oauth_id 查
        stmt = select(User).where(User.oauth_provider == "google", User.oauth_id == google_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            # 再按 email 查（可能是之前邮箱注册的）
            stmt2 = select(User).where(User.email == email)
            result2 = await db.execute(stmt2)
            user = result2.scalar_one_or_none()

            if user:
                # 已有邮箱注册用户 → 绑定 OAuth
                user.oauth_provider = "google"
                user.oauth_id = google_id
            else:
                # 新用户
                user = User(
                    email=email,
                    password_hash=hash_password(google_id),  # OAuth 用户用 Google ID 做密码占位
                    display_name=name,
                    oauth_provider="google",
                    oauth_id=google_id,
                )
                db.add(user)
                await db.flush()
                db.add(UserPreference(user_id=user.id, is_first_time=True))

        await db.commit()

        # 生成 JWT
        access_jwt, access_exp = create_access_token(str(user.id))
        refresh_jwt, refresh_exp = create_refresh_token(str(user.id))

        # 存 Redis refresh token
        from datetime import datetime, timezone
        from app.core.redis import rset
        ttl = int((refresh_exp - datetime.now(timezone.utc)).total_seconds())
        await rset(f"auth:refresh:{user.id}", refresh_jwt, ttl)

    return TokenResponse(
        access_token=access_jwt,
        refresh_token=refresh_jwt,
        expires_at=access_exp.isoformat(),
    )


@router.get("/github/url")
async def github_auth_url():
    """获取 GitHub OAuth 授权链接"""
    if not settings.GITHUB_CLIENT_ID:
        return {"url": None, "error": "GitHub OAuth 未配置"}

    params = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "redirect_uri": "http://localhost:3000/auth/callback/github",
        "scope": "user:email",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return {"url": f"https://github.com/login/oauth/authorize?{query}"}
