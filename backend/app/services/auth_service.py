"""认证服务"""

from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.redis import rset, rget, rdel
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.models.user import User
from app.models.preference import UserPreference


class AuthService:

    @staticmethod
    async def register(db: AsyncSession, email: str, password: str, display_name: str | None = None) -> tuple[User, str, str, str]:
        stmt = select(User).where(User.email == email)
        if (await db.execute(stmt)).scalar_one_or_none():
            raise ConflictError("该邮箱已注册")
        user = User(email=email, password_hash=hash_password(password), display_name=display_name)
        db.add(user)
        await db.flush()
        db.add(UserPreference(user_id=user.id, is_first_time=True))
        access_token, access_exp = create_access_token(str(user.id))
        refresh_token, refresh_exp = create_refresh_token(str(user.id))
        ttl = int((refresh_exp - datetime.now(timezone.utc)).total_seconds())
        await rset(f"auth:refresh:{user.id}", refresh_token, ttl)
        return user, access_token, refresh_token, access_exp.isoformat()

    @staticmethod
    async def login(db: AsyncSession, email: str, password: str) -> tuple[User, str, str, str]:
        stmt = select(User).where(User.email == email)
        user = (await db.execute(stmt)).scalar_one_or_none()
        if not user or not verify_password(password, user.password_hash):
            raise UnauthorizedError("邮箱或密码错误")
        access_token, access_exp = create_access_token(str(user.id))
        refresh_token, refresh_exp = create_refresh_token(str(user.id))
        ttl = int((refresh_exp - datetime.now(timezone.utc)).total_seconds())
        await rset(f"auth:refresh:{user.id}", refresh_token, ttl)
        return user, access_token, refresh_token, access_exp.isoformat()

    @staticmethod
    async def refresh(refresh_token: str) -> tuple[str, str, str]:
        try:
            payload = decode_token(refresh_token)
        except Exception:
            raise UnauthorizedError("刷新令牌无效或已过期")
        if payload.get("type") != "refresh":
            raise UnauthorizedError("令牌类型错误")
        user_id = payload["sub"]
        jti = payload.get("jti")
        stored = await rget(f"auth:refresh:{user_id}")
        if not stored or stored != refresh_token:
            raise UnauthorizedError("刷新令牌已被撤销")
        if jti:
            await rset(f"auth:blacklist:{jti}", "1", 86400 * 7)
        new_access, access_exp = create_access_token(user_id)
        new_refresh, refresh_exp = create_refresh_token(user_id)
        ttl = int((refresh_exp - datetime.now(timezone.utc)).total_seconds())
        await rset(f"auth:refresh:{user_id}", new_refresh, ttl)
        return new_access, new_refresh, access_exp.isoformat()

    @staticmethod
    async def logout(user_id: str, refresh_token: str) -> None:
        try:
            payload = decode_token(refresh_token)
            jti = payload.get("jti")
            await rdel(f"auth:refresh:{user_id}")
            if jti:
                await rset(f"auth:blacklist:{jti}", "1", 86400 * 7)
        except Exception:
            pass
