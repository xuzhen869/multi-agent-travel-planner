"""用户 & 偏好相关 Pydantic schemas"""

from datetime import datetime
from pydantic import BaseModel, Field


# ——— 用户 ———


class UserResponse(BaseModel):
    """用户信息响应"""

    id: str
    email: str
    display_name: str | None
    oauth_provider: str | None
    is_first_time: bool
    created_at: str

    model_config = {"from_attributes": True}


class UserUpdateRequest(BaseModel):
    """更新用户信息"""

    display_name: str | None = Field(default=None, max_length=100)


# ——— 出行人 ———


class Traveler(BaseModel):
    """单个出行人"""

    age: int = Field(ge=0, le=120)
    type: str = Field(default="adult")  # adult / child / senior


class TravelerResponse(Traveler):
    pass


# ——— 偏好 ———


class PreferenceRequest(BaseModel):
    """保存偏好请求"""

    default_departure_city: str | None = None
    preferred_hotel_star: int = Field(default=4, ge=1, le=5)
    preferred_flight_class: str = Field(default="economy")  # economy / business / first
    pace: str = Field(default="moderate")  # relaxed / moderate / intensive
    interests: list[str] = Field(default_factory=list)
    dietary: list[str] = Field(default_factory=list)
    budget_default_currency: str = Field(default="CNY", max_length=3)
    default_travelers: list[Traveler] = Field(default_factory=lambda: [Traveler(age=30)])


class PreferenceResponse(BaseModel):
    """偏好响应"""

    default_departure_city: str | None
    preferred_hotel_star: int
    preferred_flight_class: str
    pace: str
    interests: list[str]
    dietary: list[str]
    budget_default_currency: str
    default_travelers: list[TravelerResponse]
    is_first_time: bool

    model_config = {"from_attributes": True}


# ——— 用户画像 ———


class UserProfileResponse(BaseModel):
    """用户画像响应"""

    label: str | None
    traits: list[str]
    budget_flexibility: str | None
    generated_at: str | None

    model_config = {"from_attributes": True}
