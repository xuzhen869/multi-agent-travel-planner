"""后台规划任务（Celery Task） — 使用 LangGraph StateGraph 编排 Agent"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from app.core.database import async_session_factory
from app.models.trip import Trip
from app.models.preference import UserProfile, UserPreference
from app.services.progress_service import ProgressService
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def run_planner(self, trip_id: str, mode: str = "recommend"):
    """主规划任务 — LangGraph 编排完整 Agent 流程"""
    import asyncio
    import time as time_mod

    async def _run():
        # Celery worker 进程不经过 FastAPI lifespan，无法自动初始化 Redis。
        # 若不在此初始化，进度事件发布会走进程内内存降级（_pubsub_channels），
        # 而 SSE 端（uvicorn 进程订阅 Redis channel）收不到，前端永远停在
        # "正在连接..."。必须在任务自身的 asyncio loop 内初始化，保证
        # aioredis 客户端与当前 loop 绑定。
        from app.core.redis import init_redis
        await init_redis()

        async with async_session_factory() as db:
            trip = None
            try:
                # ——— 加载 trip ———
                stmt = select(Trip).where(Trip.id == UUID(trip_id))
                result = await db.execute(stmt)
                trip = result.scalar_one_or_none()
                if not trip:
                    logger.error("行程 %s 未找到", trip_id)
                    return

                trip.started_at = datetime.now(timezone.utc)
                trip.status = "recommending" if mode == "recommend" else "planning"
                await db.commit()

                # ——— 加载用户偏好 ———
                pref_stmt = select(UserPreference).where(UserPreference.user_id == trip.user_id)
                pref_result = await db.execute(pref_stmt)
                pref = pref_result.scalar_one_or_none()

                # ——— 构建初始状态 ———
                request_params = trip.request_params or {}

                # 注意：用 `or` 而非 `get`，避免请求里的空 dict/空预算
                # 覆盖掉用户已保存的偏好（dict.get 只在 key 缺失时返回默认值）
                preferences = request_params.get("preferences") or {
                    "hotel_star": pref.preferred_hotel_star if pref else 4,
                    "flight_class": pref.preferred_flight_class if pref else "economy",
                    "pace": pref.pace if pref else "moderate",
                    "interests": pref.interests if pref else [],
                    "dietary": pref.dietary if pref else [],
                }
                budget = request_params.get("budget") or {"total": 20000, "currency": "CNY"}

                initial_state = {
                    "trip_id": trip_id,
                    "departure_city": request_params.get("departure_city", ""),
                    "destination": request_params.get("destination", ""),
                    "start_date": request_params.get("start_date", ""),
                    "end_date": request_params.get("end_date", ""),
                    "travelers": request_params.get("travelers", [{"age": 30, "type": "adult"}]),
                    "budget": budget,
                    "preferences": preferences,
                    "mode": mode,
                    "plan_results": [],
                }

                # ——— 构建 LangGraph ———
                from app.agents.graph import build_planner_graph

                graph = build_planner_graph()

                # ——— 使用 astream 获取每节点完成事件来推送 SSE 进度 ———
                t0 = time_mod.time()

                # 先发 profile_start（推荐模式）
                if mode == "recommend":
                    await ProgressService.publish_profile_start(trip_id)

                # 数据采集开始
                await ProgressService.publish_agent_start(trip_id, "FlightAgent", "正在搜索航班...")
                await ProgressService.publish_agent_start(trip_id, "HotelAgent", "正在搜索酒店...")
                await ProgressService.publish_agent_start(trip_id, "POIAgent", "正在搜索景点和餐厅...")

                final_state = None
                async for event in graph.astream(initial_state):
                    for node_name, node_output in event.items():
                        logger.info("[%s] LangGraph 节点完成: %s", trip_id, node_name)

                        if node_name == "profile":
                            strategies = node_output.get("strategies", [])
                            await ProgressService.publish_profile_complete(
                                trip_id,
                                node_output.get("user_profile", {}).get("label", "旅行者"),
                                len(strategies),
                            )
                            # 通知前端即将开始生成方案
                            await ProgressService.publish_recommend_start(trip_id, len(strategies))

                        elif node_name == "data_collection":
                            # 数据采集完成
                            flight_count = len(node_output.get("flight_candidates", []))
                            hotel_count = len(node_output.get("hotel_candidates", []))
                            poi_data = node_output.get("poi_data", {}) or {}
                            poi_count = len(poi_data.get("attractions", [])) + len(poi_data.get("restaurants", []))
                            dur = int((time_mod.time() - t0) * 1000)

                            await ProgressService.publish_agent_complete(trip_id, "FlightAgent", flight_count, dur)
                            await ProgressService.publish_agent_complete(trip_id, "HotelAgent", hotel_count, dur)
                            await ProgressService.publish_agent_complete(trip_id, "POIAgent", poi_count, dur)

                        elif node_name == "process_strategy":
                            # 方案级流式进度已由 graph._process_strategy_node 在节点内发布
                            # （plan_start / plan_agent_start / plan_agent_complete / plan_ready），
                            # 此处无需再重复推送 recommend_plan_ready。
                            pass

                        elif node_name == "synthesizer":
                            final_state = {**initial_state, **node_output}

                # 如果 astream 没有返回最终状态（例如空策略），手动调用
                if final_state is None:
                    final_state = initial_state

                # ——— 持久化结果 ———
                final_output = final_state.get("final_output", {})
                trip.recommendations = final_output
                trip.user_profile = final_output.get("user_profile", {})

                plans = final_output.get("plans", [])
                if plans:
                    trip.status = "completed"
                    trip.completed_at = datetime.now(timezone.utc)
                    trip.budget_total = plans[0].get("total_cost", 0)
                    trip.budget_currency = final_state.get("budget", {}).get("currency", "CNY")
                    # direct 模式：单方案自动选定，直接落到 plan_data
                    if mode == "direct":
                        trip.selected_plan_id = plans[0].get("id")
                        trip.plan_data = plans[0]
                else:
                    # 极端兜底：0 方案视为失败，避免"已完成但无结果"
                    trip.status = "draft"
                    trip.completed_at = None

                await db.commit()

                if plans:
                    await ProgressService.publish_planner_complete(trip_id, len(plans))
                    logger.info("[%s] LangGraph 规划完成！%d 个方案", trip_id, len(plans))
                else:
                    await ProgressService.publish_planner_error(trip_id, "未能生成任何可用方案", "NO_PLANS")
                    logger.error("[%s] LangGraph 规划完成但 0 个方案", trip_id)

            except Exception as e:
                logger.exception("[%s] 规划失败: %s", trip_id, e)
                if trip:
                    trip.status = "draft"
                    await db.commit()
                await ProgressService.publish_planner_error(trip_id, str(e), "PLANNING_FAILED")
                raise

    asyncio.run(_run())


@celery_app.task(bind=True, max_retries=1)
def refresh_user_profile(self, user_id: str):
    """后台刷新用户画像"""
    import asyncio

    async def _run():
        async with async_session_factory() as db:
            try:
                stmt = select(UserPreference).where(UserPreference.user_id == UUID(user_id))
                result = await db.execute(stmt)
                pref = result.scalar_one_or_none()
                if not pref:
                    logger.warning("用户 %s 无偏好数据，跳过画像刷新", user_id)
                    return

                from app.agents.profile_agent import ProfileAgent

                agent = ProfileAgent()
                profile_state = {
                    "departure_city": pref.default_departure_city or "",
                    "destination": "",
                    "start_date": "",
                    "end_date": "",
                    "travelers": pref.default_travelers or [{"age": 30, "type": "adult"}],
                    "budget": {"total": 0, "currency": pref.budget_default_currency},
                    "preferences": {
                        "hotel_star": pref.preferred_hotel_star,
                        "flight_class": pref.preferred_flight_class,
                        "pace": pref.pace,
                        "interests": pref.interests or [],
                        "dietary": pref.dietary or [],
                    },
                }

                profile_result = await agent.run(profile_state)
                profile_data = profile_result.get("user_profile", {})

                stmt2 = select(UserProfile).where(UserProfile.user_id == UUID(user_id))
                result2 = await db.execute(stmt2)
                profile = result2.scalar_one_or_none()

                if not profile:
                    profile = UserProfile(user_id=UUID(user_id))
                    db.add(profile)

                profile.label = profile_data.get("label", "旅行探索者")
                profile.traits = profile_data.get("traits", [])
                profile.budget_flexibility = profile_data.get("budget_flexibility", "moderate")
                profile.generated_at = datetime.now(timezone.utc)
                await db.commit()

                logger.info("用户 %s 画像刷新完成: %s", user_id, profile.label)

            except Exception as e:
                logger.exception("用户 %s 画像刷新失败: %s", user_id, e)
                raise

    asyncio.run(_run())
