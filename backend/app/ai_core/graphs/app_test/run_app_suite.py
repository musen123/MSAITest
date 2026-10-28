"""APP 自动化套件批量执行 — 统一任务图（P4，契约 §3.4）

套件 = 有序用例编组。同一设备一锁贯穿整个套件（kind=replay，续期三来源③），
按 sort_order 顺序回放启用用例：每条独立 Agent 会话（exec-{task}-c{exec_id}，
独立 Midscene 报告）→ 结果落 app_execution（挂 suite_execution_id）→ 汇总
计数落 app_suite_execution（逐条递增，前端实时可见）。

失败策略：continue（默认）单条失败继续跑完；stop 遇错中断，余量记 skipped。
取消闭环同单用例回放（S级铁律）：轮询 event_bus.is_canceled，命中发 abort
帧到真机，当前条记 cancelled、余量记 skipped、汇总记 cancelled 正常收尾。
入口两个：手动（suites 端点预创建汇总行）/ 定时（scheduler fire_job 只带
suite_id，汇总行图内自建）。kind=app_exec → app_tasks 独立队列。
"""

import asyncio
import time
from typing import Any, Optional, TypedDict

from app.ai_core.runtime import event_bus
from app.ai_core.runtime.context import TaskContext
from app.ai_core.runtime.registry import TaskSpec, register
from app.db.session import async_session_maker

# 单条用例回放 RPC 上限（对齐网关 300s 天花板）
CASE_RPC_TIMEOUT_MS = 300_000
_CANCEL_POLL_S = 2
_RENEW_EVERY_POLLS = 5  # 2s × 5 = 10s 续一次锁


class RunAppSuiteState(TypedDict, total=False):
    suite_id: int
    suite_execution_id: Optional[int]
    device_udid: Optional[str]
    trigger_type: str
    # 结果（extract_result 用）
    exec_status: str
    passed: int
    failed: int
    skipped: int
    error: Optional[str]


