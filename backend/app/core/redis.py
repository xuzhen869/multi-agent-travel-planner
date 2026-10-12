"""Redis 连接管理（开发模式内存降级）"""

import logging
import time as _time
import asyncio

import redis.asyncio as aioredis
from app.config import settings

logger = logging.getLogger(__name__)

redis_client: aioredis.Redis | None = None
_redis_ok = False
_mem: dict[str, tuple[str, float]] = {}
_pubsub_channels: dict[str, list[asyncio.Queue]] = {}


class _FakePubSub:
    """内存版 pubsub，用于 SSE"""

    def __init__(self, channel: str):
        self.channel = channel
        if channel not in _pubsub_channels:
            _pubsub_channels[channel] = []
        self.queue: asyncio.Queue = asyncio.Queue()
        _pubsub_channels[channel].append(self.queue)

    async def subscribe(self, channel: str):
        pass

    async def listen(self):
        while True:
            msg = await self.queue.get()
            yield msg

    async def unsubscribe(self, channel: str = ""):
        if self.channel in _pubsub_channels:
            queues = _pubsub_channels[self.channel]
            if self.queue in queues:
                queues.remove(self.queue)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.unsubscribe()


async def init_redis():
    global redis_client, _redis_ok
    try:
        # 连接池需兼顾 SSE 长连接（pubsub）与常规命令并发，避免被占满
        # protocol=2：兼容本地 Redis 5.0（tporadowski Windows 移植版）。
        # redis-py 5.2 默认 RESP3，连接时会发 `HELLO` 握手，Redis 5.0 不支持该命令。
        redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
            protocol=2,
        )
        await redis_client.ping()
        _redis_ok = True
        logger.info("Redis 连接成功")
    except Exception as e:
        logger.warning("Redis 不可用，内存降级: %s", e)
        _redis_ok = False


async def close_redis():
    global redis_client
    if redis_client:
        try: await redis_client.close()
        except Exception: pass


# ——— 统一接口 ———

async def rset(key: str, value: str, ttl: int):
    if _redis_ok and redis_client:
        await redis_client.setex(key, ttl, value)
    else:
        _mem[key] = (value, _time.time() + ttl)


async def rget(key: str) -> str | None:
    if _redis_ok and redis_client:
        return await redis_client.get(key)
    e = _mem.get(key)
    if e:
        v, exp = e
        if _time.time() < exp:
            return v
        del _mem[key]
    return None


async def rdel(key: str):
    if _redis_ok and redis_client:
        await redis_client.delete(key)
    else:
        _mem.pop(key, None)


async def rpublish(channel: str, message: str):
    if _redis_ok and redis_client:
        await redis_client.publish(channel, message)
    else:
        for q in _pubsub_channels.get(channel, []):
            await q.put({"type": "message", "data": message})


def rpubsub():
    if _redis_ok and redis_client:
        return redis_client.pubsub()
    return None


def rpubsub_fake(channel: str):
    """内存版 pubsub（当 Redis 不可用时）"""
    return _FakePubSub(channel)


def is_redis_available() -> bool:
    return _redis_ok


def get_redis():
    return redis_client
