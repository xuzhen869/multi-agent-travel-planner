"""行程规划 & 路线选择 API 端点"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_optional
from app.core.database import get_db
from app.core.exceptions import NotFoundError, BadRequestError, UnauthorizedError
from app.models.user import User
from app.models.trip import Trip
from app.schemas.trip import (
    TripCreateRequest,
    TripResponse,
    TripDetailResponse,
    PlanCreatedResponse,
)
from app.services.planner_service import PlannerService
from app.services.progress_service import ProgressService
from sqlalchemy import select

router = APIRouter(prefix="/api/trips", tags=["行程"])


def _trip_to_response(trip: Trip) -> TripResponse:
    """Trip ORM → TripResponse"""
    return TripResponse(
        id=str(trip.id),
        title=trip.title,
        destination=trip.request_params.get("destination") if trip.request_params else None,
        status=trip.status,
        mode=trip.mode,
        selected_plan_id=trip.selected_plan_id,
        budget_total=float(trip.budget_total) if trip.budget_total else None,
        budget_currency=trip.budget_currency,
        user_profile_label=trip.user_profile.get("label") if trip.user_profile else None,
        created_at=trip.created_at.isoformat() if trip.created_at else "",
    )


def _trip_to_detail(trip: Trip) -> TripDetailResponse:
    """Trip ORM → TripDetailResponse"""
    # 推荐模式下返回多方案
    recommendations = None
    if trip.mode == "recommend" and trip.recommendations:
        recommendations = trip.recommendations.get("plans")

    return TripDetailResponse(
        id=str(trip.id),
        title=trip.title,
        status=trip.status,
        mode=trip.mode,
        request_params=trip.request_params or {},
        recommendations=recommendations,
        selected_plan_id=trip.selected_plan_id,
        plan_data=trip.plan_data,
        user_profile=trip.user_profile,
        weather=(trip.recommendations or {}).get("weather") if trip.recommendations else None,
        budget_total=float(trip.budget_total) if trip.budget_total else None,
        budget_currency=trip.budget_currency,
        started_at=trip.started_at.isoformat() if trip.started_at else None,
        completed_at=trip.completed_at.isoformat() if trip.completed_at else None,
        created_at=trip.created_at.isoformat() if trip.created_at else "",
        updated_at=trip.updated_at.isoformat() if trip.updated_at else "",
    )


@router.post("", response_model=PlanCreatedResponse, status_code=201)
async def create_trip(
    req: TripCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建行程 → 触发 ProfileAgent + 推荐规划"""
    trip = await PlannerService.create_trip(
        db=db,
        user_id=current_user.id,
        destination=req.destination,
        departure_city=req.departure_city,
        start_date=req.start_date,
        end_date=req.end_date,
        travelers=req.travelers,
        budget=req.budget,
        preferences=req.preferences,
        mode=req.mode,
    )
    return PlanCreatedResponse(
        trip_id=str(trip.id),
        status=trip.status,
        events_url=f"/api/trips/{trip.id}/events",
    )


@router.get("", response_model=list[TripResponse])
async def list_trips(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """行程列表"""
    trips = await PlannerService.list_trips(db, current_user.id, offset, limit)
    return [_trip_to_response(t) for t in trips]


@router.get("/{trip_id}", response_model=TripDetailResponse)
async def get_trip(
    trip_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """行程详情"""
    trip = await PlannerService.get_trip(db, trip_id, current_user.id)
    return _trip_to_detail(trip)


@router.post("/{trip_id}/select/{plan_id}", response_model=TripDetailResponse)
async def select_plan(
    trip_id: UUID,
    plan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """用户选择推荐方案"""
    trip = await PlannerService.select_plan(db, trip_id, current_user.id, plan_id)
    await db.flush()
    # flush 后显式异步刷新，避免序列化时同步访问过期属性触发 MissingGreenlet
    await db.refresh(trip)
    return _trip_to_detail(trip)


@router.delete("/{trip_id}", status_code=204)
async def delete_trip(
    trip_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除行程"""
    trip = await PlannerService.get_trip(db, trip_id, current_user.id)
    await db.delete(trip)
    return None


@router.get("/{trip_id}/events")
async def trip_events(
    trip_id: UUID,
    current_user: User | None = Depends(get_current_user_optional),
):
    """SSE 端点：推送规划实时进度。

    认证支持两种方式（EventSource 无法自定义 header，因此允许 query `token`）：
    1. Authorization: Bearer <token>
    2. ?token=<access_token>
    """
    if not current_user:
        raise UnauthorizedError("请先登录")

    # 验证行程属于当前用户，并构建连接快照（补发错过的早期事件）
    from app.core.database import async_session_factory
    async with async_session_factory() as db:
        stmt = select(Trip).where(Trip.id == trip_id, Trip.user_id == current_user.id)
        result = await db.execute(stmt)
        trip = result.scalar_one_or_none()
        if not trip:
            raise NotFoundError("行程未找到")

        snapshot = {
            "status": trip.status,
            "mode": trip.mode,
            "plan_count": len((trip.recommendations or {}).get("plans", [])) if trip.recommendations else 0,
            "selected_plan_id": trip.selected_plan_id,
            "profile_label": (trip.user_profile or {}).get("label") if trip.user_profile else None,
            "completed_at": trip.completed_at.isoformat() if trip.completed_at else None,
        }

    return StreamingResponse(
        ProgressService.subscribe(str(trip_id), snapshot=snapshot),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{trip_id}/regenerate", response_model=PlanCreatedResponse)
async def regenerate_trip(
    trip_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """重新规划行程"""
    trip = await PlannerService.get_trip(db, trip_id, current_user.id)

    # 重置状态与上次规划结果，避免旧数据残留混入展示
    from app.tasks.planner_task import run_planner
    trip.status = "recommending" if trip.mode == "recommend" else "planning"
    trip.recommendations = None
    trip.selected_plan_id = None
    trip.plan_data = None
    trip.user_profile = None
    trip.budget_total = None
    trip.budget_currency = None
    trip.started_at = None
    trip.completed_at = None
    await db.flush()

    run_planner.delay(str(trip.id), trip.mode)

    return PlanCreatedResponse(
        trip_id=str(trip.id),
        status=trip.status,
        events_url=f"/api/trips/{trip.id}/events",
    )
