"""网关内存连接注册表单测

锁住：
- 同 agent 二连拒绝（register_agent 二次 False），旧连接保留；
- 摘除按连接身份匹配：被拒新连接的清理不误摘在册旧连接；
- browser / data 会话登记与同名拒绝；
- in-flight RPC：rpc_response 按 id 路由、迟到丢弃、discard 后不再命中、
  agent 断开兜底只失败该 agent 的在途 RPC。

纯净：不起 WS 服务，用哨兵对象充当连接（注册表只做身份比较）。
"""

import pytest

from app.gateway.connections import BrowserSession, ConnectionRegistry


class _FakeWs:
    """哨兵连接对象：注册表只按身份（is）比较，不调用其任何方法"""


def _browser(session_id: str = "s-1", udid: str = "3:ABC", ws=None) -> BrowserSession:
    return BrowserSession(
        ws=ws or _FakeWs(), udid=udid, owner_user_id=1, session_id=session_id
    )


# ── Agent 控制 WS ─────────────────────────────────────────────


def test_register_agent_second_conn_rejected():
    reg = ConnectionRegistry()
    ws1, ws2 = _FakeWs(), _FakeWs()
    assert reg.register_agent(3, ws1) is True
    assert reg.register_agent(3, ws2) is False  # 二连拒绝（调用方 close 4409）
    assert reg.get_agent(3) is ws1              # 旧连接保留


def test_unregister_agent_identity_guard():
    reg = ConnectionRegistry()
    ws1, ws2 = _FakeWs(), _FakeWs()
    reg.register_agent(3, ws1)
    reg.unregister_agent(3, ws2)      # 被拒连接的清理：不得误摘旧连接
    assert reg.get_agent(3) is ws1
    reg.unregister_agent(3, ws1)
    assert reg.get_agent(3) is None
    reg.unregister_agent(3, ws1)      # 幂等，不抛


def test_get_agent_missing_returns_none():
    assert ConnectionRegistry().get_agent(99) is None


# ── 浏览器控制 WS ─────────────────────────────────────────────


def test_bind_browser_duplicate_session_rejected():
    reg = ConnectionRegistry()
    first = _browser("s-1")
    assert reg.bind_browser(first) is True
    assert reg.bind_browser(_browser("s-1")) is False
    assert reg.get_browser("s-1") is first


def test_unbind_browser_identity_guard():
    reg = ConnectionRegistry()
    session = _browser("s-1")
    reg.bind_browser(session)
    reg.unbind_browser("s-1", _FakeWs())      # 别的连接不能摘
    assert reg.get_browser("s-1") is session
    reg.unbind_browser("s-1", session.ws)
    assert reg.get_browser("s-1") is None


# ── Agent data WS ─────────────────────────────────────────────


def test_bind_and_unbind_data_ws():
    reg = ConnectionRegistry()
    ws1, ws2 = _FakeWs(), _FakeWs()
    assert reg.bind_data("s-1", ws1) is True
    assert reg.bind_data("s-1", ws2) is False
    assert reg.get_data("s-1") is ws1
    reg.unbind_data("s-1", ws2)               # 身份不符不摘
    assert reg.get_data("s-1") is ws1
    reg.unbind_data("s-1", ws1)
    assert reg.get_data("s-1") is None


# ── in-flight RPC ─────────────────────────────────────────────


async def test_rpc_resolve_roundtrip():
    reg = ConnectionRegistry()
    fut = reg.create_rpc("r-1", agent_id=3)
    assert not fut.done()
    ok = reg.resolve_rpc(
        {"v": 1, "type": "rpc_response", "id": "r-1", "ok": True, "result": {"pong": True}}
    )
    assert ok is True
    assert fut.result() == {"ok": True, "result": {"pong": True}}


async def test_rpc_resolve_unknown_id_returns_false():
    reg = ConnectionRegistry()
    assert reg.resolve_rpc({"id": "r-nope", "ok": True}) is False


async def test_rpc_discard_then_late_response_dropped():
    reg = ConnectionRegistry()
    fut = reg.create_rpc("r-1", agent_id=3)
    reg.discard_rpc("r-1")                    # 超时清理
    assert reg.resolve_rpc({"id": "r-1", "ok": True}) is False  # 迟到响应丢弃
    assert not fut.done()


async def test_rpc_resolve_error_payload_normalized():
    reg = ConnectionRegistry()
    fut = reg.create_rpc("r-1", agent_id=3)
    reg.resolve_rpc({"id": "r-1", "ok": False})
    payload = fut.result()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "internal"  # 缺 error 自动补


async def test_rpc_resolve_after_future_cancelled_no_raise():
    reg = ConnectionRegistry()
    fut = reg.create_rpc("r-1", agent_id=3)
    fut.cancel()
    assert reg.resolve_rpc({"id": "r-1", "ok": True}) is True  # 已 done 只摘表，不抛


async def test_fail_agent_rpcs_only_target_agent():
    reg = ConnectionRegistry()
    fut_a = reg.create_rpc("r-a", agent_id=3)
    fut_b = reg.create_rpc("r-b", agent_id=3)
    fut_other = reg.create_rpc("r-c", agent_id=4)

    count = reg.fail_agent_rpcs(3, code="internal", message="agent 控制连接断开")

    assert count == 2
    for fut in (fut_a, fut_b):
        payload = fut.result()
        assert payload["ok"] is False
        assert payload["error"]["code"] == "internal"
    assert not fut_other.done()               # 别的 agent 不受影响
    # 已摘表：迟到响应不再命中
    assert reg.resolve_rpc({"id": "r-a", "ok": True}) is False
