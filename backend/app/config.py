"""应用配置 — 所有环境变量通过 pydantic-settings 管理"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ——— LLM ———
    LLM_PROVIDER: str = "deepseek"  # deepseek | anthropic
    LLM_MODEL: str = "deepseek-chat"  # deepseek-chat(V3) / deepseek-reasoner(R1)
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    # LLM_PROVIDER=anthropic 时使用
    ANTHROPIC_API_KEY: str = ""

    # ——— Amadeus ———
    AMADEUS_API_KEY: str = ""
    AMADEUS_API_SECRET: str = ""

    # ——— 百度地图（覆盖天气/POI/地址搜索/路线规划） ———
    BAIDU_MAP_AK: str = ""
    BAIDU_MAP_SK: str = ""  # 可选，SN 校验模式时填写

    # ——— 数据库（本地 SQLite，无外部服务依赖） ———
    DATABASE_URL: str = "sqlite+aiosqlite:///./travel_planner.db"
    DATABASE_URL_SYNC: str = "sqlite:///./travel_planner.db"

    # ——— Redis ———
    REDIS_URL: str = "redis://localhost:6379/0"

    # ——— JWT ———
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ——— OAuth ———
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""

    # ——— App ———
    APP_ENV: str = "development"
    CORS_ORIGINS: str = "http://localhost:3000"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"


# 单例
settings = Settings()