def build_graph(params: dict, ctx: TaskContext) -> Any:
    from langgraph.graph import END, START, StateGraph

    async def _raced_rpc(
        agent_id: int,
        udid: str,
        lock_session: str,
        agent_session: str,
        rpc_params: dict,
    ) -> tuple[Optional[dict], bool, Optional[str]]:
        """单条用例 RPC + 取消轮询(2s) + 锁续期(10s) + 进度直播转 SSE。

        返回 (result, cancelled, error)。锁续期用 lock_session（一锁贯穿套件），
        进度拉取/abort 用 agent_session（每条用例独立会话）。
        """
        from app.services.app_device.gateway_rpc import (
            AgentRpcError,
            GatewayRpcError,
            call_agent_rpc,
        )
        from app.services.app_device.lock import device_lock

        progress_seq = 0

        async def _pump_progress(timeout_ms: int = 8_000) -> None:
            nonlocal progress_seq
            try:
                prog = await call_agent_rpc(
                    agent_id,
                    "get_app_step_progress",
                    {"session_id": agent_session, "after_seq": progress_seq},
                    timeout_ms=timeout_ms,
                )
            except (AgentRpcError, GatewayRpcError):
                return
            for e in prog.get("entries") or []:
                text = str(e.get("text") or "")
                if text:
                    ctx.log(text, level="warning" if e.get("kind") == "error" else "info")
            progress_seq = int(prog.get("seq") or progress_seq)

        rpc_task = asyncio.create_task(
            call_agent_rpc(
                agent_id, "run_app_yaml", rpc_params, timeout_ms=CASE_RPC_TIMEOUT_MS
            )
        )
        polls = 0
        while True:
            done, _ = await asyncio.wait({rpc_task}, timeout=_CANCEL_POLL_S)
            if done:
                break
            polls += 1
            if polls % _RENEW_EVERY_POLLS == 0:
                await device_lock.renew(udid, lock_session)  # 续期来源③
            await _pump_progress()
            if await event_bus.is_canceled(ctx.task_id):
                ctx.log("收到取消请求，正在停止设备侧执行…", level="warning")
                for c in ("abort_app_flow", "end_app_session"):
                    try:
                        await call_agent_rpc(
                            agent_id, c, {"session_id": agent_session}, timeout_ms=10_000
                        )
                    except (AgentRpcError, GatewayRpcError):
                        pass
                rpc_task.cancel()
                return None, True, "用户取消"
        await _pump_progress(timeout_ms=5_000)
        try:
            return await rpc_task, False, None
        except (AgentRpcError, GatewayRpcError) as exc:
            return None, False, str(exc)

    async def run(state: RunAppSuiteState) -> dict:
        from app.ai_core.graphs.app_test.run_app_script import (
            _fetch_report,
            _record_ai_model,
            _resolve_vision_model,
        )
        from app.crud.app_device.device import crud_app_device
        from app.crud.app_test import (
            crud_app_execution,
            crud_app_suite,
            crud_app_suite_execution,
        )
        from app.services.app_device.gateway_rpc import (
            AgentRpcError,
            GatewayRpcError,
            call_agent_rpc,
        )
        from app.services.app_device.lock import device_lock

        suite_id = state["suite_id"]
        trigger_type = state.get("trigger_type") or "manual"
        lock_session = f"exec-{ctx.task_id}"

        # ── 1. 准备：套件 / 编排 / 设备 / 模型 ──
        ctx.stage("准备执行", index=1, total=2)
        ctx.progress(3)
        async with async_session_maker() as db:
            suite = await crud_app_suite.get_in_project(db, ctx.project_id, suite_id)
            if suite is None:
                raise ValueError(f"套件不存在：{suite_id}")
            suite_name = suite.name
            failure_strategy = suite.failure_strategy
            udid = state.get("device_udid") or suite.device_udid
            cases = [
                {"script_id": s.id, "name": s.name, "yaml": s.yaml_content}
                for c, s in await crud_app_suite.get_cases_with_script(db, suite_id)
                if c.enabled
            ]
            if not udid:
                raise ValueError("套件未配默认执行设备，且本次执行未指定设备")
            if not cases:
                raise ValueError("套件没有启用的用例，无法执行")
            device = await crud_app_device.get_by_udid(db, udid)
            if device is None:
                raise ValueError(f"设备不存在：{udid}")
            agent_id, serial = device.agent_id, device.serial

            # 汇总行：手动入口端点已预创建；定时入口图内自建
            execution_id = state.get("suite_execution_id")
            if execution_id is None:
                execution = await crud_app_suite_execution.create(
                    db,
                    suite_id=suite_id,
                    project_id=ctx.project_id,
                    device_udid=udid,
                    trigger_type=trigger_type,
                    ai_task_id=str(ctx.task_id),
                    status="pending",
                    created_by=ctx.user_id,
                )
                execution_id = execution.id

        model = await _resolve_vision_model(ctx.user_id)
        await _record_ai_model(ctx.task_id, model.get("name"))
        total = len(cases)
        ctx.log(f"套件「{suite_name}」→ 设备 {udid} · {total} 条用例 · 失败策略 {failure_strategy}")

        # ── 2. 抢锁（一锁贯穿整个套件；同用户接管——用户开着操作台点批量执行
        # 是常态，撞自己的 control 锁不该失败，对齐探索图先例）──
        acquired, holder = await device_lock.acquire(
            udid, ctx.user_id, lock_session, "replay"
        )
        if not acquired and holder and holder.get("owner_user_id") == ctx.user_id:
            acquired = await device_lock.takeover(udid, ctx.user_id, lock_session, "replay")
            if acquired:
                ctx.log("已接管你自己的设备会话（原投屏/录制会话将断开）", level="warning")
        if not acquired:
            owner = (holder or {}).get("owner_user_id")
            msg = f"设备被占用（用户 #{owner}），无法执行套件"
            async with async_session_maker() as db:
                execution = await crud_app_suite_execution.get(db, execution_id)
                if execution is not None:
                    await crud_app_suite_execution.update(
                        db, execution, {"status": "failed", "error": msg}
                    )
            raise ValueError(msg)

        started = time.monotonic()
        passed = failed = done = 0
        cancelled = False
        stop_reason: Optional[str] = None
        current_session: Optional[str] = None
        try:
            async with async_session_maker() as db:
                execution = await crud_app_suite_execution.get(db, execution_id)
                if execution is not None:
                    await crud_app_suite_execution.update(
                        db, execution, {"status": "running", "total_cases": total}
                    )

            ctx.stage("批量回放", index=2, total=2)
            for i, case in enumerate(cases):
                # 每条开跑前先看取消（条间窗口）
                if await event_bus.is_canceled(ctx.task_id):
                    cancelled = True
                    break

                ctx.progress(min(95, 5 + int(i / total * 90)))
                ctx.log(f"[{i + 1}/{total}] 开始回放「{case['name']}」")
                async with async_session_maker() as db:
                    case_exec = await crud_app_execution.create(
                        db,
                        script_id=case["script_id"],
                        device_udid=udid,
                        ai_task_id=str(ctx.task_id),
                        status="running",
                        suite_execution_id=execution_id,
                    )
                case_started = time.monotonic()
                # 每条独立 Agent 会话：独立 Midscene 报告 + dispose 清内存态
                current_session = f"exec-{ctx.task_id}-c{case_exec.id}"
                result, case_cancelled, err = await _raced_rpc(
                    agent_id,
                    udid,
                    lock_session,
                    current_session,
                    {
                        "serial": serial,
                        "session_id": current_session,
                        "yaml": case["yaml"],
                        "model": model,
                        # 起点锚定：每条用例都从桌面起跑（P3 联调实证）
                        "press_home": True,
                    },
                )
                case_status = "failed"
                if case_cancelled:
                    case_status = "cancelled"
                    cancelled = True
                elif result is not None and result.get("status") == "ok":
                    case_status = "success"
                elif result is not None:
                    err = str(result.get("error") or "回放失败")

                # 报告成功失败都取（失败现场在报告里）；取消不取（会话已结束）
                report_path = None
                if not case_cancelled:
                    report_path = await _fetch_report(agent_id, current_session, case_exec.id)
                try:
                    await call_agent_rpc(
                        agent_id,
                        "end_app_session",
                        {"session_id": current_session},
                        timeout_ms=15_000,
                    )
                except (AgentRpcError, GatewayRpcError):
                    pass
                current_session = None

                case_duration = int((time.monotonic() - case_started) * 1000)
                async with async_session_maker() as db:
                    row = await crud_app_execution.get(db, case_exec.id)
                    if row is not None:
                        await crud_app_execution.update(
                            db,
                            row,
                            {
                                "status": case_status,
                                "steps_summary": {
                                    "result": (result or {}).get("result"),
                                    "error": err,
                                    "session_id": f"exec-{ctx.task_id}-c{case_exec.id}",
                                },
                                "report_path": report_path,
                                "duration_ms": case_duration,
                            },
                        )

                if case_status == "success":
                    passed += 1
                    ctx.log(f"[{i + 1}/{total}] 「{case['name']}」通过（{case_duration}ms）")
                elif case_status == "cancelled":
                    ctx.log(f"[{i + 1}/{total}] 「{case['name']}」已取消", level="warning")
                else:
                    failed += 1
                    ctx.log(
                        f"[{i + 1}/{total}] 「{case['name']}」失败：{err}", level="warning"
                    )
                done = i + 1

                # 汇总计数逐条回写（前端列表实时可见）
                async with async_session_maker() as db:
                    execution = await crud_app_suite_execution.get(db, execution_id)
                    if execution is not None:
                        await crud_app_suite_execution.update(
                            db, execution, {"passed_count": passed, "failed_count": failed}
                        )

                if cancelled:
                    break
                if case_status == "failed" and failure_strategy == "stop":
                    stop_reason = f"失败策略 stop：第 {i + 1} 条失败，中断余下 {total - done} 条"
                    ctx.log(stop_reason, level="warning")
                    break
        finally:
            # 无条件收尾：当前会话兜底 end（幂等）+ 释放锁
            if current_session is not None:
                try:
                    await call_agent_rpc(
                        agent_id,
                        "end_app_session",
                        {"session_id": current_session},
                        timeout_ms=15_000,
                    )
                except (AgentRpcError, GatewayRpcError):
                    pass
            try:
                await device_lock.release(udid, lock_session)
            except Exception:  # noqa: BLE001
                pass

        skipped = total - done
        duration_ms = int((time.monotonic() - started) * 1000)
        if cancelled:
            exec_status, error_msg = "cancelled", "用户取消"
        elif failed > 0:
            exec_status = "failed"
            error_msg = stop_reason or f"{failed}/{total} 条用例失败"
        else:
            exec_status, error_msg = "success", None

        async with async_session_maker() as db:
            execution = await crud_app_suite_execution.get(db, execution_id)
            if execution is not None:
                await crud_app_suite_execution.update(
                    db,
                    execution,
                    {
                        "status": exec_status,
                        "passed_count": passed,
                        "failed_count": failed,
                        "skipped_count": skipped,
                        "error": error_msg,
                        "duration_ms": duration_ms,
                    },
                )

        summary = f"通过 {passed} / 失败 {failed} / 跳过 {skipped}（共 {total} 条，{duration_ms}ms）"
        ctx.log(
            f"套件执行{('已取消' if cancelled else '完成')}：{summary}",
            level="warning" if exec_status != "success" else "info",
        )
        ctx.progress(100)
        # 有失败让任务失败（汇总/明细已落库），取消/成功正常收尾——同单用例回放约定
        if exec_status == "failed":
            raise RuntimeError(f"套件执行失败：{error_msg}")
        return {
            "exec_status": exec_status,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "error": error_msg,
            "suite_execution_id": execution_id,
        }

    graph = StateGraph(RunAppSuiteState)
    graph.add_node("run", run)
    graph.add_edge(START, "run")
    graph.add_edge("run", END)
    return graph.compile()


def _extract_result(final_state: dict) -> tuple[Optional[dict], Optional[dict]]:
    summary = {
        "exec_status": final_state.get("exec_status"),
        "passed": final_state.get("passed"),
        "failed": final_state.get("failed"),
        "skipped": final_state.get("skipped"),
        "error": final_state.get("error"),
    }
    ref = {"kind": "app_suite_execution", "suite_execution_id": final_state.get("suite_execution_id")}
    return summary, ref


register(
    TaskSpec(
        task_type="run_app_suite",
        build_graph=build_graph,
        build_input=lambda params: {
            "suite_id": params["suite_id"],
            "suite_execution_id": params.get("suite_execution_id"),
            "device_udid": params.get("device_udid"),
            "trigger_type": params.get("trigger_type") or "manual",
        },
        title=lambda params: f"App 套件执行：{params.get('suite_name') or params['suite_id']}",
        llm_kind="none",  # VISION 配置图内直读（Agent 侧持内存态），壳层不加载 LLM
        extract_result=_extract_result,
        kind="app_exec",  # → app_tasks 独立队列
        stream_messages=False,
        adapter_cancel=False,  # 图内协作式取消（abort 帧到真机），禁硬中断跳过收尾
    )
)
