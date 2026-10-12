"""pytest 测试夹具 — 使用独立测试库，完全隔离真实业务数据。

要点：
1. 环境变量必须在 import app 之前设置（pydantic-settings 中环境变量优先于 .env 文件）；
2. 使用独立的 test_travel_planner.db，会话前后清理，绝不触碰生产 travel_planner.db；
3. TestClient 以 context manager 运行，触发应用 lifespan（建表 + Redis 初始化）。
"""

import os

# ——— 必须最先执行：指向独立测试库（相对 backend 工作目录） ———
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_travel_planner.db"
os.environ["DATABASE_URL_SYNC"] = "sqlite:///./test_travel_planner.db"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"
os.environ["JWT_SECRET"] = "pytest-secret-key-not-for-production"
os.environ["APP_ENV"] = "test"

from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

TEST_DB_FILE = Path(__file__).resolve().parent.parent / "test_travel_planner.db"


@pytest.fixture(scope="session", autouse=True)
def _cleanup_test_db():
    """测试会话前后清理独立测试库文件"""
    if TEST_DB_FILE.exists():
        TEST_DB_FILE.unlink()
    yield
    if TEST_DB_FILE.exists():
        TEST_DB_FILE.unlink()


@pytest.fixture(scope="session")
def client():
    """FastAPI TestClient — context manager 触发 lifespan（建表 + Redis 连接）"""
    with TestClient(app) as c:
        yield c
