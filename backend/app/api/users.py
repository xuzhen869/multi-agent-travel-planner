"""用户 & 偏好 & 画像 API 端点"""

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.preference import UserPreference, UserProfile
from app.schemas.user import (
    UserResponse,
    UserUpdateRequest,
    PreferenceRequest,
    PreferenceResponse,
    UserProfileResponse,
)
from app.core.exceptions import NotFoundError

router = APIRouter(prefix="/api/users", tags=["用户"])


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """获取当前用户信息"""
    # 查偏好获取 is_first_time
    stmt = select(UserPreference).where(UserPreference.user_id == current_user.id)
    result = await db.execute(stmt)
    pref = result.scalar_one_or_none()
    is_first_time = pref.is_first_time if pref else True

    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        display_name=current_user.display_name,
        oauth_provider=current_user.oauth_provider,
        is_first_time=is_first_time,
        created_at=current_user.created_at.isoformat() if current_user.created_at else "",
    )


@router.put("/me", response_model=UserResponse)
async def update_me(
    req: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新当前用户信息"""
    if req.display_name is not None:
        current_user.display_name = req.display_name
    await db.flush()

    stmt = select(UserPreference).where(UserPreference.user_id == current_user.id)
    result = await db.execute(stmt)
    pref = result.scalar_one_or_none()

    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        display_name=current_user.display_name,
        oauth_provider=current_user.oauth_provider,
        is_first_time=pref.is_first_time if pref else True,
        created_at=current_user.created_at.isoformat() if current_user.created_at else "",
    )


# ——— 偏好 ———


@router.get("/me/preferences", response_model=PreferenceResponse)
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户偏好"""
    stmt = select(UserPreference).where(UserPreference.user_id == current_user.id)
    result = await db.execute(stmt)
    pref = result.scalar_one_or_none()

    if not pref:
        # 返回默认偏好
        return PreferenceResponse(
            default_departure_city=None,
            preferred_hotel_star=4,
            preferred_flight_class="economy",
            pace="moderate",
            interests=[],
            dietary=[],
            budget_default_currency="CNY",
            default_travelers=[{"age": 30, "type": "adult"}],
            is_first_time=True,
        )

    return PreferenceResponse(
        default_departure_city=pref.default_departure_city,
        preferred_hotel_star=pref.preferred_hotel_star,
        preferred_flight_class=pref.preferred_flight_class,
        pace=pref.pace,
        interests=pref.interests or [],
        dietary=pref.dietary or [],
        budget_default_currency=pref.budget_default_currency,
        default_travelers=pref.default_travelers or [{"age": 30, "type": "adult"}],
        is_first_time=pref.is_first_time,
    )


@router.put("/me/preferences", response_model=PreferenceResponse)
async def update_preferences(
    req: PreferenceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新偏好（首次设置后 is_first_time 自动置为 False）"""
    stmt = select(UserPreference).where(UserPreference.user_id == current_user.id)
    result = await db.execute(stmt)
    pref = result.scalar_one_or_none()

    if not pref:
        pref = UserPreference(user_id=current_user.id)
        db.add(pref)

    # 更新字段
    if req.default_departure_city is not None:
        pref.default_departure_city = req.default_departure_city
    pref.preferred_hotel_star = req.preferred_hotel_star
    pref.preferred_flight_class = req.preferred_flight_class
    pref.pace = req.pace
    pref.interests = req.interests
    pref.dietary = req.dietary
    pref.budget_default_currency = req.budget_default_currency
    pref.default_travelers = [t.model_dump() for t in req.default_travelers]

    # 首次设置偏好
    if pref.is_first_time:
        pref.is_first_time = False

    await db.flush()

    return PreferenceResponse(
        default_departure_city=pref.default_departure_city,
        preferred_hotel_star=pref.preferred_hotel_star,
        preferred_flight_class=pref.preferred_flight_class,
        pace=pref.pace,
        interests=pref.interests or [],
        dietary=pref.dietary or [],
        budget_default_currency=pref.budget_default_currency,
        default_travelers=pref.default_travelers or [],
        is_first_time=pref.is_first_time,
    )


# ——— 用户画像 ———


@router.get("/me/profile", response_model=UserProfileResponse)
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取用户画像（缓存）"""
    stmt = select(UserProfile).where(UserProfile.user_id == current_user.id)
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()

    if not profile:
        return UserProfileResponse(
            label=None,
            traits=[],
            budget_flexibility=None,
            generated_at=None,
        )

    return UserProfileResponse(
        label=profile.label,
        traits=profile.traits or [],
        budget_flexibility=profile.budget_flexibility,
        generated_at=profile.generated_at.isoformat() if profile.generated_at else None,
    )


@router.post("/me/profile/refresh", response_model=UserProfileResponse, status_code=202)
async def refresh_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """重新生成用户画像（触发 ProfileAgent）"""
    # 触发 Celery 异步任务重新生成画像
    from app.tasks.planner_task import refresh_user_profile
    refresh_user_profile.delay(str(current_user.id))

    return UserProfileResponse(
        label=None,
        traits=[],
        budget_flexibility=None,
        generated_at=None,
    )
