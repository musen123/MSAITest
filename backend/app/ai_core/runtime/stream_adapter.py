"""StreamAdapter — LangGraph 流 → 统一事件

消费 ``graph.astream(input, stream_mode=["updates","messages","custom"])``：
  - custom（writer 发的 dict）  → stage / progress / log / result
  - messages（token 流）        → message_delta（全量落库，逐条实时推送）
  - updates（节点状态变更）      → node_update

每个事件分配单调 seq，**实时逐条 PUBLISH 到 Redis**（前端打字机），
**DB 批量写入**（每 flush_ms 一次多行 INSERT，规避写放大）。
seq 在实时通道与 DB 回放间保持一致，支撑 SSE 断线续传。

周期性更新 ai_task 主表 progress/current_stage/heartbeat；每 N 事件检查取消。
"""

import time
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_core.runtime import event_bus
from app.ai_core.runtime.context import TaskContext
from app.ai_core.runtime.events import (
    EventType,
    W_BIZ,
    W_LOG,
    W_LOG_LEVEL,
    W_PROGRESS,
    W_STAGE,
    W_STAGE_INDEX,
    W_STAGE_TOTAL,
    log_payload,
    make_event,
    message_delta_payload,
    node_update_payload,
    progress_payload,
    result_payload,
    stage_payload,
)
from app.crud.ai.ai_task import crud_ai_task


class TaskCanceled(Exception):
    """协作式取消信号"""


