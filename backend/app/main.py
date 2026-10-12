"""FastAPI 应用入口"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import engine, Base
from app.core.exceptions import AppException, app_exception_handler, general_exception_handler
from app.core.redis import init_redis, close_redis

# ——— API 路由 ———
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.trips import router as trips_router
from app.api.lookup import router as lookup_router
from app.api.oauth import router as oauth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时：自动建表（开发环境免去手动 migrate）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await init_redis()
    yield
    # 关闭时
    await close_redis()
    await engine.dispose()


app = FastAPI(
    title="旅行规划助手 API",
    description="Multi-Agent 旅行规划后端服务",
    version="1.0.0",
    lifespan=lifespan,
)

# ——— CORS ———
app.add_middleware(
    CORSMiddleware,
    # 开发环境：允许本机与局域网 IP 访问前端（如 http://192.168.10.9:3000）。
    # 之前仅白名单 localhost，从局域网 IP 访问时 CORS 预检被拒（400 Disallowed CORS
    # origin），浏览器拦截请求导致前端报 NetworkError。用 origin 正则覆盖本机与
    # 常见局域网网段，IP 变化也无需改配置。
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ——— 异常处理器 ———
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# ——— 注册路由 ———
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(trips_router)
app.include_router(lookup_router)
app.include_router(oauth_router)


@app.get("/api/health")
async def health():
    """健康检查"""
    return {"status": "ok", "version": "1.0.0"}
