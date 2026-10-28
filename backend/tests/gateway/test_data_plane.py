"""投屏数据面单测（契约 §3 / §3.1，control_ws）

锁住四件事：
- video 方向 bounded queue 丢帧决策（enqueue_or_drop / VideoPump.offer）：
  队满丢最旧、计数正确、close 后拒收；
- VideoPump.run 泵送：正常抽干、send 失败即停泵、慢消费者不无界堆积；
- 配对 → 双向转字节（data-ws Agent→浏览器；浏览器→Agent 逐帧锁校验）；
- 生命周期触发点（契约 §3.1「不看即停」）：浏览器连上发 start_scrcpy、
  断开 / 心跳超时发 stop_scrcpy。

纯净：不起真 WS 服务，用 FakeWebSocket 驱动端点协程；ticket/lock/send_rpc
全部 monkeypatch，不碰 Redis/DB/agent 连接。
"""

import asyncio
from collections import deque

import pytest

from app.gateway import control_ws
from app.gateway.connections import BrowserSession, ConnectionRegistry
from app.gateway.control_ws import (
    VIDEO_QUEUE_MAXLEN,
    VideoPump,
    agent_data_ws,
    browser_control_ws,
    enqueue_or_drop,
)


# ── FakeWebSocket ─────────────────────────────────────────────


class FakeWebSocket:
    """够用的 WS 替身：脚本化 receive 队列 + 记录 accept/close/发送。

    receive() 依次弹出 _incoming；耗尽后返回一个 disconnect 帧（模拟客户端
    正常断开），除非脚本里显式放了 disconnect。send_bytes 累积到 sent。
    """

    def __init__(self, headers=None, incoming=None):
        self.headers = headers or {}
        self._incoming = list(incoming or [])
        self.sent: list[bytes] = []
        self.accepted_subprotocol = None
        self.close_code = None
        self.close_reason = None
        self.closed = False

    async def accept(self, subprotocol=None):
        self.accepted_subprotocol = subprotocol

    async def close(self, code=1000, reason=None):
        self.closed = True
        self.close_code = code
        self.close_reason = reason

    async def receive(self):
        # 真 WS receive 会 await I/O 让出事件循环；替身也让一拍，好让并发的
        # video 泵协程有机会被调度抽干队列（否则 receive 同步跑完整个循环）。
        await asyncio.sleep(0)
        if self._incoming:
            return self._incoming.pop(0)
        # 脚本耗尽：模拟客户端正常断开
        return {"type": "websocket.disconnect", "code": 1000}

    async def send_bytes(self, data):
        self.sent.append(data)


def _bytes_frame(data: bytes) -> dict:
    return {"type": "websocket.bytes", "bytes": data}


# ── enqueue_or_drop（纯函数丢帧决策） ─────────────────────────


def test_enqueue_under_limit_no_drop():
    q: deque[bytes] = deque()
    for i in range(3):
        assert enqueue_or_drop(q, bytes([i]), maxlen=4) is True
    assert list(q) == [b"\x00", b"\x01", b"\x02"]


def test_enqueue_at_limit_drops_oldest():
    q: deque[bytes] = deque([b"a", b"b", b"c"])
    # 已满（len==maxlen）：丢最旧 a，入新 d
    assert enqueue_or_drop(q, b"d", maxlen=3) is False
    assert list(q) == [b"b", b"c", b"d"]


def test_enqueue_keeps_bounded_under_flood():
    q: deque[bytes] = deque()
    drops = 0
    for i in range(100):
        if not enqueue_or_drop(q, bytes([i % 256]), maxlen=8):
            drops += 1
    assert len(q) == 8  # 恒不超上限
    assert drops == 92  # 100 - 8


# ── VideoPump.offer（丢帧计数 / close 门禁） ───────────────────


def test_pump_offer_counts_drops():
    pump = VideoPump(send=None, maxlen=2)
    assert pump.offer(b"a") is True
    assert pump.offer(b"b") is True
    assert pump.offer(b"c") is False  # 满，丢最旧
    assert pump.offer(b"d") is False
    assert pump.dropped == 2


def test_pump_offer_after_close_rejected():
    pump = VideoPump(send=None, maxlen=4)
    pump.close()
    assert pump.offer(b"a") is False
    assert pump.dropped == 0  # close 后拒收不计丢帧


def test_pump_default_maxlen_from_constant():
    pump = VideoPump(send=None)
    assert pump._maxlen == VIDEO_QUEUE_MAXLEN


# ── VideoPump.run（泵送 / send 失败即停 / 慢消费不堆积） ───────


