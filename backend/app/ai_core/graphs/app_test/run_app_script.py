"""APP 自动化用例回放 — 统一任务图（P2，契约 §3.2）

回放已保存用例（Midscene YAML）到指定设备：
    抢设备锁（kind=replay，session=exec-{task_id}）
    → 经网关 RPC run_app_yaml（Agent 侧 AndroidAgent.runYaml）
    → 分块拉取 HTML 报告落 APP_REPORT_DIR（鉴权端点展示，绝不落 /uploads）
    → 更新 app_execution（status/steps_summary/report_path/duration_ms）。

取消闭环（S级铁律）：RPC 在跑期间每 2s 轮询 event_bus.is_canceled，命中即发
abort_app_flow + end_app_session 到真机（否则任务标 failed 后真机仍被驱动烧
token 占锁）；同一循环每 10s 续设备锁（契约 §4 续期来源③=exec 图心跳）。
finally 无条件 end_app_session（幂等，dispose 清 Agent 侧内存 modelConfig）+
释放锁。kind=app_exec → 独立 app_tasks 队列（worker 需 -Q 增列）。
"""

import asyncio
import base64
import time
from pathlib import Path
from typing import Any, Optional, TypedDict

from app.ai_core.runtime import event_bus
from app.ai_core.runtime.context import TaskContext
from app.ai_core.runtime.registry import TaskSpec, register
from app.core.config import settings
from app.db.session import async_session_maker

# 回放 RPC 超时（整段 YAML 一次 RPC；10 步 ≈ 60–90s，上限对齐网关 300s）
REPLAY_RPC_TIMEOUT_MS = 300_000
# 取消轮询节拍 / 锁续期节拍
_CANCEL_POLL_S = 2
_RENEW_EVERY_POLLS = 5  # 2s × 5 = 10s 续一次锁
# 报告分块大小（256KB/块）
_REPORT_CHUNK_BYTES = 262_144


class RunAppScriptState(TypedDict, total=False):
    script_id: int
    execution_id: int
    device_udid: str
    # 结果（extract_result 用）
    exec_status: str
    report_path: Optional[str]
    error: Optional[str]


async def _resolve_vision_model(user_id: int) -> dict:
    """回放执行者的默认 VISION 配置 → Agent model 参数（family 必填）。"""
    from app.crud.auth.user_llm_config import crud_user_llm_config
    from app.models.auth.user_llm_config import ModelType

    async with async_session_maker() as db:
        cfg = await crud_user_llm_config.get_default(
            db, user_id=user_id, model_type=ModelType.VISION
        )
    if cfg is None or not cfg.is_active:
        raise ValueError("未配置视觉（VISION）模型，无法回放")
    if not cfg.base_url or not cfg.model_family:
        raise ValueError(
            "VISION 模型缺少 Base URL 或 model_family（Midscene 兼容家族），无法回放"
        )
    return {
        "name": cfg.model,
        "base_url": cfg.base_url,
        "api_key": cfg.api_key,
        "family": cfg.model_family,
    }


async def _record_ai_model(task_id: int, model_name: Optional[str]) -> None:
    """App 三图 llm_kind="none"，壳层不回写 ai_model——图内补记（任务中心展示用）。"""
    if not model_name:
        return
    from app.crud.ai.ai_task import crud_ai_task

    async with async_session_maker() as db:
        await crud_ai_task.set_ai_model(db, task_id=task_id, ai_model=model_name)


async def _fetch_report(agent_id: int, session_id: str, execution_id: int) -> Optional[str]:
    """分块拉取报告 HTML 落盘；无报告/失败返回 None（不阻塞回放结论）。"""
    from app.services.app_device.gateway_rpc import AgentRpcError, call_agent_rpc

    chunks: list[bytes] = []
    offset = 0
    try:
        while True:
            part = await call_agent_rpc(
                agent_id,
                "get_app_report",
                {"session_id": session_id, "offset": offset, "max_bytes": _REPORT_CHUNK_BYTES},
                timeout_ms=30_000,
            )
            chunks.append(base64.b64decode(part.get("data_b64") or ""))
            offset += len(chunks[-1])
            if part.get("eof") or not part.get("data_b64"):
                break
    except AgentRpcError:
        return None  # 会话已结束/无报告：可接受，报告缺失不改回放结论
    html = b"".join(chunks)
    if not html:
        return None
    report_dir = Path(settings.APP_REPORT_DIR)
    report_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{execution_id}.html"
    (report_dir / filename).write_bytes(html)
    return filename


