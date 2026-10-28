"""投屏数据面：浏览器控制 WS + Agent data WS（契约 §3）

浏览器经 Sec-WebSocket-Protocol: ticket.<t> 携带一次性 ticket（网关原样
回选该子协议完成握手）→ consume_ticket 校验 → 登记 browser 会话 → 经
控制帧向 Agent 发 start_scrcpy → Agent 出站另连 data-ws 配对 → 二进制帧
原样互转。

方向性规则（契约 §3/§4）：
- 浏览器 → Agent 逐帧校验锁 holder.session_id == 连接 session_id
  （holder 结果缓存 2s），不符 close 4403；Agent → 浏览器方向不校验。
- 有活跃帧时每 10s renew 锁；任一端断开只拆对+通知对端，显式 release
  仅在浏览器正常关闭（close 1000/1001 且非网关踢断）时做，其余靠锁
  TTL 自然过期。

观战会话（ticket.mode=observe，P4 观战锁）：不占锁只读观看——不跑续期
任务（永不 4403）、入站控制字节一律丢弃（服务端强制只读）、keepalive/
4408 不看即停照旧。单流拓扑约束：同设备已有活跃浏览器会话时观战被拒
（close 4423），反向操控连接会经 takeover 踢掉在座观战者（4410）。

生命周期（契约 §3.1「不看即停」）：
- 浏览器 control WS 是唯一「观看」信号——连上即向 Agent 发 start_scrcpy；
  断开 / 心跳超时（BROWSER_IDLE_TIMEOUT_S 内无任何入站帧）即立即向
  Agent 发 stop_scrcpy，绝不让无人观看的 scrcpy 空跑烧本地上行带宽。

video 方向背压（S1 结论 + 方案 §2.1）：Agent → 浏览器方向经 bounded
queue 泵送——浏览器慢时在网关侧丢最旧帧（H264 靠后续关键帧自愈）而非
无界堆积 OOM，并记丢帧计数。控制帧（浏览器 → Agent）方向不丢，量小。
"""

import asyncio
import logging
import time
from collections import deque
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.gateway.agent_ws import (
    AgentNotConnectedError,
    RpcTimeoutError,
    resolve_agent_by_token,
    send_rpc,
)
from app.gateway.connections import BrowserSession, registry

logger = logging.getLogger(__name__)

router = APIRouter()

TICKET_SUBPROTOCOL_PREFIX = "ticket."
# 逐帧锁校验的 holder 结果缓存时长（性能，契约允许 2s 窗口）
HOLDER_CACHE_TTL_S = 2.0
# 锁续期节拍（契约 §4）
LOCK_RENEW_INTERVAL_S = 10
# 浏览器主动正常关闭的 close code（此时才显式 release 锁）
_NORMAL_CLOSE_CODES = (1000, 1001)
# 浏览器 control WS 心跳超时（契约 §3.1）：此时长内无任何入站帧即视为
# 「不再观看」→ 拆连接触发 stop_scrcpy。浏览器空闲时应发文本 keepalive。
BROWSER_IDLE_TIMEOUT_S = 30.0
# video 方向 bounded queue 深度（Agent → 浏览器）：浏览器慢时超过即丢最旧
# 帧（S1 结论：H264 靠后续关键帧自愈，无界堆积会 OOM）。约 1s@15fps 缓冲。
VIDEO_QUEUE_MAXLEN = 16


# ── 纯函数（可单测） ───────────────────────────────────────────


def pick_ticket_subprotocol(header_value: str | None) -> str | None:
    """从 Sec-WebSocket-Protocol 头挑出 ticket.<t> 子协议（原样返回用于回选）"""
    for part in (header_value or "").split(","):
        proto = part.strip()
        if proto.startswith(TICKET_SUBPROTOCOL_PREFIX) and len(proto) > len(
            TICKET_SUBPROTOCOL_PREFIX
        ):
            return proto
    return None


def split_udid(udid: str) -> tuple[int, str] | None:
    """udid = "{agent_id}:{serial}"（契约 §7），拆出所属 agent 与设备序列号"""
    head, sep, serial = udid.partition(":")
    if not sep or not serial or not head.isdigit():
        return None
    return int(head), serial


def enqueue_or_drop(
    queue: "deque[bytes]", frame: bytes, maxlen: int
) -> bool:
    """video 方向 bounded queue 入队决策（纯函数，可单测）。

    队列已满（浏览器消费不过来）时丢**最旧**帧再入新帧——H264 靠后续
    关键帧自愈，丢旧帧比丢新帧交互延迟更低（S1 结论 + 方案 §2.1）。
    返回 True=正常入队；False=发生了丢帧（调用方据此累加丢帧计数）。
    """
    if len(queue) >= maxlen:
        queue.popleft()  # 丢最旧
        queue.append(frame)
        return False
    queue.append(frame)
    return True