async def test_pump_run_drains_all_frames():
    sent: list[bytes] = []

    async def send(data):
        sent.append(data)

    pump = VideoPump(send=send, maxlen=8)
    for i in range(5):
        pump.offer(bytes([i]))
    task = asyncio.create_task(pump.run())
    await asyncio.sleep(0)  # 让泵抽干
    await asyncio.sleep(0)
    pump.close()
    await task
    assert sent == [bytes([i]) for i in range(5)]


async def test_pump_run_stops_on_send_error():
    async def send(_data):
        raise ConnectionResetError("browser gone")

    pump = VideoPump(send=send, maxlen=8)
    pump.offer(b"x")
    # send 抛错 → run 应自然返回（不无限循环），wait_for 兜底防挂死
    await asyncio.wait_for(pump.run(), timeout=1.0)


async def test_pump_slow_consumer_drops_not_grows():
    """慢消费者：send 卡住时 offer 继续丢帧，队列恒不超上限（不 OOM）。"""
    release = asyncio.Event()

    async def slow_send(_data):
        await release.wait()  # 一直卡在第一帧

    pump = VideoPump(send=slow_send, maxlen=4)
    task = asyncio.create_task(pump.run())
    await asyncio.sleep(0)  # 泵取第一帧后卡在 slow_send
    for i in range(50):
        pump.offer(bytes([i % 256]))
    assert len(pump._queue) <= pump._maxlen  # 恒不超上限
    assert pump.dropped > 0
    release.set()
    pump.close()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


# ── 生命周期触发点（契约 §3.1「不看即停」） ───────────────────


class _RpcRecorder:
    """记录网关向 agent 发的每次 RPC（cmd, params），供断言触发点。"""

    def __init__(self):
        self.calls: list[tuple[int, str, dict]] = []

    async def __call__(self, agent_id, cmd, params=None, **_kw):
        self.calls.append((agent_id, cmd, params or {}))
        return {"ok": True, "result": {}}

    def cmds(self):
        return [c[1] for c in self.calls]


@pytest.fixture
def data_plane_env(monkeypatch):
    """隔离环境：全新 registry + monkeypatch ticket/lock/send_rpc。"""
    reg = ConnectionRegistry()
    monkeypatch.setattr(control_ws, "registry", reg)

    async def fake_consume_ticket(_ticket):
        return {"user_id": 1, "udid": "3:ABC", "session_id": "s-1"}

    class FakeLock:
        async def holder(self, _udid):
            return {"session_id": "s-1"}

        async def renew(self, _udid, _sid):
            return True

        async def release(self, _udid, _sid):
            return True

    monkeypatch.setattr(control_ws, "_load_consume_ticket", lambda: fake_consume_ticket)
    monkeypatch.setattr(control_ws, "_load_device_lock", lambda: FakeLock())
    # 审计收尾走 async_session_maker，正常关闭路径会碰它——直接短路成 no-op
    monkeypatch.setattr(
        control_ws,
        "_kick_peer_data_ws",
        control_ws._kick_peer_data_ws,  # 保留真实拆对
    )
    rpc = _RpcRecorder()
    monkeypatch.setattr(control_ws, "send_rpc", rpc)
    return reg, rpc


async def _run_browser_ws(ws):
    """驱动 browser_control_ws；审计收尾用真实 DB 会被短路（正常关闭分支
    里 crud 落库失败被吞），此处不落 DB——把它整体包超时防挂死。"""
    await asyncio.wait_for(browser_control_ws(ws, "3:ABC"), timeout=2.0)


async def test_browser_connect_triggers_start_scrcpy(data_plane_env, monkeypatch):
    reg, rpc = data_plane_env
    # 审计收尾（正常关闭分支）会 import crud + async_session_maker：让 release
    # 分支里的落库吞异常即可，不需真库；这里直接断 close_code 非正常关闭以绕开。
    ws = FakeWebSocket(
        headers={"sec-websocket-protocol": "ticket.abc"},
        incoming=[{"type": "websocket.disconnect", "code": 1006}],  # 异常断开
    )
    await _run_browser_ws(ws)
    assert "start_scrcpy" in rpc.cmds()
    # 触发点顺序：start 在前，stop 在后
    assert rpc.cmds().index("start_scrcpy") < rpc.cmds().index("stop_scrcpy")
    start_call = next(c for c in rpc.calls if c[1] == "start_scrcpy")
    assert start_call[0] == 3  # agent_id 来自 udid 拆解
    assert start_call[2] == {"serial": "ABC", "session_id": "s-1"}


