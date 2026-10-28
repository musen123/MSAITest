"""Redis 设备锁（backend-core 实现，网关只读复用）

key   app:device:lock:{udid}
value JSON {"owner_user_id":1,"session_id":"s-uuid","kind":"control|record|replay"}
TTL   30s（持有方续期；断连不续期靠 TTL 自然过期）

语义（契约 §4）：
  - acquire   SET NX PX，失败返回当前持有者信息
  - renew/release  Lua CAS——cjson 解析 value，session_id 匹配才 PEXPIRE/DEL
  - takeover  Lua CAS——owner_user_id 匹配即整体替换 value 并重置 TTL（同用户换标签页）
"""

import json
from typing import Optional

from app.ai_core.runtime.event_bus import get_redis

LOCK_TTL_MS = 30_000

# session_id 匹配才续期
_RENEW_LUA = """
local v = redis.call('GET', KEYS[1])
if not v then return 0 end
local ok, data = pcall(cjson.decode, v)
if not ok or type(data) ~= 'table' then return 0 end
if tostring(data.session_id) ~= ARGV[1] then return 0 end
return redis.call('PEXPIRE', KEYS[1], ARGV[2])
"""

# session_id 匹配才删除
_RELEASE_LUA = """
local v = redis.call('GET', KEYS[1])
if not v then return 0 end
local ok, data = pcall(cjson.decode, v)
if not ok or type(data) ~= 'table' then return 0 end
if tostring(data.session_id) ~= ARGV[1] then return 0 end
return redis.call('DEL', KEYS[1])
"""

# owner_user_id 匹配即整体替换 value 并重置 TTL
_TAKEOVER_LUA = """
local v = redis.call('GET', KEYS[1])
if not v then return 0 end
local ok, data = pcall(cjson.decode, v)
if not ok or type(data) ~= 'table' then return 0 end
if tostring(data.owner_user_id) ~= ARGV[1] then return 0 end
redis.call('SET', KEYS[1], ARGV[2], 'PX', ARGV[3])
return 1
"""


def _lock_key(udid: str) -> str:
    return f"app:device:lock:{udid}"


def _lock_value(owner_user_id: int, session_id: str, kind: str) -> str:
    return json.dumps(
        {"owner_user_id": owner_user_id, "session_id": session_id, "kind": kind},
        ensure_ascii=False,
    )


class DeviceLock:
    """设备锁操作集合（无状态，Redis 为唯一事实来源）"""

    async def acquire(
        self, udid: str, owner_user_id: int, session_id: str, kind: str
    ) -> tuple[bool, Optional[dict]]:
        """抢锁。成功 (True, None)；被占 (False, 持有者 dict)。

        SET NX 失败到 GET 之间锁可能刚好过期，此时重试一轮；两轮都竞不到
        且读不到持有者（极端竞争）返回 (False, None)，调用方按被占处理。
        """
        redis = get_redis()
        key = _lock_key(udid)
        value = _lock_value(owner_user_id, session_id, kind)
        for _ in range(2):
            if await redis.set(key, value, nx=True, px=LOCK_TTL_MS):
                return True, None
            holder = await self.holder(udid)
            if holder is not None:
                return False, holder
        return False, None

    async def renew(self, udid: str, session_id: str) -> bool:
        """续期（session_id 匹配才 PEXPIRE）。"""
        result = await get_redis().eval(_RENEW_LUA, 1, _lock_key(udid), session_id, LOCK_TTL_MS)
        return bool(result)

    async def release(self, udid: str, session_id: str) -> bool:
        """释放（session_id 匹配才 DEL）。"""
        result = await get_redis().eval(_RELEASE_LUA, 1, _lock_key(udid), session_id)
        return bool(result)

    async def takeover(
        self, udid: str, owner_user_id: int, new_session_id: str, kind: str
    ) -> bool:
        """同用户接管：owner_user_id 匹配即替换整个 value 并重置 TTL。"""
        new_value = _lock_value(owner_user_id, new_session_id, kind)
        result = await get_redis().eval(
            _TAKEOVER_LUA, 1, _lock_key(udid), str(owner_user_id), new_value, LOCK_TTL_MS
        )
        return bool(result)

    async def holder(self, udid: str) -> Optional[dict]:
        """读当前持有者信息，无锁返回 None。"""
        raw = await get_redis().get(_lock_key(udid))
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return None
        return data if isinstance(data, dict) else None


device_lock = DeviceLock()