class StreamAdapter:
    def __init__(
        self,
        *,
        db: AsyncSession,
        task_id: int,
        ctx: TaskContext,
        flush_ms: int = 300,
        cancel_check_every: int = 20,
        stream_messages: bool = True,
        adapter_cancel: bool = True,
    ) -> None:
        self.db = db
        self.task_id = task_id
        self.ctx = ctx
        self.flush_ms = flush_ms
        self.cancel_check_every = cancel_check_every
        # False 时不订阅 messages 模式（见 TaskSpec.stream_messages）
        self.stream_messages = stream_messages
        # False 时不做事件计数取消检查（图自带协作取消，见 TaskSpec.adapter_cancel）
        self.adapter_cancel = adapter_cancel

        # seq 不恒从 0 起：consume() 开头从 DB 已落库 MAX(seq) 续接（见 _resume_seq）。
        # task_acks_late=True 重投同一任务时，新 worker 接着已存在的 seq 编号，
        # 避免裸 insert 撞 (task_id,seq) 唯一约束、整批回滚 → 回放丢段。
        self.seq = 0
        self._seq_resumed = False
        self._db_batch: list[dict] = []
        self._last_flush = time.monotonic()
        self._since_cancel_check = 0
        # 供 shell 兜底持久化
        self.result_summary: Optional[dict] = None
        self.result_ref: Optional[dict] = None
        # 最新完整 state（用于 spec.extract_result 兜底）
        self.final_state: Any = None

    # ── 事件发射 ────────────────────────────────────────────

    async def _resume_seq(self) -> None:
        """从 DB 当前 MAX(seq) 续接 seq（幂等，仅首次实际查询）。

        正常首跑：表内无该任务事件 → max_seq=0 → 从 1 起，行为不变。
        重投/续跑：表内已有事件 → 从 max_seq+1 起，新 emit 不与已落库 seq 冲突。
        """
        if self._seq_resumed:
            return
        self._seq_resumed = True
        max_seq = await crud_ai_task.max_event_seq(self.db, task_id=self.task_id)
        if max_seq > self.seq:
            self.seq = max_seq

    async def emit(self, event_type: str, payload: Optional[dict] = None) -> None:
        # 兜底：若 consume() 尚未跑到（如极早期异常路径直接 emit），先续接 seq
        if not self._seq_resumed:
            await self._resume_seq()
        self.seq += 1
        ev = make_event(self.seq, event_type, payload)
        await event_bus.publish(self.task_id, ev)
        self._db_batch.append({"seq": self.seq, "type": event_type, "payload": payload})

    # ── 主循环 ──────────────────────────────────────────────

    async def consume(self, graph: Any, graph_input: dict) -> None:
        # 续接 seq：重投时从 DB 已有 max_seq+1 起编号（首跑则从 1 起，行为不变）
        await self._resume_seq()
        # subgraphs=True：嵌套子图内部的 messages/updates/custom 事件原生冒泡，
        # 每项形如 (namespace, mode, data)；顶层 namespace 为 ()。
        modes = ["values", "updates", "messages", "custom"]
        if not self.stream_messages:
            modes.remove("messages")
        async for item in graph.astream(
            graph_input,
            stream_mode=modes,
            subgraphs=True,
        ):
            if isinstance(item, tuple) and len(item) == 3:
                _ns, mode, data = item
            elif isinstance(item, tuple) and len(item) == 2:
                mode, data = item
            else:  # 兜底：单 mode
                mode, data = "updates", item
            await self._handle(mode, data)
            await self._maybe_flush()
            await self._maybe_cancel_check()
        # 收尾 flush
        await self.flush()

    async def _handle(self, mode: str, data: Any) -> None:
        if mode == "values":
            self.final_state = data  # 记录最新完整 state，不发事件
        elif mode == "custom":
            await self._handle_custom(data)
        elif mode == "messages":
            await self._handle_message(data)
        elif mode == "updates":
            await self._handle_update(data)

    async def _handle_custom(self, data: Any) -> None:
        if not isinstance(data, dict):
            await self.emit(EventType.LOG.value, log_payload(str(data)))
            return
        if W_STAGE in data:
            name = data.get(W_STAGE) or ""
            index = data.get(W_STAGE_INDEX)
            total = data.get(W_STAGE_TOTAL)
            await self.emit(EventType.STAGE.value, stage_payload(name, index, total))
            await crud_ai_task.update_progress(
                self.db,
                task_id=self.task_id,
                current_stage=name,
                stage_index=index,
                total_stages=total,
            )
        elif W_PROGRESS in data:
            pct = int(data.get(W_PROGRESS) or 0)
            await self.emit(EventType.PROGRESS.value, progress_payload(pct))
            await crud_ai_task.update_progress(self.db, task_id=self.task_id, progress=pct)
        elif W_LOG in data:
            await self.emit(
                EventType.LOG.value,
                log_payload(str(data.get(W_LOG)), data.get(W_LOG_LEVEL, "info")),
            )
        elif W_BIZ in data:
            # 业务自定义事件（payload 含 kind 字段，前端按 kind 渲染）
            biz = data.get(W_BIZ)
            if isinstance(biz, dict) and biz:
                await self.emit(EventType.BIZ.value, biz)
        elif "_message_delta" in data:
            # 子工作流转发来的 LLM token（实时输出）
            text = str(data.get("_message_delta") or "")
            if text:
                await self.emit(
                    EventType.MESSAGE_DELTA.value,
                    message_delta_payload(text, data.get("_node")),
                )
        elif "_result" in data:
            res = data.get("_result") or {}
            self.result_summary = res.get("summary")
            self.result_ref = res.get("ref")
            await self.emit(
                EventType.RESULT.value,
                result_payload(self.result_summary, self.result_ref),
            )
        else:
            # 其余 custom 一律归 log
            await self.emit(EventType.LOG.value, log_payload(_safe_json(data)))

    async def _handle_message(self, data: Any) -> None:
        # data 通常为 (message_chunk, metadata)
        chunk, meta = (data if isinstance(data, tuple) and len(data) == 2 else (data, {}))
        text = _chunk_text(getattr(chunk, "content", None))
        if not text:
            return
        node = (meta or {}).get("langgraph_node") if isinstance(meta, dict) else None
        await self.emit(EventType.MESSAGE_DELTA.value, message_delta_payload(text, node))

    async def _handle_update(self, data: Any) -> None:
        if not isinstance(data, dict):
            return
        for node, updates in data.items():
            keys = list(updates.keys()) if isinstance(updates, dict) else []
            await self.emit(EventType.NODE_UPDATE.value, node_update_payload(node, keys))

    # ── 落库 / 取消 ─────────────────────────────────────────

    async def _maybe_flush(self) -> None:
        if (time.monotonic() - self._last_flush) * 1000 >= self.flush_ms or len(
            self._db_batch
        ) >= 100:
            await self.flush()

    async def flush(self) -> None:
        if not self._db_batch:
            return
        batch = self._db_batch
        self._db_batch = []
        await crud_ai_task.append_events(self.db, task_id=self.task_id, events=batch)
        await crud_ai_task.heartbeat(self.db, task_id=self.task_id)
        self._last_flush = time.monotonic()

    async def _maybe_cancel_check(self) -> None:
        if not self.adapter_cancel:
            return
        self._since_cancel_check += 1
        if self._since_cancel_check >= self.cancel_check_every:
            self._since_cancel_check = 0
            if await event_bus.is_canceled(self.task_id):
                await self.flush()
                raise TaskCanceled()


def _chunk_text(content: Any) -> str:
    """从 message chunk content 提取文本（兼容 str / list[dict]）"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for c in content:
            if isinstance(c, str):
                parts.append(c)
            elif isinstance(c, dict):
                parts.append(c.get("text") or c.get("content") or "")
        return "".join(parts)
    return str(content)


def _safe_json(data: Any) -> str:
    import json

    try:
        return json.dumps(data, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(data)
