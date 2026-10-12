"""Celery 应用配置"""

from celery import Celery
from kombu.transport import redis as _kombu_redis
import celery.backends.redis as _celery_redis_backend

from app.config import settings

# ——— Redis 5.0 兼容：强制 RESP2 协议 ———
# redis-py 5.2 默认使用 RESP3 协议，连接时会向 Redis 发送 `HELLO 3` 握手命令。
# HELLO 是 Redis 6.0 才引入的命令，而本项目本地使用 tporadowski 的 Windows 移植版
# Redis 5.0（不支持 HELLO），收到后返回 `unknown command 'HELLO'`，导致 Celery
# broker 连接失败，前端规划新行程时报 NetworkError。这里 monkey-patch kombu 的
# Redis Channel，在生成的连接参数中强制 protocol=2（RESP2，Redis 5.0 完全兼容）。
# 注意：必须在任何 broker 连接建立之前执行（模块导入时）。
_orig_connparams = _kombu_redis.Channel._connparams


def _connparams_resp2(channel, *args, **kwargs):
    """在 kombu 生成的 Redis 连接参数中注入 RESP2，覆盖 redis-py 的 RESP3 默认值。"""
    params = _orig_connparams(channel, *args, **kwargs)
    params["protocol"] = 2  # RESP2，Redis 5.0 兼容（Redis 6+ 同样支持）
    return params


_kombu_redis.Channel._connparams = _connparams_resp2

# ——— 结果后端（RedisBackend）同样需要强制 RESP2 ———
# Celery 的 Redis result backend 不走 kombu broker，而是用 redis-py 直接创建
# 客户端（self.client = redis.Redis(**connparams)），同样默认 RESP3 导致 HELLO
# 握手失败（send_task 时 RedisBackend.on_task_call 会订阅结果频道触发连接）。
# 因此在 RedisBackend 初始化后给 connparams 注入 protocol=2。
_orig_backend_init = _celery_redis_backend.RedisBackend.__init__


def _backend_init_resp2(backend, *args, **kwargs):
    """在 RedisBackend 初始化后强制 RESP2，覆盖 redis-py 的 RESP3 默认值。"""
    _orig_backend_init(backend, *args, **kwargs)
    backend.connparams["protocol"] = 2  # RESP2，Redis 5.0 兼容


_celery_redis_backend.RedisBackend.__init__ = _backend_init_resp2

celery_app = Celery(
    "travel_planner",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.planner_task"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 最长 5 分钟
    task_soft_time_limit=240,  # 软限制 4 分钟
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
)