def build_graph(params: dict, ctx: TaskContext) -> Any:
    from langgraph.graph import END, START, StateGraph

    async def run(state: RunAppScriptState) -> dict:
        from app.crud.app_device.device import crud_app_device
        from app.crud.app_test import crud_app_execution, crud_app_script
        from app.services.app_device.gateway_rpc import (
            AgentRpcError,
            GatewayRpcError,
            call_agent_rpc,
        )
        from app.services.app_device.lock import device_lock

        script_id = state["script_id"]
        execution_id = state["execution_id"]
        udid = state["device_udid"]
        session_id = f"exec-{ctx.task_id}"

        # ── 1. 准备：用例 / 设备 / 模型 ──
        ctx.stage("准备回放", index=1, total=3)
        ctx.progress(5)
        async with async_session_maker() as db:
            script = await crud_app_script.get_in_project(db, ctx.project_id, script_id)
            if script is None:
                raise ValueError(f"用例不存在：{script_id}")
            yaml_content = script.yaml_content
            script_name = script.name
            device = await crud_app_device.get_by_udid(db, udid)
            if device is None:
                raise ValueError(f"设备不存在：{udid}")
            agent_id, serial = device.agent_id, device.serial
        model = await _resolve_vision_model(ctx.user_id)
        await _record_ai_model(ctx.task_id, model.get("name"))
        ctx.log(f"用例「{script_name}」→ 设备 {udid}")

        # ── 2. 抢锁（kind=replay）──
        acquired, holder = await device_lock.acquire(
            udid, ctx.user_id, session_id, "replay"
        )
        if not acquired:
            owner = (holder or {}).get("owner_user_id")
            # 锁失败发生在 execution 转 running 之前——同步标 failed，
            # 不给执行记录页留永远 pending 的孤儿行
            async with async_session_maker() as db:
                execution = await crud_app_execution.get(db, execution_id)
                if execution is not None and execution.status == "pending":
                    await crud_app_execution.update(db, execution, {"status": "failed"})
            raise ValueError(f"设备被占用（用户 #{owner}），无法回放")

        started = time.monotonic()
        exec_status = "failed"
        error_msg: Optional[str] = None
        result_payload: Any = None
        report_path: Optional[str] = None
        try:
            async with async_session_maker() as db:
                execution = await crud_app_execution.get(db, execution_id)
                if execution is not None:
                    await crud_app_execution.update(db, execution, {"status": "running"})

            # ── 3. 回放 RPC（raced：取消轮询 + 锁续期 + 进度直播转 SSE）──
            ctx.stage("回放执行", index=2, total=3)
            ctx.progress(15)

            progress_seq = 0

            async def _pump_progress(timeout_ms: int = 8_000) -> None:
                """增量拉 Agent 侧执行进度（模型每轮规划/定位/动作）→ ctx.log
                转统一事件流，前端实时查看页直播。best-effort，拉不到不影响执行。"""
                nonlocal progress_seq
                try:
                    prog = await call_agent_rpc(
                        agent_id,
                        "get_app_step_progress",
                        {"session_id": session_id, "after_seq": progress_seq},
                        timeout_ms=timeout_ms,
                    )
                except (AgentRpcError, GatewayRpcError):
                    return
                for e in prog.get("entries") or []:
                    text = str(e.get("text") or "")
                    if text:
                        ctx.log(
                            text,
                            level="warning" if e.get("kind") == "error" else "info",
                        )
                progress_seq = int(prog.get("seq") or progress_seq)

            rpc_task = asyncio.create_task(
                call_agent_rpc(
                    agent_id,
                    "run_app_yaml",
                    {
                        "serial": serial,
                        "session_id": session_id,
                        "yaml": yaml_content,
                        "model": model,
                        # 起点锚定：回放前回桌面。设备停在任意页面时，从"当前屏"
                        # 起跑首步定位必失败（P3 联调实证的同款问题）
                        "press_home": True,
                    },
                    timeout_ms=REPLAY_RPC_TIMEOUT_MS,
                )
            )
            polls = 0
            while True:
                done, _ = await asyncio.wait({rpc_task}, timeout=_CANCEL_POLL_S)
                if done:
                    break
                polls += 1
                if polls % _RENEW_EVERY_POLLS == 0:
                    await device_lock.renew(udid, session_id)  # 续期来源③
                await _pump_progress()
                if await event_bus.is_canceled(ctx.task_id):
                    # 取消闭环：abort 帧必须到真机，别让它继续烧 token
                    ctx.log("收到取消请求，正在停止设备侧执行…", level="warning")
                    for cmd in ("abort_app_flow", "end_app_session"):
                        try:
                            await call_agent_rpc(
                                agent_id, cmd, {"session_id": session_id}, timeout_ms=10_000
                            )
                        except (AgentRpcError, GatewayRpcError):
                            pass
                    exec_status = "cancelled"
                    error_msg = "用户取消"
                    rpc_task.cancel()
                    break
            if exec_status != "cancelled":
                # 收尾补拉：RPC 已结束，缓冲里可能还剩没拉走的尾行
                await _pump_progress(timeout_ms=5_000)
                try:
                    result = await rpc_task
                except (AgentRpcError, GatewayRpcError) as exc:
                    error_msg = str(exc)
                else:
                    if result.get("status") == "ok":
                        exec_status = "success"
                        result_payload = result.get("result")
                    else:
                        error_msg = str(result.get("error") or "回放失败")

                # ── 4. 拉报告（成功失败都取，报告里有失败现场）──
                ctx.stage("回收报告", index=3, total=3)
                ctx.progress(85)
                report_path = await _fetch_report(agent_id, session_id, execution_id)
        finally:
            # 无条件收尾：end_app_session（dispose+清 key，幂等）+ 释放锁
            from app.services.app_device.gateway_rpc import (
                AgentRpcError as _ARE,
                GatewayRpcError as _GRE,
                call_agent_rpc as _call,
            )

            try:
                await _call(agent_id, "end_app_session", {"session_id": session_id}, timeout_ms=15_000)
            except (_ARE, _GRE):
                pass
            try:
                await device_lock.release(udid, session_id)
            except Exception:  # noqa: BLE001
                pass

        duration_ms = int((time.monotonic() - started) * 1000)
        steps_summary = {
            "result": result_payload,
            "error": error_msg,
            "session_id": session_id,
        }
        async with async_session_maker() as db:
            execution = await crud_app_execution.get(db, execution_id)
            if execution is not None:
                await crud_app_execution.update(
                    db,
                    execution,
                    {
                        "status": exec_status,
                        "steps_summary": steps_summary,
                        "report_path": report_path,
                        "duration_ms": duration_ms,
                    },
                )

        if exec_status == "success":
            ctx.log(f"回放成功，耗时 {duration_ms}ms")
        else:
            ctx.log(f"回放{('已取消' if exec_status == 'cancelled' else '失败')}：{error_msg}", level="warning")
        ctx.progress(100)
        # 失败让任务失败（保留 execution 记录），取消/成功正常收尾
        if exec_status == "failed":
            raise RuntimeError(error_msg or "回放失败")
        return {
            "exec_status": exec_status,
            "report_path": report_path,
            "error": error_msg,
        }

    graph = StateGraph(RunAppScriptState)
    graph.add_node("run", run)
    graph.add_edge(START, "run")
    graph.add_edge("run", END)
    return graph.compile()


def _extract_result(final_state: dict) -> tuple[Optional[dict], Optional[dict]]:
    summary = {
        "exec_status": final_state.get("exec_status"),
        "report_path": final_state.get("report_path"),
        "error": final_state.get("error"),
    }
    ref = {"kind": "app_execution", "execution_id": final_state.get("execution_id")}
    return summary, ref


register(
    TaskSpec(
        task_type="run_app_script",
        build_graph=build_graph,
        build_input=lambda params: {
            "script_id": params["script_id"],
            "execution_id": params["execution_id"],
            "device_udid": params["device_udid"],
        },
        title=lambda params: f"App 回放：{params.get('script_name') or params['script_id']}",
        llm_kind="none",  # VISION 配置在图内直读（Agent 侧持内存态），壳层不加载 LLM
        extract_result=_extract_result,
        kind="app_exec",  # → app_tasks 独立队列（worker -Q 需增列）
        stream_messages=False,
        adapter_cancel=False,  # 图内协作式取消（abort 帧到真机），禁硬中断跳过收尾
    )
)