# ── video 方向 bounded queue 泵 ────────────────────────────────


class VideoPump:
    """Agent → 浏览器 video 帧泵（bounded queue + 丢帧，S1 结论 / 方案 §2.1）。

    data-ws 接收循环只调 offer()（O(1)、绝不阻塞）；真正的 send_bytes 在
    独立 pump 协程里做——浏览器慢只会让 pump 停在 send 上、队列堆到上限
    后丢最旧帧，绝不反压 data-ws 接收侧、绝不在网关无界堆积。

    offer() 是同步非阻塞的（deque + Event），可脱离事件循环单测入队/丢帧
    决策；run() 是协程，需在事件循环内跑。
    """

    def __init__(
        self, send: Any, maxlen: int = VIDEO_QUEUE_MAXLEN, session_id: str = ""
    ) -> None:
        self._send = send  # awaitable send_bytes(data)
        self._maxlen = maxlen
        self._session_id = session_id
        self._queue: "deque[bytes]" = deque()
        self._wake = asyncio.Event()
        self._closed = False
        self.dropped = 0  # 累计丢帧数（观测 / 单测断言）

    def offer(self, frame: bytes) -> bool:
        """入队一帧（非阻塞）。队满丢最旧并计数。返回 True=未丢帧。"""
        if self._closed:
            return False
        ok = enqueue_or_drop(self._queue, frame, self._maxlen)
        if not ok:
            self.dropped += 1
        self._wake.set()
        return ok

    def close(self) -> None:
        """结束泵：唤醒 run() 让它自然退出。"""
        self._closed = True
        self._wake.set()

    async def run(self) -> None:
        """抽干队列并逐帧 send；send 失败即整体退出（对端已断）。"""
        try:
            while True:
                if not self._queue:
                    if self._closed:
                        return
                    self._wake.clear()
                    # clear 后再看一眼队列，避开 offer 与 clear 的竞态窗口
                    if not self._queue and not self._closed:
                        await self._wake.wait()
                    continue
                frame = self._queue.popleft()
                try:
                    await self._send(frame)
                except Exception:
                    # 浏览器 send 失败（断开/背压异常）：停泵，交由上层拆对
                    logger.debug(
                        "video 泵 send 失败，停泵 session=%s", self._session_id
                    )
                    return
        except asyncio.CancelledError:
            raise


# ── backend-core 锁 / ticket 模块（并行开发，懒加载） ──────────


def _load_device_lock() -> Any | None:
    """Redis 设备锁模块（契约 §4，backend-core 实现，网关只做校验+续期+释放）"""
    try:
        from app.services.app_device.lock import device_lock

        return device_lock
    except ImportError:
        return None


def _load_consume_ticket() -> Any | None:
    """一次性 ticket 消费（契约 §5：GETDEL；返回 {user_id, udid, session_id}）"""
    try:
        # TODO(P1 集成): 待 app.services.app_device.ticket 落地后联调
        from app.services.app_device.ticket import consume_ticket

        return consume_ticket
    except ImportError:
        return None


# ── 浏览器控制 WS ──────────────────────────────────────────────


