"""健康检查 & 配置清理验证"""

from app.config import settings


def test_health(client):
    """健康检查端点应返回 ok"""
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_database_url_is_sqlite():
    """清理后配置默认值应为本地 SQLite（无外部服务依赖）"""
    assert settings.DATABASE_URL.startswith("sqlite+aiosqlite")
    assert settings.DATABASE_URL_SYNC.startswith("sqlite")


def test_removed_config_fields_gone():
    """验证已删除的死配置字段确实从 Settings 中移除"""
    removed = (
        "GOOGLE_PLACES_API_KEY",
        "GOOGLE_MAPS_API_KEY",
        "OPENWEATHER_API_KEY",
        "EXCHANGE_RATE_API_KEY",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
    )
    for field in removed:
        assert not hasattr(settings, field), f"字段 {field} 应已删除"


def test_essential_config_preserved():
    """核心配置字段必须保留（删除时不能误伤）"""
    for field in ("LLM_PROVIDER", "DEEPSEEK_API_KEY", "BAIDU_MAP_AK",
                  "JWT_SECRET", "REDIS_URL", "CORS_ORIGINS", "DATABASE_URL"):
        assert hasattr(settings, field), f"字段 {field} 不应被删除"
