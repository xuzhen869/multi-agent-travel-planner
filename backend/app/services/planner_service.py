"""规划服务 — 触发 Celery 异步规划任务"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trip import Trip
from app.models.preference import UserPreference, UserProfile
from app.core.exceptions import NotFoundError, BadRequestError
from app.tasks.planner_task import run_planner


class PlannerService:
    """行程规划业务逻辑"""

    @staticmethod
    async def create_trip(
        db: AsyncSession,
        user_id: UUID,
        destination: str,
        departure_city: str,
        start_date: str,
        end_date: str,
        travelers: list[dict],
        budget: dict | None,
        preferences: dict | None,
        mode: str = "recommend",
    ) -> Trip:
        """创建行程并触发后台规划"""
        # 构建请求参数
        request_params = {
            "destination": destination,
            "departure_city": departure_city,
            "start_date": start_date,
            "end_date": end_date,
            "travelers": travelers,
            "budget": budget or {},
            "preferences": preferences or {},
        }

        # 生成标题
        title = f"{departure_city} → {destination}（{start_date} ~ {end_date}）"

        trip = Trip(
            user_id=user_id,
            title=title,
            status="recommending" if mode == "recommend" else "planning",
            mode=mode,
            request_params=request_params,
            started_at=None,  # Celery 任务中设置
        )
        db.add(trip)
        await db.flush()  # 获取 trip.id

        # 异步触发规划（Celery）
        run_planner.delay(str(trip.id), mode)

        return trip

    @staticmethod
    async def get_trip(db: AsyncSession, trip_id: UUID, user_id: UUID) -> Trip:
        """获取行程详情"""
        stmt = select(Trip).where(Trip.id == trip_id, Trip.user_id == user_id)
        result = await db.execute(stmt)
        trip = result.scalar_one_or_none()
        if not trip:
            raise NotFoundError("行程未找到")
        return trip

    @staticmethod
    async def list_trips(
        db: AsyncSession, user_id: UUID, offset: int = 0, limit: int = 20
    ) -> list[Trip]:
        """获取用户行程列表"""
        stmt = (
            select(Trip)
            .where(Trip.user_id == user_id)
            .order_by(Trip.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def select_plan(
        db: AsyncSession, trip_id: UUID, user_id: UUID, plan_id: str
    ) -> Trip:
        """用户选择一个推荐方案，展开为完整行程"""
        trip = await PlannerService.get_trip(db, trip_id, user_id)

        # direct 模式：唯一方案在规划完成时已自动选定，选择操作幂等返回
        if trip.mode == "direct":
            if trip.selected_plan_id:
                return trip
            raise BadRequestError("该行程为直接规划模式，方案已自动选定")

        recommendations = trip.recommendations or {}
        plans = recommendations.get("plans", [])
        selected = next((p for p in plans if p.get("id") == plan_id), None)
        if not selected:
            raise BadRequestError(f"方案 {plan_id} 不存在")

        trip.selected_plan_id = plan_id
        trip.plan_data = selected
        trip.status = "completed"
        return trip

    @staticmethod
    async def get_user_profile_dict(db: AsyncSession, user_id: UUID) -> dict | None:
        """获取用户画像（字典格式）"""
        stmt = select(UserProfile).where(UserProfile.user_id == user_id)
        result = await db.execute(stmt)
        profile = result.scalar_one_or_none()
        if not profile:
            return None
        return {
            "label": profile.label,
            "traits": profile.traits or [],
            "budget_flexibility": profile.budget_flexibility,
            "generated_at": profile.generated_at.isoformat() if profile.generated_at else None,
        }