@router.websocket("/api/v1/app/devices/{udid}/control/ws")
async def browser_control_ws(websocket: WebSocket, udid: str) -> None:
    """浏览器端投屏/控制连接（契约 §3）"""
    ticket_proto = pick_ticket_subprotocol(
        websocket.headers.get("sec-websocket-protocol")
    )
    if ticket_proto is None:
        await websocket.accept()
        await websocket.close(code=4401)
        return
    # 契约 §3：网关须原样回选 ticket.<t> 子协议完成握手
    await websocket.accept(subprotocol=ticket_proto)

    consume_ticket = _load_consume_ticket()
    device_lock = _load_device_lock()
    if consume_ticket is None or device_lock is None:
        logger.error("app_device 锁/ticket 模块未就绪，无法建立浏览器控制连接")
        await websocket.close(code=1011)
        return

    # 一次性 ticket 校验 + udid 与路径一致性（契约 §5）
    try:
        info = await consume_ticket(ticket_proto[len(TICKET_SUBPROTOCOL_PREFIX) :])
    except Exception:
        logger.exception("consume_ticket 失败 udid=%s", udid)
        await websocket.close(code=1011)
        return
    if not info:
        await websocket.close(code=4401)
        return
    if info.get("udid") != udid:
        await websocket.close(code=4403)
        return
    parsed = split_udid(udid)
    if parsed is None:
        await websocket.close(code=4403)
        return
    agent_id, serial = parsed

    session = BrowserSession(
        ws=websocket,
        udid=udid,
        owner_user_id=int(info["user_id"]),
        session_id=str(info["session_id"]),
        mode=str(info.get("mode") or "control"),
    )
    if not registry.bind_browser(session):
        # 同 session 已有浏览器连接（ticket 一次性，理论不可达，防御）
        await websocket.close(code=4409)
        return

    logger.info(
        "浏览器控制 WS 建立 udid=%s session=%s user=%s mode=%s",
        udid,
        session.session_id,
        session.owner_user_id,
        session.mode,
    )
    client_close_code: int | None = None
    # 观战会话不占锁 → 不跑续期任务（也就永不因续期失败 4403）
    renew_task = (
        asyncio.create_task(_renew_lock_loop(session, device_lock))
        if session.mode == "control"
        else None
    )
    try:
        if session.mode == "observe":
            # 观战：不夺他人的流。同设备已有**他人**活跃浏览器会话时拒绝——
            # 单流拓扑（一次一台）下抢起 scrcpy 会踢掉正主的画面；
            # 自己的残留会话（如刚被 exec takeover 将死的控制会话）照拆，
            # 否则「转观战」永远撞 4423（同用户接管哲学与控制路径一致）。
            others = registry.find_browsers_by_udid(
                udid, exclude_session=session.session_id
            )
            if any(s.owner_user_id != session.owner_user_id for s in others):
                session.kicked = True
                await websocket.close(code=4423, reason="设备画面已被占用，稍后再试")
                return
            if others:
                await _takeover_stale_sessions(agent_id, session)
        else:
            # 接管编排：先拆同设备旧会话（含观战者——操控优先级高于观战），
            # 避免 Agent 一次一台 gate 回 busy
            await _takeover_stale_sessions(agent_id, session)
        await _kick_off_scrcpy(agent_id, serial, session.session_id)
        client_close_code = await _browser_frame_loop(session, device_lock)
    except WebSocketDisconnect as exc:
        client_close_code = exc.code
    except Exception:
        logger.exception("浏览器控制 WS 异常退出 session=%s", session.session_id)
    finally:
        if renew_task is not None:
            renew_task.cancel()
        registry.unbind_browser(session.session_id, websocket)
        # 契约 §3.1「不看即停」：浏览器观看信号一断（断开/心跳超时/踢断），
        # 立即让 Agent 停 scrcpy，绝不留无人观看的推流空跑烧本地上行带宽。
        await _stop_scrcpy(agent_id, session.session_id)
        await _kick_peer_data_ws(session.session_id)
        # 显式 release 仅在浏览器正常关闭且非网关踢断时做，其余靠锁 TTL 过期
        # （契约 §3）；观战不占锁无从释放，但正常关闭同样补审计 ended_at。
        if not session.kicked and client_close_code in _NORMAL_CLOSE_CODES:
            if session.mode == "control":
                try:
                    await device_lock.release(udid, session.session_id)
                except Exception:
                    logger.exception("释放设备锁失败 udid=%s", udid)
            # 审计收尾：正常关闭补 ended_at（其余场景留空，锁靠 TTL 过期）
            try:
                from app.crud.app_device.control_session import (
                    crud_app_control_session,
                )
                from app.db.session import async_session_maker

                async with async_session_maker() as db:
                    await crud_app_control_session.end(
                        db, session_id=session.session_id, end_reason="ws_closed"
                    )
            except Exception:
                logger.exception(
                    "控制会话审计收尾失败 session=%s", session.session_id
                )
        logger.info(
            "浏览器控制 WS 断开 udid=%s session=%s mode=%s code=%s",
            udid,
            session.session_id,
            session.mode,
            client_close_code,
        )


async def _takeover_stale_sessions(agent_id: int, session: BrowserSession) -> None:
    """接管编排（契约 §2.3/§3.1）：同 udid 已有旧浏览器会话时先拆旧再起新。

    场景：同用户换标签页/刷新残留/前端重复挂载——不先停旧，Agent 的
    一次一台 gate 会对新会话回 busy。踢旧浏览器（4410）→ 停旧 scrcpy →
    拆旧 data-WS；旧连接 handler 的 finally 会再走一遍清理，均幂等。
    """
    for stale in registry.find_browsers_by_udid(
        session.udid, exclude_session=session.session_id
    ):
        logger.info(
            "takeover：拆同设备旧会话 old=%s new=%s udid=%s",
            stale.session_id,
            session.session_id,
            session.udid,
        )
        try:
            await stale.ws.close(code=4410)
        except Exception:
            pass
        registry.unbind_browser(stale.session_id, stale.ws)
        await _stop_scrcpy(agent_id, stale.session_id)
        await _kick_peer_data_ws(stale.session_id)


