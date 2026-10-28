"""Redis 实时事件总线

职责：
  - 实时事件 Pub/Sub（worker PUBLISH，SSE 端 SUBSCRIBE）
  - 取消标志（协作式取消）
  - 运行锁（执行幂等第2层兜底）
  - 提交锁（提交去重第1层兜底）

频道/键：
  - 事件频道  ai:task:{id}:events
  - 取消标志  ai:task:{id}:cancel
  - 运行锁    ai:task:{id}:run
  - 提交锁    ai:submit:{key}
"""

import json
from typing import AsyncIterator, Optional

import redis.asyncio as aioredis

from app.core.config import settings

_client: Optional[aioredis.Redis] = None


def get_redis() -> aioredis.Redis:
    global _client
    if _client is None:
        _client = aioredis.from_url(
            settings.REDIS_URL, encoding="utf-8", decode_responses=True
        )
    return _client


async def close_redis() -> None:
    """关闭全局客户端并重置。

    Celery prefork 下每个任务 ``asyncio.run`` 新建事件循环，连接绑定旧 loop，
    任务收尾必须在当前 loop 内关闭，否则下个任务复用会报
    "attached to a different loop" / "Event loop is closed"。
    """
    global _client
    if _client is not None:
        try:
            await _client.aclose()
        except Exception:  # noqa: BLE001
            pass
        _client = None


def _events_channel(task_id: int) -> str:
    return f"ai:task:{task_id}:events"


def _cancel_key(task_id: int) -> str:
    return f"ai:task:{task_id}:cancel"


def _run_lock_key(task_id: int) -> str:
    return f"ai:task:{task_id}:run"


def _submit_lock_key(key: str) -> str:
    return f"ai:submit:{key}"


# ── 事件发布 / 订阅 ──────────────────────────────────────────

async def publish(task_id: int, event: dict) -> None:
    await get_redis().publish(_events_channel(task_id), json.dumps(event, ensure_ascii=False))


async def open_subscription(task_id: int):
    """订阅频道并返回 pubsub（调用方负责 unsubscribe/aclose）。

    用于 SSE「先订阅再回放」，避免订阅与 DB 回放之间丢事件。
    """
    pubsub = get_redis().pubsub()
    await pubsub.subscribe(_events_channel(task_id))
    return pubsub


async def subscribe(task_id: int) -> AsyncIterator[dict]:
    """订阅任务事件，yield 事件 dict。收到 task_end 后由调用方决定关闭。"""
    pubsub = get_redis().pubsub()
    await pubsub.subscribe(_events_channel(task_id))
    try:
        async for msg in pubsub.listen():
            if msg is None or msg.get("type") != "message":
                continue
            data = msg.get("data")
            if not data:
                continue
            try:
                yield json.loads(data)
            except (ValueError, TypeError):
                continue
    finally:
        await pubsub.unsubscribe(_events_channel(task_id))
        await pubsub.aclose()


# ── 取消标志 ────────────────────────────────────────────────

async def request_cancel(task_id: int, ttl: int = 3600) -> None:
    await get_redis().set(_cancel_key(task_id), "1", ex=ttl)


async def is_canceled(task_id: int) -> bool:
    return await get_redis().exists(_cancel_key(task_id)) == 1


async def clear_cancel(task_id: int) -> None:
    await get_redis().delete(_cancel_key(task_id))


# ── 运行锁（第2层兜底）──────────────────────────────────────

async def acquire_run_lock(task_id: int, ttl: int) -> bool:
    """SET NX 运行锁，成功返回 True。"""
    return bool(await get_redis().set(_run_lock_key(task_id), "1", nx=True, ex=ttl))


async def release_run_lock(task_id: int) -> None:
    await get_redis().delete(_run_lock_key(task_id))


async def renew_run_lock(task_id: int, ttl: int) -> None:
    """续期运行锁 TTL（SET EX 覆盖，保持存活）。

    长压测（kind=load）运行时长可能超过初始 TTL，节点内周期调用续期，
    防止锁过期后被 task_acks_late 重投的第二个 worker 抢到、重复打流量（评审 blocker B3）。
    """
    await get_redis().set(_run_lock_key(task_id), "1", ex=ttl)


# ── 提交锁（第1层兜底）──────────────────────────────────────

async def acquire_submit_lock(key: str, ttl: int = 10) -> bool:
    return bool(await get_redis().set(_submit_lock_key(key), "1", nx=True, ex=ttl))


async def release_submit_lock(key: str) -> None:
    await get_redis().delete(_submit_lock_key(key))