async def test_browser_disconnect_triggers_stop_scrcpy(data_plane_env):
    reg, rpc = data_plane_env
    ws = FakeWebSocket(
        headers={"sec-websocket-protocol": "ticket.abc"},
        incoming=[{"type": "websocket.disconnect", "code": 1006}],
    )
    await _run_browser_ws(ws)
    stop_calls = [c for c in rpc.calls if c[1] == "stop_scrcpy"]
    assert len(stop_calls) == 1
    assert stop_calls[0][0] == 3
    assert stop_calls[0][2] == {"session_id": "s-1"}
    # 拆连接后 browser 已摘表
    assert reg.get_browser("s-1") is None


async def test_browser_idle_timeout_triggers_stop_scrcpy(
    data_plane_env, monkeypatch
):
    """心跳超时：BROWSER_IDLE_TIMEOUT_S 内无帧 → 踢断 + stop_scrcpy。"""
    reg, rpc = data_plane_env
    # 把超时压到极小，让 receive() 的 wait_for 立刻超时（脚本 receive 永不返回）
    monkeypatch.setattr(control_ws, "BROWSER_IDLE_TIMEOUT_S", 0.05)

    never = asyncio.Event()

    class HangingWs(FakeWebSocket):
        async def receive(self):
            await never.wait()  # 永不返回 → 触发 idle 超时

    ws = HangingWs(headers={"sec-websocket-protocol": "ticket.abc"})
    await _run_browser_ws(ws)
    assert "stop_scrcpy" in rpc.cmds()
    assert ws.closed is True
    assert ws.close_code == 4408  # 心跳超时 close code


# ── 配对 + 双向转字节 ─────────────────────────────────────────


async def test_data_ws_pairs_and_forwards_video_to_browser(
    data_plane_env, monkeypatch
):
    """Agent data-ws → 浏览器方向：配对成功后视频帧经泵送达浏览器。"""
    reg, _rpc = data_plane_env

    # 先登记一个等待配对的浏览器会话
    browser_ws = FakeWebSocket()
    reg.bind_browser(
        BrowserSession(ws=browser_ws, udid="3:ABC", owner_user_id=1, session_id="s-1")
    )

    async def fake_resolve(_token):
        return (3, "fp")  # agent_id=3 与 udid 前缀一致

    monkeypatch.setattr(control_ws, "resolve_agent_by_token", fake_resolve)

    data_ws = FakeWebSocket(
        headers={"X-Agent-Token": "tok"},
        incoming=[
            _bytes_frame(b"video-1"),
            _bytes_frame(b"video-2"),
            {"type": "websocket.disconnect", "code": 1000},
        ],
    )
    await asyncio.wait_for(agent_data_ws(data_ws, session_id="s-1"), timeout=2.0)

    # 泵送保序、不重复、不越权（子集：断开时未抽干的尾帧允许丢，但已送的
    # 必是按序前缀）——本 FakeWS 调度下两帧均达，这里断言严格相等。
    assert browser_ws.sent == [b"video-1", b"video-2"]
    assert browser_ws.sent == [b"video-1", b"video-2"][: len(browser_ws.sent)]
    # data-ws 断开后拆对：浏览器被踢（close 4410），data 表已摘
    assert browser_ws.closed is True
    assert browser_ws.close_code == 4410
    assert reg.get_data("s-1") is None


async def test_data_ws_rejected_when_agent_mismatch(data_plane_env, monkeypatch):
    """来源 agent 与会话设备所属 agent 不符 → close 4403，不配对。"""
    reg, _rpc = data_plane_env
    browser_ws = FakeWebSocket()
    reg.bind_browser(
        BrowserSession(ws=browser_ws, udid="3:ABC", owner_user_id=1, session_id="s-1")
    )

    async def fake_resolve(_token):
        return (9, "fp")  # agent 9 ≠ udid 前缀 3

    monkeypatch.setattr(control_ws, "resolve_agent_by_token", fake_resolve)
    data_ws = FakeWebSocket(headers={"X-Agent-Token": "tok"})
    await asyncio.wait_for(agent_data_ws(data_ws, session_id="s-1"), timeout=2.0)

    assert data_ws.close_code == 4403
    assert reg.get_data("s-1") is None  # 未配对


async def test_data_ws_no_waiting_browser_closes_4404(data_plane_env, monkeypatch):
    reg, _rpc = data_plane_env

    async def fake_resolve(_token):
        return (3, "fp")

    monkeypatch.setattr(control_ws, "resolve_agent_by_token", fake_resolve)
    data_ws = FakeWebSocket(headers={"X-Agent-Token": "tok"})
    await asyncio.wait_for(agent_data_ws(data_ws, session_id="nope"), timeout=2.0)
    assert data_ws.close_code == 4404


# ── 观战会话（P4 观战锁：ticket.mode=observe） ─────────────────