async def _kick_off_scrcpy(agent_id: int, serial: str, session_id: str) -> None:
    """经控制帧触发 Agent 建数据面。

    busy 兜底：Agent 侧仍有活跃会话（网关重启后失忆/浏览器崩溃未清理的
    孤儿）时，error 会带 active_session_id——停掉它重试一次。
    """
    for attempt in (1, 2):
        try:
            resp = await send_rpc(
                agent_id, "start_scrcpy", {"serial": serial, "session_id": session_id}
            )
        except AgentNotConnectedError:
            logger.warning(
                "start_scrcpy 未发出：agent=%s 不在线 session=%s", agent_id, session_id
            )
            return
        except RpcTimeoutError:
            logger.warning("start_scrcpy 超时 agent=%s session=%s", agent_id, session_id)
            return
        if resp.get("ok"):
            return
        error = resp.get("error") or {}
        stale_sid = error.get("active_session_id")
        if attempt == 1 and error.get("code") == "busy" and stale_sid:
            logger.info(
                "start_scrcpy busy，停 Agent 侧孤儿会话后重试 stale=%s new=%s",
                stale_sid,
                session_id,
            )
            await _stop_scrcpy(agent_id, str(stale_sid))
            await _kick_peer_data_ws(str(stale_sid))
            continue
        logger.warning(
            "start_scrcpy 失败 agent=%s session=%s error=%s",
            agent_id,
            session_id,
            error,
        )
        return


async def _stop_scrcpy(agent_id: int, session_id: str) -> None:
    """浏览器观看信号断开 → 通知 Agent 优雅停对应 scrcpy 会话（契约 §3.1）。

    best-effort：agent 已离线 / 超时都吞掉——设备侧 scrcpy 靠 socket 断裂
    的 broken pipe 也会自行 release 编码器（S1 铁律），stop RPC 只是显式
    快速收口；绝不因为停流失败拖住浏览器 WS 的清理。
    """
    try:
        resp = await send_rpc(agent_id, "stop_scrcpy", {"session_id": session_id})
    except AgentNotConnectedError:
        logger.info(
            "stop_scrcpy 略过：agent=%s 已离线 session=%s", agent_id, session_id
        )
        return
    except RpcTimeoutError:
        logger.warning("stop_scrcpy 超时 agent=%s session=%s", agent_id, session_id)
        return
    except Exception:
        logger.exception(
            "stop_scrcpy 异常 agent=%s session=%s", agent_id, session_id
        )
        return
    if not resp.get("ok"):
        logger.info(
            "stop_scrcpy 非 ok（会话可能已停）agent=%s session=%s error=%s",
            agent_id,
            session_id,
            resp.get("error"),
        )


async def _browser_frame_loop(
    session: BrowserSession, device_lock: Any
) -> int | None:
    """浏览器 → Agent 帧循环：逐帧锁校验后转发；返回客户端 close code。

    心跳超时（契约 §3.1）：BROWSER_IDLE_TIMEOUT_S 内无任何入站帧即视为
    浏览器不再观看 → 踢断（触发上层 stop_scrcpy），不空等挂死的连接。
    """
    websocket = session.ws
    holder_cache: dict[str, Any] = {"expires": 0.0, "sid": None}
    while True:
        try:
            message = await asyncio.wait_for(
                websocket.receive(), timeout=BROWSER_IDLE_TIMEOUT_S
            )
        except asyncio.TimeoutError:
            logger.info(
                "浏览器控制 WS 心跳超时（%ss 无帧），断开 session=%s",
                BROWSER_IDLE_TIMEOUT_S,
                session.session_id,
            )
            session.kicked = True
            await _safe_close(websocket, code=4408)
            return None
        if message["type"] == "websocket.disconnect":
            return message.get("code")
        data = message.get("bytes")
        if data is None:
            # 数据面只走二进制帧；文本帧＝keepalive：刷新心跳窗口 + 标记活跃
            # （纯观看无二进制帧，靠 keepalive 驱动锁续期，否则锁 30s 后过期）。
            session.saw_frame = True
            continue
        session.saw_frame = True
        if session.mode == "observe":
            # 观战强制只读（P4）：入站控制字节一律丢弃，绝不转发到设备——
            # 服务端强制，前端禁触控只是 UX 不是安全边界。
            continue
        holder_sid = await _holder_session_id(session.udid, device_lock, holder_cache)
        if holder_sid != session.session_id:
            # 锁易主/过期：立即断开（契约 §3）
            session.kicked = True
            await websocket.close(code=4403)
            return None
        peer = registry.get_data(session.session_id)
        if peer is not None:
            await peer.send_bytes(data)
        # data WS 未配对（P1 骨架 / S1 建流中）：静默丢帧


