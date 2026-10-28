"""
Celery worker / 队列 快照监控 —— 全原生（inspect + broker LLEN），不引入 Flower。

- worker 存活/并发/已处理/内存/正在跑：`celery_app.control.inspect`（同步广播 RPC → 丢线程池 + 超时）
- 队列积压：broker（Redis）`LLEN <queue>`
- 无人消费告警：预期队列有积压却没 worker 消费 → danger（本平台最痛的“任务永远 pending”）
- 整快照缓存数秒，避免每次请求都打 broker / 被挂掉的 worker 拖住。
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as aioredis
from app.core.config import settings
from app.tasks.celery_app import celery_app

# 预期队列（见 celery_app.py 路由 + worker -Q 起法）；主看这几个，<node>.dq 直达队列略过
EXPECTED_QUEUES = ["ai_tasks", "app_tasks"]
# 每个 inspect 方法都是一次广播、各自等满 timeout（不会因先到的回复提前返回），
# 所以调用次数 × timeout = 总耗时。保持小 timeout + 少调用，靠缓存抹平。
_INSPECT_TIMEOUT = 1.0
_CACHE_TTL = 8.0

_broker_redis: Optional[aioredis.Redis] = None
_cache: dict = {"at": 0.0, "data": None}
_lock = asyncio.Lock()


def _get_broker_redis() -> aioredis.Redis:
    global _broker_redis
    if _broker_redis is None:
        # broker 就是队列所在库（CELERY_BROKER_URL，Redis db1）；队列 = 同名 Redis list
        _broker_redis = aioredis.from_url(
            settings.CELERY_BROKER_URL, encoding="utf-8", decode_responses=True
        )
    return _broker_redis


def _inspect_snapshot() -> dict:
    """同步 inspect（在 to_thread 里跑）；worker 全挂时各项返回 None → 归一为 {}。"""
    insp = celery_app.control.inspect(timeout=_INSPECT_TIMEOUT)
    # stats 已含存活/并发/累计/内存 → 省掉 ping（存活=是否出现在 stats），少一次广播
    return {
        "stats": insp.stats() or {},
        "active": insp.active() or {},
        "active_queues": insp.active_queues() or {},
    }


def _build_workers(snap: dict) -> list[dict]:
    stats, active, aq = snap["stats"], snap["active"], snap["active_queues"]
    names = set(stats) | set(active) | set(aq)
    workers: list[dict] = []
    for w in sorted(names):
        st = stats.get(w) or {}
        pool = st.get("pool") or {}
        total = st.get("total")
        processed = sum(total.values()) if isinstance(total, dict) else int(total or 0)
        rusage = st.get("rusage") or {}
        workers.append(
            {
                "name": w,
                "alive": w in stats,
                "concurrency": pool.get("max-concurrency")
                or len(pool.get("processes") or [])
                or 0,
                "processed": int(processed or 0),
                "active": len(active.get(w) or []),
                "queues": [
                    q.get("name")
                    for q in (aq.get(w) or [])
                    if q.get("name") and ".dq" not in q["name"]
                ],
                "mem_rss_kb": int(rusage.get("maxrss") or 0),
            }
        )
    return workers


def _build_queues(workers: list[dict], depths: dict[str, int]) -> list[dict]:
    consume: dict[str, int] = {}
    for w in workers:
        for q in w["queues"]:
            consume[q] = consume.get(q, 0) + 1
    ordered = EXPECTED_QUEUES + [
        q for q in consume if q not in EXPECTED_QUEUES and ".dq" not in q
    ]
    queues: list[dict] = []
    seen: set[str] = set()
    for q in ordered:
        if q in seen:
            continue
        seen.add(q)
        depth = int(depths.get(q, 0))
        wc = consume.get(q, 0)
        if wc == 0 and depth > 0:
            level = "danger"  # 有积压却无人消费 —— 任务会永远 pending
        elif wc == 0 and q in EXPECTED_QUEUES:
            level = "warn"  # 预期队列暂时没 worker（当前无积压）
        else:
            level = "ok"
        queues.append(
            {
                "name": q,
                "backlog": depth,
                "worker_count": wc,
                "has_worker": wc > 0,
                "level": level,
            }
        )
    return queues


def _build_beat() -> list[dict]:
    return [
        {"name": name, "task": cfg.get("task"), "schedule": str(cfg.get("schedule"))}
        for name, cfg in (celery_app.conf.beat_schedule or {}).items()
    ]


async def get_snapshot(force: bool = False) -> dict:
    """组装一份 worker/队列/beat 监控快照（数秒缓存）。inspect 失败即降级为“无 worker”。"""
    async with _lock:
        now = time.monotonic()
        if (
            not force
            and _cache["data"] is not None
            and (now - _cache["at"]) < _CACHE_TTL
        ):
            return _cache["data"]

        try:
            snap = await asyncio.wait_for(
                asyncio.to_thread(_inspect_snapshot),
                timeout=_INSPECT_TIMEOUT * 3 + 5,
            )
        except Exception:
            snap = {"stats": {}, "active": {}, "active_queues": {}}

        workers = _build_workers(snap)

        r = _get_broker_redis()
        q_names = list(
            dict.fromkeys(EXPECTED_QUEUES + [q for w in workers for q in w["queues"]])
        )
        depths: dict[str, int] = {}
        for q in q_names:
            if ".dq" in q:
                continue
            try:
                depths[q] = int(await r.llen(q))
            except Exception:
                depths[q] = 0

        queues = _build_queues(workers, depths)
        data = {
            "summary": {
                "workers_online": sum(1 for w in workers if w["alive"]),
                "total_concurrency": sum(w["concurrency"] for w in workers),
                "total_backlog": sum(q["backlog"] for q in queues),
                "active_tasks": sum(w["active"] for w in workers),
                "alerts": sum(1 for q in queues if q["level"] == "danger"),
            },
            "workers": workers,
            "queues": queues,
            "beat_jobs": _build_beat(),
            "degraded": len(workers) == 0,
            "inspected_at": datetime.now(timezone.utc).isoformat(),
        }
        _cache["data"] = data
        _cache["at"] = now
        return data
