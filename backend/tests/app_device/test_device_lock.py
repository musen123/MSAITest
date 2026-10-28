"""设备锁 + 一次性 ticket 集成测试（需要真实 Redis，不可达时整文件 skip）

覆盖契约 §4/§5 语义：SET NX 抢锁、被占返回持有者、Lua CAS 续期/释放/接管、
ticket GETDEL 一次性消费。
"""

import uuid

import pytest
import redis.asyncio as aioredis

from app.ai_core.runtime.event_bus import close_redis, get_redis
from app.core.config import settings
from app.services.app_device.lock import device_lock
from app.services.app_device.ticket import consume_ticket, issue_ticket

pytestmark = pytest.mark.integration


def _udid() -> str:
    return f"test:{uuid.uuid4().hex[:12]}"


@pytest.fixture(autouse=True)
async def _redis_env():
    """redis 不可达时 skip；每个测试后在当前事件循环内关闭全局客户端。

    event_bus 的全局客户端绑定创建时的事件循环，pytest-asyncio 每个测试
    换新 loop，用后必须 close_redis() 重置，否则跨测试复用会报 loop 错误。
    """
    probe = aioredis.from_url(
        settings.REDIS_URL, decode_responses=True, socket_connect_timeout=1
    )
    try:
        await probe.ping()
    except Exception:
        pytest.skip("Redis 不可达，跳过设备锁集成测试")
    finally:
        try:
            await probe.aclose()
        except Exception:
            pass
    yield
    await close_redis()


class TestDeviceLock:
    async def test_acquire_then_holder(self):
        udid = _udid()
        ok, holder = await device_lock.acquire(udid, 1, "s-a", "control")
        assert ok is True and holder is None
        holder = await device_lock.holder(udid)
        assert holder == {"owner_user_id": 1, "session_id": "s-a", "kind": "control"}
        await device_lock.release(udid, "s-a")

    async def test_acquire_occupied_returns_holder(self):
        udid = _udid()
        await device_lock.acquire(udid, 1, "s-a", "control")
        ok, holder = await device_lock.acquire(udid, 2, "s-b", "control")
        assert ok is False
        assert holder is not None and holder["owner_user_id"] == 1
        assert holder["session_id"] == "s-a"
        await device_lock.release(udid, "s-a")

    async def test_renew_cas_by_session_id(self):
        udid = _udid()
        await device_lock.acquire(udid, 1, "s-a", "control")
        assert await device_lock.renew(udid, "s-a") is True
        assert await device_lock.renew(udid, "s-wrong") is False
        assert await device_lock.renew(_udid(), "s-a") is False  # 无锁
        await device_lock.release(udid, "s-a")

    async def test_release_cas_by_session_id(self):
        udid = _udid()
        await device_lock.acquire(udid, 1, "s-a", "control")
        assert await device_lock.release(udid, "s-wrong") is False
        assert await device_lock.holder(udid) is not None  # 错 session 不误删
        assert await device_lock.release(udid, "s-a") is True
        assert await device_lock.holder(udid) is None
        assert await device_lock.release(udid, "s-a") is False  # 幂等：已无锁

    async def test_takeover_same_owner_replaces_session(self):
        udid = _udid()
        await device_lock.acquire(udid, 1, "s-a", "control")
        assert await device_lock.takeover(udid, 1, "s-b", "record") is True
        holder = await device_lock.holder(udid)
        assert holder == {"owner_user_id": 1, "session_id": "s-b", "kind": "record"}
        await device_lock.release(udid, "s-b")

    async def test_takeover_other_owner_rejected(self):
        udid = _udid()
        await device_lock.acquire(udid, 1, "s-a", "control")
        assert await device_lock.takeover(udid, 2, "s-b", "control") is False
        holder = await device_lock.holder(udid)
        assert holder is not None and holder["session_id"] == "s-a"
        await device_lock.release(udid, "s-a")

    async def test_takeover_without_lock_rejected(self):
        assert await device_lock.takeover(_udid(), 1, "s-b", "control") is False

    async def test_lock_ttl_is_set(self):
        udid = _udid()
        await device_lock.acquire(udid, 1, "s-a", "control")
        ttl_ms = await get_redis().pttl(f"app:device:lock:{udid}")
        assert 0 < ttl_ms <= 30_000
        await device_lock.release(udid, "s-a")


class TestTicket:
    async def test_issue_and_consume_once(self):
        udid = _udid()
        ticket = await issue_ticket(7, udid, "s-t")
        assert isinstance(ticket, str) and len(ticket) >= 32
        data = await consume_ticket(ticket)
        assert data == {
            "user_id": 7,
            "udid": udid,
            "session_id": "s-t",
            "mode": "control",
        }
        # GETDEL 一次性：二次消费必须失效
        assert await consume_ticket(ticket) is None

    async def test_issue_observe_mode(self):
        """观战票（P4）：mode=observe 随载荷透传给网关"""
        udid = _udid()
        ticket = await issue_ticket(7, udid, "s-ob", mode="observe")
        data = await consume_ticket(ticket)
        assert data is not None and data["mode"] == "observe"

    async def test_consume_invalid_ticket(self):
        assert await consume_ticket("not-a-ticket") is None
        assert await consume_ticket("") is None
