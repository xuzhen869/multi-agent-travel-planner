"""SSE 进度推送服务

使用 Redis Pub/Sub 作为中间层：
Celery worker 发布进度事件 → Redis channel → FastAPI SSE endpoint 转发给前端
"""

import json
import logging
import time
from typing import AsyncIterator

logger = logging.getLogger(__name__)

from app.core.redis import rpublish, rpubsub, rpubsub_fake, is_redis_available


class ProgressService:
    """规划进度管理"""

    CHANNEL_PREFIX = "planner:progress:"

    @classmethod
    def _channel(cls, trip_id: str) -> str:
        return f"{cls.CHANNEL_PREFIX}{trip_id}"

    # ——— 发布端（Celery worker 调用） ———

    @staticmethod
    async def publish_event(trip_id: str, event: str, data: dict) -> None:
        """发布一条进度事件"""
        payload = json.dumps({"event": event, "data": data})
        await rpublish(f"planner:progress:{trip_id}", payload)

    @staticmethod
    async def publish_profile_start(trip_id: str) -> None:
        await ProgressService.publish_event(
            trip_id,
            "profile_start",
            {"message": "正在分析你的旅行偏好...", "ts": int(time.time())},
        )

    @staticmethod
    async def publish_profile_complete(trip_id: str, label: str, strategy_count: int) -> None:
        await ProgressService.publish_event(
            trip_id,
            "profile_complete",
            {"label": label, "strategies": strategy_count, "ts": int(time.time())},
        )

    @staticmethod
    async def publish_agent_start(trip_id: str, agent_name: str, message: str) -> None:
        await ProgressService.publish_event(
            trip_id,
            "agent_start",
            {"agent": agent_name, "message": message, "ts": int(time.time())},
        )

    @staticmethod
    async def publish_agent_complete(
        trip_id: str, agent_name: str, result_count: int, duration_ms: int
    ) -> None:
        await ProgressService.publish_event(
            trip_id,
            "agent_complete",
            {
                "agent": agent_name,
                "results": result_count,
                "duration_ms": duration_ms,
                "ts": int(time.time()),
            },
        )

    @staticmethod
    async def publish_recommend_start(trip_id: str, total: int) -> None:
        await ProgressService.publish_event(
            trip_id,
            "recommend_start",
            {"message": f"基于你的偏好生成 {total} 套方案...", "total": total, "ts": int(time.time())},
        )

    @staticmethod
    async def publish_recommend_plan_ready(
        trip_id: str, plan_id: str, title: str, reason: str
    ) -> None:
        await ProgressService.publish_event(
            trip_id,
            "recommend_plan_ready",
            {
                "plan_id": plan_id,
                "title": title,
                "reason": reason,
                "ts": int(time.time()),
            },
        )

    @staticmethod
    async def publish_planner_complete(trip_id: str, plan_count: int) -> None:
        await ProgressService.publish_event(
            trip_id,
            "planner_complete",
            {
                "trip_id": trip_id,
                "message": f"{plan_count} 套方案已就绪，请选择！",
                "plan_count": plan_count,
                "ts": int(time.time()),
            },
        )

    @staticmethod
    async def publish_planner_error(trip_id: str, message: str, error_code: str) -> None:
        await ProgressService.publish_event(
            trip_id,
            "planner_error",
            {"message": message, "error_code": error_code, "ts": int(time.time())},
        )

    # ——— 方案级事件（按 plan_id 归属，供前端「方案方框 + Agent 步骤流」渲染） ———

    @staticmethod
    async def publish_plan_start(trip_id: str, plan_id: str, title: str, reason: str) -> None:
        """某个方案开始生成"""
        await ProgressService.publish_event(
            trip_id,
            "plan_start",
            {"plan_id": plan_id, "title": title, "reason": reason, "ts": int(time.time())},
        )

    @staticmethod
    async def publish_plan_agent_start(
        trip_id: str, plan_id: str, agent: str, step: str, message: str = ""
    ) -> None:
        """某个方案下某 Agent 步骤开始"""
        await ProgressService.publish_event(
            trip_id,
            "plan_agent_start",
            {
                "plan_id": plan_id,
                "agent": agent,
                "step": step,
                "message": message,
                "ts": int(time.time()),
            },
        )

    @staticmethod
    async def publish_plan_agent_complete(
        trip_id: str, plan_id: str, agent: str, step: str, message: str = ""
    ) -> None:
        """某个方案下某 Agent 步骤完成"""
        await ProgressService.publish_event(
            trip_id,
            "plan_agent_complete",
            {
                "plan_id": plan_id,
                "agent": agent,
                "step": step,
                "message": message,
                "ts": int(time.time()),
            },
        )

    @staticmethod
    async def publish_plan_ready(trip_id: str, plan_id: str, title: str, reason: str, cost: float) -> None:
        """某个方案就绪（携带标题/理由/预算，前端据此展示方框完成态）"""
        await ProgressService.publish_event(
            trip_id,
            "plan_ready",
            {
                "plan_id": plan_id,
                "title": title,
                "reason": reason,
                "cost": cost,
                "ts": int(time.time()),
            },
        )

    # ——— 订阅端（SSE endpoint 调用） ———

    @staticmethod
    async def subscribe(trip_id: str, snapshot: dict | None = None) -> AsyncIterator[str]:
        """订阅规划进度事件，返回异步生成器（SSE 格式）。

        Args:
            trip_id: 行程 ID
            snapshot: 连接时的行程状态快照，随 connected 事件补发给前端，
                      用于恢复订阅建立前已发生的进度事件（Redis Pub/Sub 无历史回放）。
        """
        channel_name = f"planner:progress:{trip_id}"

        def _connected() -> str:
            data = {"trip_id": trip_id}
            if snapshot:
                data["snapshot"] = snapshot
            return f"data: {json.dumps({'event': 'connected', 'data': data})}\n\n"

        def _parse(raw: str) -> tuple[str | None, str]:
            """解析事件 payload → (event_type, SSE 行)；无法解析时按原文透传"""
            try:
                parsed = json.loads(raw)
                event_type = parsed.get("event", "message")
                line = f"event: {event_type}\ndata: {json.dumps(parsed['data'])}\n\n"
                return event_type, line
            except (json.JSONDecodeError, KeyError):
                return None, f"data: {raw}\n\n"

        def _terminated(event_type: str | None) -> bool:
            return event_type in ("planner_complete", "planner_error")

        if is_redis_available():
            pubsub = rpubsub()
            await pubsub.subscribe(channel_name)
            yield _connected()
            try:
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        event_type, line = _parse(message["data"])
                        yield line
                        if _terminated(event_type):
                            break
            except Exception as e:
                logger.exception("[SSE] Redis 订阅读取异常: %s", e)
        else:
            async with rpubsub_fake(channel_name) as pubsub:
                yield _connected()
                async for message in pubsub.listen():
                    event_type, line = _parse(message["data"])
                    yield line
                    if _terminated(event_type):
                        break