def _use_observe_ticket(monkeypatch):
    """把 consume_ticket 换成观战票（mode=observe，session=s-ob）。"""

    async def fake_consume(_ticket):
        return {"user_id": 9, "udid": "3:ABC", "session_id": "s-ob", "mode": "observe"}

    monkeypatch.setattr(control_ws, "_load_consume_ticket", lambda: fake_consume)


async def test_observe_drops_control_bytes_and_never_touches_lock(
    data_plane_env, monkeypatch
):
    """观战三铁律：入站控制字节丢弃（只读服务端强制）、不做逐帧锁校验
    （锁属 exec 也不 4403）、不续期不释放锁。同时观战照常拉起/停止推流。"""
    reg, rpc = data_plane_env
    _use_observe_ticket(monkeypatch)

    class ForeignLock:
        """锁属于别人（自动化 exec 正持有）——观战对锁零接触"""

        async def holder(self, _udid):
            return {"session_id": "exec-someone-else"}

        async def renew(self, _udid, _sid):
            raise AssertionError("观战会话不得续锁")

        async def release(self, _udid, _sid):
            raise AssertionError("观战会话不得释放锁")

    monkeypatch.setattr(control_ws, "_load_device_lock", lambda: ForeignLock())

    peer = FakeWebSocket()
    reg.bind_data("s-ob", peer)  # 预配对 data 对端，验证控制字节不被转发
    ws = FakeWebSocket(
        headers={"sec-websocket-protocol": "ticket.abc"},
        incoming=[
            _bytes_frame(b"\x02fake-touch"),
            {"type": "websocket.disconnect", "code": 1000},  # 正常关闭走 release 分支
        ],
    )
    await _run_browser_ws(ws)

    assert peer.sent == []  # 控制字节被丢弃，未到设备
    assert ws.close_code is None  # 未被 4403（锁不属于它也无妨）
    assert "start_scrcpy" in rpc.cmds() and "stop_scrcpy" in rpc.cmds()


async def test_observe_rejected_when_stream_busy(data_plane_env, monkeypatch):
    """单流拓扑：同设备已有活跃浏览器会话（正主在看/在控）→ 观战 4423 被拒，
    绝不抢起 scrcpy 踢掉正主画面。"""
    reg, rpc = data_plane_env
    _use_observe_ticket(monkeypatch)
    owner_ws = FakeWebSocket()
    reg.bind_browser(
        BrowserSession(ws=owner_ws, udid="3:ABC", owner_user_id=1, session_id="s-owner")
    )

    ws = FakeWebSocket(headers={"sec-websocket-protocol": "ticket.abc"})
    await _run_browser_ws(ws)

    assert ws.close_code == 4423
    assert "start_scrcpy" not in rpc.cmds()
    assert owner_ws.closed is False  # 正主毫发无损
    assert reg.get_browser("s-owner") is not None


async def test_control_takeover_kicks_observer(data_plane_env):
    """操控优先于观战：控制连接经 takeover 踢掉在座观战者（4410）。"""
    reg, rpc = data_plane_env
    observer_ws = FakeWebSocket()
    reg.bind_browser(
        BrowserSession(
            ws=observer_ws,
            udid="3:ABC",
            owner_user_id=9,
            session_id="s-ob",
            mode="observe",
        )
    )

    ws = FakeWebSocket(
        headers={"sec-websocket-protocol": "ticket.abc"},
        incoming=[{"type": "websocket.disconnect", "code": 1006}],
    )
    await _run_browser_ws(ws)  # 默认 fixture 票据 = control 模式 s-1

    assert observer_ws.close_code == 4410  # 观战者被接管踢断
    assert reg.get_browser("s-ob") is None
    # 观战者的 scrcpy 会话也被停掉后，新控制会话再拉起自己的
    stop_sids = [c[2].get("session_id") for c in rpc.calls if c[1] == "stop_scrcpy"]
    assert "s-ob" in stop_sids


async def test_observe_takes_over_own_stale_session(data_plane_env, monkeypatch):
    """同用户残留会话（如被 exec 接管后将死的控制会话）不挡观战——照拆再开流；
    否则「转观战」永远撞 4423。"""
    reg, rpc = data_plane_env
    _use_observe_ticket(monkeypatch)  # 观战者 user_id=9
    stale_ws = FakeWebSocket()
    reg.bind_browser(
        BrowserSession(ws=stale_ws, udid="3:ABC", owner_user_id=9, session_id="s-old")
    )

    ws = FakeWebSocket(
        headers={"sec-websocket-protocol": "ticket.abc"},
        incoming=[{"type": "websocket.disconnect", "code": 1006}],
    )
    await _run_browser_ws(ws)

    assert stale_ws.close_code == 4410  # 自己的残留被拆
    assert ws.close_code != 4423
    assert "start_scrcpy" in rpc.cmds()
