"""行程 & 规划相关 Pydantic schemas"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# 行程规划模式：推荐（多方案） / 直接（单方案定制）
TripMode = Literal["recommend", "direct"]


# ——— 行程 ———


class TripCreateRequest(BaseModel):
    """创建行程请求（推荐模式）"""

    destination: str = Field(min_length=1, max_length=100)
    departure_city: str = Field(min_length=1, max_length=100)
    start_date: str = Field(description="YYYY-MM-DD")
    end_date: str = Field(description="YYYY-MM-DD")
    travelers: list[dict] = Field(default_factory=list)  # [{"age": 28, "type": "adult"}]
    budget: dict | None = None  # {"total": 20000, "currency": "CNY"}
    preferences: dict | None = None  # 本次行程偏好覆盖
    mode: TripMode = "recommend"


class TripResponse(BaseModel):
    """行程列表项"""

    id: str
    title: str | None
    destination: str | None
    status: str
    mode: str
    selected_plan_id: str | None
    budget_total: float | None
    budget_currency: str | None
    user_profile_label: str | None
    created_at: str

    model_config = {"from_attributes": True}


class TripDetailResponse(BaseModel):
    """行程详情响应"""

    id: str
    title: str | None
    status: str
    mode: str
    request_params: dict
    recommendations: list[dict] | None  # 推荐模式：多方案
    selected_plan_id: str | None
    plan_data: dict | None  # 选中方案的完整行程
    user_profile: dict | None
    weather: list[dict] | None  # 天气预报
    budget_total: float | None
    budget_currency: str | None
    started_at: str | None
    completed_at: str | None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class PlanCreatedResponse(BaseModel):
    """创建行程后的即时响应"""

    trip_id: str
    status: str  # "recommending"
    events_url: str
