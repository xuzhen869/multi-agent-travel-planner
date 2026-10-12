"""FastAPI 依赖注入"""

from uuid import UUID

from fastapi import Depends, Header, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import UnauthorizedError
from app.core.security import decode_token
from app.models.user import User


async def _resolve_user_from_token(raw_token: str, db: AsyncSession) -> User | None:
    """从 JWT 字符串解析用户（失败返回 None）"""
    if raw_token.startswith("Bearer "):
        raw_token = raw_token[7:]
    try:
        payload = decode_token(raw_token)
    except Exception:
        return None

    if payload.get("type") != "access":
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    stmt = select(User).where(User.id == UUID(user_id))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_current_user(
    authorization: str = Header(..., description="Bearer {token}"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """从 JWT 中获取当前登录用户（必填 header，用于普通 API）"""
    if not authorization.startswith("Bearer "):
        raise UnauthorizedError("认证格式错误，需要 Bearer token")

    user = await _resolve_user_from_token(authorization, db)
    if not user:
        raise UnauthorizedError("令牌无效或已过期")
    return user


async def get_current_user_optional(
    authorization: str | None = Header(default=None, description="Bearer {token}"),
    token: str | None = Query(default=None, description="query 参数中的 JWT（SSE/EventSource 场景）"),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """可选认证：优先 Authorization header，缺失时回退到 query `token`。

    用于 SSE 等无法自定义 header 的客户端（EventSource）。
    两者皆无或校验失败时返回 None，由调用方决定行为。
    """
    raw = authorization or token
    if not raw:
        return None
    return await _resolve_user_from_token(raw, db)
