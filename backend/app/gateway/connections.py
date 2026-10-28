"""网关单进程内存连接注册表

四张表全存本进程内存（契约 §9：网关必须单 worker，多 worker 会让注册表脑裂）：
- agent_id → Agent 控制 WS
- session_id → 浏览器控制 WS（含 udid / owner 元信息）
- session_id → Agent 投屏 data WS
- rpc_id → in-flight Future（rpc_request 已发出、等 rpc_response 回填）

摘除一律按连接身份（is 同一对象）匹配：同 agent 二连被拒（close 4409）时，
被拒连接的清理不能误摘在册的旧连接。
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Optional

from app.gateway.frames import rpc_payload


@dataclass
class BrowserSession:
    """浏览器控制 WS 及其会话元信息（ticket 消费结果，契约 §5）"""

    ws: Any
    udid: str
    owner_user_id: int
    session_id: str
    # 会话模式（P4 观战锁）：control=占锁可注入；observe=不占锁只读观看
    # （不续锁、不做逐帧锁校验、入站控制字节一律丢弃）
    mode: str = "control"
    # 网关主动踢断标记（对端断开拆对/锁易主）：正常关闭 release 判定要排除
    kicked: bool = False
    # 续期窗口内是否有活跃帧（契约 §4：有活跃帧才 renew）
    saw_frame: bool = False


@dataclass
class _InflightRpc:
    """一次在途 RPC：记录目标 agent，便于 agent 断开时兜底失败返回"""

    agent_id: int
    future: asyncio.Future


class ConnectionRegistry:
    """连接注册表（纯内存，无锁——单进程单事件循环内操作均为原子）"""

    def __init__(self) -> None:
        self._agents: dict[int, Any] = {}
        self._browsers: dict[str, BrowserSession] = {}
        self._data: dict[str, Any] = {}
        self._rpcs: dict[str, _InflightRpc] = {}

    # ── Agent 控制 WS ──────────────────────────────────────────

    def register_agent(self, agent_id: int, ws: Any) -> bool:
        """False = 该 agent 已有活跃连接（调用方应 close 4409）"""
        if agent_id in self._agents:
            return False
        self._agents[agent_id] = ws
        return True

    def unregister_agent(self, agent_id: int, ws: Any) -> None:
        if self._agents.get(agent_id) is ws:
            del self._agents[agent_id]

    def get_agent(self, agent_id: int) -> Any | None:
        return self._agents.get(agent_id)

    # ── 浏览器控制 WS ──────────────────────────────────────────

    def bind_browser(self, session: BrowserSession) -> bool:
        """False = 同 session_id 已有浏览器连接（一次性 ticket 异常重放）"""
        if session.session_id in self._browsers:
            return False
        self._browsers[session.session_id] = session
        return True

    def unbind_browser(self, session_id: str, ws: Any) -> None:
        cur = self._browsers.get(session_id)
        if cur is not None and cur.ws is ws:
            del self._browsers[session_id]

    def get_browser(self, session_id: str) -> Optional[BrowserSession]:
        return self._browsers.get(session_id)

    def find_browsers_by_udid(
        self, udid: str, *, exclude_session: str | None = None
    ) -> list[BrowserSession]:
        """同 udid 的既有浏览器会话（接管编排用）；量级=在线会话数，线性扫无碍"""
        return [
            s
            for s in self._browsers.values()
            if s.udid == udid and s.session_id != exclude_session
        ]

    # ── Agent 投屏 data WS ─────────────────────────────────────

    def bind_data(self, session_id: str, ws: Any) -> bool:
        """False = 同 session 已有 data 连接"""
        if session_id in self._data:
            return False
        self._data[session_id] = ws
        return True

    def unbind_data(self, session_id: str, ws: Any) -> None:
        if self._data.get(session_id) is ws:
            del self._data[session_id]

    def get_data(self, session_id: str) -> Any | None:
        return self._data.get(session_id)

    # ── in-flight RPC ─────────────────────────────────────────

    def create_rpc(self, rpc_id: str, agent_id: int) -> asyncio.Future:
        """登记一次在途 RPC，返回等待 rpc_response 的 Future"""
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._rpcs[rpc_id] = _InflightRpc(agent_id=agent_id, future=fut)
        return fut

    def resolve_rpc(self, frame: dict[str, Any]) -> bool:
        """rpc_response 帧按 id 路由回等待方；未知/迟到 id 返回 False（丢弃）"""
        entry = self._rpcs.pop(str(frame.get("id")), None)
        if entry is None:
            return False
        if not entry.future.done():
            entry.future.set_result(rpc_payload(frame))
        return True

    def discard_rpc(self, rpc_id: str) -> None:
        self._rpcs.pop(rpc_id, None)

    def fail_agent_rpcs(self, agent_id: int, code: str, message: str) -> int:
        """agent 控制 WS 断开时兜底：其全部在途 RPC 立即失败返回，返回失败个数"""
        count = 0
        stale = [k for k, v in self._rpcs.items() if v.agent_id == agent_id]
        for rpc_id in stale:
            entry = self._rpcs.pop(rpc_id)
            if not entry.future.done():
                entry.future.set_result(
                    {"ok": False, "error": {"code": code, "message": message}}
                )
                count += 1
        return count


# 进程级单例（单 worker 部署形态，见模块 docstring）
registry = ConnectionRegistry()