async def _holder_session_id(
    udid: str, device_lock: Any, cache: dict[str, Any]
) -> str | None:
    """当前锁持有者的 session_id，结果缓存 HOLDER_CACHE_TTL_S 秒（性能）"""
    now = time.monotonic()
    if now < cache["expires"]:
        return cache["sid"]
    holder = await device_lock.holder(udid)  # 契约 §4 value JSON；无锁 → None
    sid = holder.get("session_id") if isinstance(holder, dict) else None
    cache["expires"] = now + HOLDER_CACHE_TTL_S
    cache["sid"] = sid
    return sid


async def _renew_lock_loop(session: BrowserSession, device_lock: Any) -> None:
    """契约 §4 续期来源①：有活跃帧时每 10s renew；续期失败（锁已过期/
    被 takeover）→ 踢断浏览器连接"""
    try:
        while True:
            await asyncio.sleep(LOCK_RENEW_INTERVAL_S)
            if not session.saw_frame:
                continue
            session.saw_frame = False
            try:
                renewed = await device_lock.renew(session.udid, session.session_id)
            except Exception:
                logger.exception("设备锁续期异常 udid=%s", session.udid)
                continue
            if not renewed:
                logger.info(
                    "设备锁续期失败（已过期/被接管），断开浏览器 session=%s",
                    session.session_id,
                )
                session.kicked = True
                await _safe_close(session.ws, code=4403)
                return
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("锁续期任务异常退出 session=%s", session.session_id)


async def _kick_peer_data_ws(session_id: str) -> None:
    """拆对：浏览器端退出时踢断配对的 data WS"""
    peer = registry.get_data(session_id)
    if peer is not None:
        registry.unbind_data(session_id, peer)
        await _safe_close(peer, code=4410)


async def _safe_close(ws: Any, code: int) -> None:
    try:
        await ws.close(code=code)
    except Exception:
        pass  # 已断开等


# ── Agent 投屏 data WS ─────────────────────────────────────────


@router.websocket("/api/v1/app/agents/data-ws")
async def agent_data_ws(websocket: WebSocket, session_id: str = Query(...)) -> None:
    """Agent 出站数据面连接：与浏览器控制 WS 按 session_id 配对（契约 §3）"""
    token = websocket.headers.get("X-Agent-Token", "")
    await websocket.accept()

    try:
        resolved = await resolve_agent_by_token(token)
    except Exception:
        logger.exception("data-ws 鉴权查询失败")
        await websocket.close(code=1011)
        return
    if resolved is None:
        await websocket.close(code=4401)
        return
    agent_id = resolved[0]

    browser = registry.get_browser(session_id)
    if browser is None:
        # 无等待配对的浏览器会话
        await websocket.close(code=4404)
        return
    parsed = split_udid(browser.udid)
    if parsed is None or parsed[0] != agent_id:
        # 会话对应的设备不属于该 agent
        await websocket.close(code=4403)
        return
    if not registry.bind_data(session_id, websocket):
        await websocket.close(code=4409)
        return

    logger.info("data WS 配对完成 session=%s agent=%s", session_id, agent_id)
    # video 方向经 bounded queue 泵送到浏览器：data-ws 接收循环只 offer（O(1)、
    # 绝不阻塞），浏览器慢时在泵里丢最旧帧而非反压接收侧 / 无界堆积（S1 结论）。
    pump = VideoPump(browser.ws.send_bytes, session_id=session_id)
    pump_task = asyncio.create_task(pump.run())
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            data = message.get("bytes")
            if data is None:
                continue
            # Agent → 浏览器方向不做锁校验（契约 §3 只查反向）
            pump.offer(data)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("data WS 异常退出 session=%s", session_id)
    finally:
        pump.close()
        pump_task.cancel()
        registry.unbind_data(session_id, websocket)
        if pump.dropped:
            logger.info(
                "data WS 关闭 session=%s 累计丢帧=%d（浏览器消费慢）",
                session_id,
                pump.dropped,
            )
        # 拆对通知对端：踢断标记 → 浏览器端清理不 release，锁靠 TTL 过期
        browser2 = registry.get_browser(session_id)
        if browser2 is not None:
            browser2.kicked = True
            await _safe_close(browser2.ws, code=4410)
        logger.info("data WS 断开 session=%s agent=%s", session_id, agent_id)
