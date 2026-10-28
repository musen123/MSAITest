"""APP 探索式生成 — 统一任务图（P3，方案 §5 Phase 3 路线 A）

一句自然语言目标 → 设备上自动探索 → 沉淀可回放用例：
    抢/接管设备锁（同用户 takeover，session=explore-{task_id}）
    → RPC run_app_step（Agent 侧一次大 aiAct，多轮规划直到目标完成）
    → 回收即时动作步骤存 AppScript（draft）
    → 同会话 run_app_yaml 回放验证（成功 → active；失败留 draft）
    → 落 app_execution + 分块拉报告（鉴权端点展示，绝不落 /uploads）
    → TEXT 模型断言建议（惰性加载，缺配置优雅跳过；以注释行追加进 YAML）。

Agent / 网关零改动：探索 = run_app_step（instruction=目标句 + 更高
replanning_cycle_limit），验证 = run_app_yaml，全部复用 P2 RPC。

锁语义：探索期间设备独占（浏览器控制 WS 会因续期失败被网关 4403 断开——
围观 observer 语义是 P4 事项）；取消闭环与锁续期同 run_app_script：
RPC 在跑期间每 2s 轮询 event_bus.is_canceled（命中发 abort 帧到真机），
每 10s 续锁（契约 §4 续期来源③）。finally 无条件 end_app_session + 释放锁。

验证失败不算任务失败——生成本身成功（草稿 + 失败报告都是产出），
verify_status 记进结果由前端呈现。kind=app_exec → app_tasks 独立队列。
"""

import asyncio
import time
from typing import Any, Optional, TypedDict

from app.ai_core.runtime import event_bus
from app.ai_core.runtime.context import TaskContext
from app.ai_core.runtime.registry import TaskSpec, register
from app.db.session import async_session_maker

# 探索/验证 RPC 超时（上限对齐网关 MAX_RPC_TIMEOUT_MS=300s）
EXPLORE_RPC_TIMEOUT_MS = 300_000
# 单句 aiAct 最大重规划轮数（成本闸门 G3：一轮≈一次 VL 调用）
_DEFAULT_CYCLE_LIMIT = 12
_CANCEL_POLL_S = 2
_RENEW_EVERY_POLLS = 5  # 2s × 5 = 10s 续一次锁

_ACTION_LABEL = {
    "aiTap": "点击",
    "aiInput": "输入",
    "aiDoubleClick": "双击",
    "aiScroll": "滚动",
    "aiKeyboardPress": "按键",
    "aiLongPress": "长按",
    # 无定位动作（回收完整度增补）
    "AndroidHomeButton": "按 Home 键",
    "AndroidBackButton": "按返回键",
    "AndroidRecentAppsButton": "最近任务键",
    "Swipe": "滑动",
    "PullGesture": "拉动",
    "KeyboardPress": "按键",
    "sleep": "等待",
    "launch": "启动应用",
}


def _step_brief(s: dict) -> str:
    """回收步骤 → 单行人话（locate/value/params 均可缺省）。"""
    label = _ACTION_LABEL.get(str(s.get("action")), str(s.get("action")))
    text = label
    if s.get("locate"):
        text += f"「{s.get('locate')}」"
    if s.get("value"):
        text += f"：{s.get('value')}"
    params = s.get("params") or {}
    if params.get("direction"):
        text += f"（{params['direction']}{'，' + str(params['distance']) + 'px' if params.get('distance') else ''}）"
    elif params.get("timeMs"):
        text += f" {params['timeMs']}ms"
    return text


class ExploreAppScriptState(TypedDict, total=False):
    device_udid: str
    goal: str
    script_name: str
    app_hint: str
    verify: bool
    suggest_asserts: bool
    cycle_limit: int
    # 结果（extract_result 用）
    script_id: Optional[int]
    execution_id: Optional[int]
    steps_count: int
    verify_status: Optional[str]
    asserts: list[str]
    error: Optional[str]


def _yaml_dq(text: str) -> str:
    """YAML 双引号标量转义（反斜杠、双引号；换行折叠为空格）。"""
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def _assemble_yaml(name: str, yaml_flow: str) -> str:
    """回收 flow 片段 → 完整 Midscene tasks 文档（与操作台保存格式一致）。"""
    return "\n".join(["tasks:", f'  - name: "{_yaml_dq(name)}"', "    flow:", yaml_flow])


async def _resolve_vision_model(user_id: int) -> dict:
    """发起人默认 VISION 配置 → Agent model 参数（family 必填，同回放图）。"""
    from app.crud.auth.user_llm_config import crud_user_llm_config
    from app.models.auth.user_llm_config import ModelType

    async with async_session_maker() as db:
        cfg = await crud_user_llm_config.get_default(
            db, user_id=user_id, model_type=ModelType.VISION
        )
    if cfg is None or not cfg.is_active:
        raise ValueError("未配置视觉（VISION）模型，无法探索")
    if not cfg.base_url or not cfg.model_family:
        raise ValueError(
            "VISION 模型缺少 Base URL 或 model_family（Midscene 兼容家族），无法探索"
        )
    return {
        "name": cfg.model,
        "base_url": cfg.base_url,
        "api_key": cfg.api_key,
        "family": cfg.model_family,
    }


async def _ask_json_array(user_id: int, prompt: str, max_items: int) -> list[str]:
    """TEXT 模型问答，约定只回 JSON 字符串数组（宽松解析）。

    不用 with_structured_output（部分 OpenAI 兼容 provider 不支持 tool/json schema），
    纯 prompt + 正则提取，任何 chat 模型都可用。缺配置/失败一律返回空——调用方
    自己决定回退行为（增益项不阻塞主流程）。
    """
    import json as _json
    import logging
    import re

    from app.ai_core.llm_client import build_llm_from_config
    from app.crud.auth.user_llm_config import crud_user_llm_config
    from app.models.auth.user_llm_config import ModelType

    logger = logging.getLogger(__name__)

    async with async_session_maker() as db:
        cfg = await crud_user_llm_config.get_default(
            db, user_id=user_id, model_type=ModelType.TEXT
        )
    if cfg is None or not cfg.is_active:
        return []
    try:
        llm = build_llm_from_config(cfg)
        resp = await llm.ainvoke(prompt)
        text_out = getattr(resp, "content", None) or str(resp)
        if isinstance(text_out, list):  # 多模态 content 块拍平
            text_out = " ".join(str(b) for b in text_out)
        match = re.search(r"\[.*\]", text_out, re.S)
        if not match:
            logger.warning("TEXT 问答：模型输出不含 JSON 数组：%.200s", text_out)
            return []
        arr = _json.loads(match.group(0))
        return [str(a).strip().replace("\n", " ") for a in arr if str(a).strip()][:max_items]
    except Exception as exc:  # noqa: BLE001
        logger.warning("TEXT 问答失败（忽略）：%s", exc)
        return []


async def _suggest_asserts(user_id: int, goal: str, steps: list, summary: str) -> list[str]:
    """TEXT 模型建议 1-3 条 aiAssert（缺配置/失败一律返回空——建议失败不改探索结论）。"""
    lines = [f"{i + 1}. {_step_brief(s)}" for i, s in enumerate(steps)]
    prompt = (
        "你是移动端 UI 测试专家。AI 刚按自然语言目标在 Android 真机上探索完成了一段操作，"
        "请给出 1-3 条可直接用于 Midscene aiAssert 的自然语言断言，用于回放时验证目标达成"
        "后的界面状态。要求：只描述界面上可见、可视觉判定的具体状态；不要复述操作动作本身；"
        "每条一句话。\n\n"
        f"探索目标：{goal}\n"
        f"动作序列：\n" + "\n".join(lines) + "\n"
        f"执行总结：{summary or '（无）'}\n\n"
        '只输出一个 JSON 字符串数组（1-3 条），例如 ["页面顶部显示\\"网络和互联网\\"标题"]，'
        "不要输出任何其他文字。"
    )
    return await _ask_json_array(user_id, prompt, max_items=3)


# 分段探索上限：8 段 × 每段 12 轮 ≈ 96 动作容量；每段独立 RPC 各享 300s
_MAX_SEGMENTS = 8


async def _decompose_goal(user_id: int, goal: str, app_hint: str) -> list[str]:
    """复杂目标 → 顺序执行段（1-8 句）。

    单次 aiAct 受"重规划轮数 × 单 RPC 300s"双重上限约束，复杂目标必须分段：
    每段一次 aiAct（独立轮数预算 + 独立 RPC 超时），段间设备状态自然衔接。
    缺 TEXT 配置 / 解析失败 → 回退单段（等价旧行为，探索不因此失败）。
    """
    prompt = (
        "你是移动端 UI 自动化专家。请把下面的探索目标分解为可在 Android 设备上"
        "顺序执行的操作段：每段是一句自然语言指令，包含 1-4 个具体连贯的操作，"
        "将直接交给视觉自动化 Agent 逐段执行（上一段结束的界面就是下一段的起点，"
        "不要重复铺垫）。\n"
        "分段判据（必须遵守）：目标涉及多个应用、或多个相互独立的界面目的地"
        "（出现「然后」「再」「接着」等衔接词通常就是段边界），必须按里程碑分段，"
        "每段结束于一个明确可见的界面状态；仅当目标只在单一应用内且约 4 个连续"
        "操作以内，才返回单段原文。\n"
        '例：目标「打开设置进入网络页，然后回到桌面打开时钟」→ '
        '["打开设置，进入\\"网络和互联网\\"页面", "回到桌面，打开时钟应用"]\n\n'
        f"探索目标：{goal}\n"
        + (f"应用上下文：{app_hint}\n" if app_hint else "")
        + f'\n只输出一个 JSON 字符串数组（1-{_MAX_SEGMENTS} 段），不要输出任何其他文字。'
    )
    segments = await _ask_json_array(user_id, prompt, max_items=_MAX_SEGMENTS)
    segments = [s for s in segments if len(s) >= 2]
    return segments or [goal]


def build_graph(params: dict, ctx: TaskContext) -> Any:
    from langgraph.graph import END, START, StateGraph

    async def _raced_rpc(
        agent_id: int, udid: str, session_id: str, cmd: str, rpc_params: dict
    ) -> tuple[Optional[dict], bool, Optional[str]]:
        """RPC + 取消轮询(2s) + 锁续期(10s) + 进度直播转 SSE。返回 (result, cancelled, error)。

        直播：每个轮询节拍顺带 get_app_step_progress 增量拉 Agent 侧执行进度
        （大模型每轮规划原话+tokens/定位/动作），ctx.log 转进统一事件流——
        探索/验证长 RPC 期间前端不再黑盒等待。best-effort，拉不到不影响执行。
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
                    {"session_id": session_id, "after_seq": progress_seq},
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
            call_agent_rpc(agent_id, cmd, rpc_params, timeout_ms=EXPLORE_RPC_TIMEOUT_MS)
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
                ctx.log("收到取消请求，正在停止设备侧执行…", level="warning")
                for c in ("abort_app_flow", "end_app_session"):
                    try:
                        await call_agent_rpc(
                            agent_id, c, {"session_id": session_id}, timeout_ms=10_000
                        )
                    except (AgentRpcError, GatewayRpcError):
                        pass
                rpc_task.cancel()
                return None, True, "用户取消"
        # 收尾补拉：RPC 已结束，缓冲里可能还剩没拉走的尾行（"步骤完成，回收 N 个动作"）
        await _pump_progress(timeout_ms=5_000)
        try:
            return await rpc_task, False, None
        except (AgentRpcError, GatewayRpcError) as exc:
            return None, False, str(exc)

    async def run(state: ExploreAppScriptState) -> dict:
        from app.crud.app_device.device import crud_app_device
        from app.crud.app_test import crud_app_execution, crud_app_script
        # 报告分块拉取/模型补记复用回放图实现（同包内）
        from app.ai_core.graphs.app_test.run_app_script import (
            _fetch_report,
            _record_ai_model,
        )
        from app.services.app_device.gateway_rpc import (
            AgentRpcError,
            GatewayRpcError,
            call_agent_rpc,
        )
        from app.services.app_device.lock import device_lock

        udid = state["device_udid"]
        goal = state["goal"].strip()
        verify = state.get("verify", True)
        want_asserts = state.get("suggest_asserts", True)
        cycle_limit = max(4, min(20, state.get("cycle_limit") or _DEFAULT_CYCLE_LIMIT))
        session_id = f"explore-{ctx.task_id}"

        # ── 1/5 准备：设备 / 模型 ──
        ctx.stage("准备探索", index=1, total=5)
        ctx.progress(5)
        async with async_session_maker() as db:
            device = await crud_app_device.get_by_udid(db, udid)
            if device is None:
                raise ValueError(f"设备不存在：{udid}")
            agent_id, serial = device.agent_id, device.serial
            device_platform = device.platform or "android"
        model = await _resolve_vision_model(ctx.user_id)
        await _record_ai_model(ctx.task_id, model.get("name"))
        ctx.log(f"探索目标：{goal}")
        ctx.log(f"设备 {udid} · 重规划上限 {cycle_limit} 轮")

        # ── 抢锁 / 同用户接管（kind=record，探索本质是一次录制会话）──
        acquired, holder = await device_lock.acquire(udid, ctx.user_id, session_id, "record")
        if not acquired and holder and holder.get("owner_user_id") == ctx.user_id:
            acquired = await device_lock.takeover(udid, ctx.user_id, session_id, "record")
            if acquired:
                ctx.log(
                    "已接管你在该设备上的既有会话（投屏控制会断开，探索期间设备独占）",
                    level="warning",
                )
        if not acquired:
            owner = (holder or {}).get("owner_user_id")
            raise ValueError(f"设备被占用（用户 #{owner}），无法探索")

        started = time.monotonic()
        script_id: Optional[int] = None
        execution_id: Optional[int] = None
        verify_status: Optional[str] = None
        asserts: list[str] = []
        error_msg: Optional[str] = None
        cancelled = False
        try:
            # ── 2/5 探索执行（分段：复杂目标先分解，逐段 aiAct）──
            # 单段受"重规划轮数 × 单 RPC 300s"双重上限，分段后每段独享预算：
            # 8 段 × 12 轮 ≈ 96 动作容量。段间设备状态自然衔接，仅首段回桌面锚定。
            ctx.stage("自动探索", index=2, total=5)
            ctx.progress(12)
            segments = await _decompose_goal(ctx.user_id, goal, state.get("app_hint") or "")
            if len(segments) > 1:
                ctx.log(f"目标分解为 {len(segments)} 段顺序执行：")
                for i, seg in enumerate(segments):
                    ctx.log(f"  {i + 1}. {seg}")

            steps: list = []
            flow_parts: list[str] = []
            dedup_flow_parts: list[str] = []
            dedup_steps: list = []
            had_dedup = False
            summaries: list[str] = []
            segment_failed = False
            for i, seg in enumerate(segments):
                if len(segments) > 1:
                    ctx.log(f"── 第 {i + 1}/{len(segments)} 段：{seg}")
                ctx.progress(12 + int(43 * i / len(segments)))
                step_params = {
                    "serial": serial,
                    "session_id": session_id,
                    "instruction": seg,
                    "model": model,
                    "replanning_cycle_limit": cycle_limit,
                    # 起点锚定只在首段：段间界面必须自然衔接，中途回桌面会毁掉流程
                    "press_home": i == 0,
                }
                if state.get("app_hint"):
                    step_params["act_context"] = state["app_hint"]
                result, cancelled, seg_error = await _raced_rpc(
                    agent_id, udid, session_id, "run_app_step", step_params
                )
                if cancelled:
                    return {"error": seg_error, "steps_count": len(steps), "asserts": []}
                if result is None or result.get("status") != "ok":
                    seg_error = str(
                        seg_error or (result or {}).get("error") or "未知错误"
                    )
                    if not steps:
                        raise RuntimeError(f"探索执行失败：{seg_error}")
                    # 部分成功：保住已回收段落存草稿，跳过验证（目标未完整达成）
                    error_msg = (
                        f"第 {i + 1}/{len(segments)} 段执行失败：{seg_error}"
                        f"（前 {len(steps)} 步已保留为草稿）"
                    )
                    ctx.log(error_msg, level="warning")
                    segment_failed = True
                    break
                seg_steps: list = result.get("steps") or []
                if not seg_steps:
                    # 该段无动作可回收（如目标状态已满足），不算失败
                    ctx.log("该段未回收到动作（可能状态已满足），继续下一段")
                    continue
                steps.extend(seg_steps)
                flow_parts.append(str(result.get("yaml_flow") or ""))
                dd_flow = result.get("yaml_flow_deduped")
                dedup_flow_parts.append(str(dd_flow or result.get("yaml_flow") or ""))
                dedup_steps.extend(result.get("steps_deduped") or seg_steps)
                had_dedup = had_dedup or bool(dd_flow)
                if result.get("summary"):
                    summaries.append(str(result.get("summary")))

            yaml_flow = "\n".join(p for p in flow_parts if p)
            summary = " / ".join(summaries)
            if not steps or not yaml_flow:
                raise RuntimeError("探索完成但未回收到任何可回放动作，请换个更具体的目标重试")
            if summary:
                ctx.log(f"模型总结：{summary[:300]}")
            ctx.log(f"共回收 {len(steps)} 个即时动作：")
            for i, s in enumerate(steps):
                ctx.log(f"  {i + 1}. {_step_brief(s)}")

            # ── 3/5 沉淀用例（先存 draft，验证通过再转 active）──
            ctx.stage("沉淀用例", index=3, total=5)
            ctx.progress(55)
            name = (state.get("script_name") or "").strip() or f"探索-{goal[:24]}"
            yaml_content = _assemble_yaml(name, yaml_flow)
            async with async_session_maker() as db:
                script = await crud_app_script.create(
                    db,
                    project_id=ctx.project_id,
                    name=name,
                    yaml_content=yaml_content,
                    platform=device_platform,
                    target_app=state.get("app_hint") or None,
                    description=f"探索式生成 · 目标：{goal}",
                    status="draft",
                    created_by=ctx.user_id,
                )
                script_id = script.id
            ctx.log(f"用例「{name}」已保存（#{script_id}，草稿）")

            # ── 4/5 回放验证（同会话 runYaml；执行记录 = 报告锚点）──
            ctx.stage("回放验证", index=4, total=5)
            ctx.progress(65)
            async with async_session_maker() as db:
                execution = await crud_app_execution.create(
                    db,
                    script_id=script_id,
                    device_udid=udid,
                    ai_task_id=str(ctx.task_id),
                    status="running",
                )
                execution_id = execution.id
            if segment_failed:
                verify_status = "failed"
                ctx.log("目标未完整达成，跳过回放验证（部分草稿可手工补全后回放）")
            elif verify:
                async def _verify_once(yaml_text: str):
                    return await _raced_rpc(
                        agent_id,
                        udid,
                        session_id,
                        "run_app_yaml",
                        # press_home：探索把设备停在目标页，验证必须回桌面从头跑（联调实证）
                        {"serial": serial, "session_id": session_id,
                         "yaml": yaml_text, "model": model, "press_home": True},
                    )

                v_result, cancelled, v_error = await _verify_once(yaml_content)
                # 自愈重验：失败且存在去重候选（相邻全等步折叠，跨段合并）→ 用去重版
                # 再验一次。判据=真实回放结果：冗余场景重验通过（转正并落去重版），
                # 必要重复场景重验仍失败（保草稿），零误伤（裁决见 recover.ts）。
                yaml_flow_deduped = "\n".join(p for p in dedup_flow_parts if p) if had_dedup else None
                if (
                    not cancelled
                    and (v_result is None or v_result.get("status") != "ok")
                    and yaml_flow_deduped
                ):
                    first_error = v_error or str((v_result or {}).get("error") or "回放失败")
                    ctx.log(
                        f"回放验证失败：{first_error}",
                        level="warning",
                    )
                    ctx.log("检测到疑似重规划冗余步，用去重版自愈重验一次…")
                    yaml_v2 = _assemble_yaml(name, yaml_flow_deduped)
                    v_result, cancelled, v_error = await _verify_once(yaml_v2)
                    if not cancelled and v_result is not None and v_result.get("status") == "ok":
                        steps = dedup_steps or steps
                        yaml_content = yaml_v2
                        async with async_session_maker() as db:
                            script = await crud_app_script.get_in_project(
                                db, ctx.project_id, script_id
                            )
                            if script is not None:
                                await crud_app_script.update(
                                    db, script, {"yaml_content": yaml_content}
                                )
                        ctx.log(f"自愈生效：去除冗余步后共 {len(steps)} 步，已更新用例")
                if cancelled:
                    verify_status = "cancelled"
                    error_msg = v_error
                elif v_result is not None and v_result.get("status") == "ok":
                    verify_status = "success"
                    ctx.log("回放验证通过，用例转为 active")
                    async with async_session_maker() as db:
                        script = await crud_app_script.get_in_project(
                            db, ctx.project_id, script_id
                        )
                        if script is not None:
                            await crud_app_script.update(db, script, {"status": "active"})
                else:
                    verify_status = "failed"
                    error_msg = v_error or str((v_result or {}).get("error") or "回放失败")
                    ctx.log(f"回放验证失败（用例保留草稿）：{error_msg}", level="warning")
            else:
                verify_status = "skipped"
                ctx.log("已按选项跳过回放验证（用例保留草稿，可在用例库手动回放）")

            # 报告（探索 + 验证同一会话累积在一份报告里；失败也取，含失败现场）
            report_path = await _fetch_report(agent_id, session_id, execution_id)
            duration_ms = int((time.monotonic() - started) * 1000)
            exec_status = {
                "success": "success",
                "skipped": "success",
                "cancelled": "cancelled",
            }.get(verify_status or "", "failed")
            async with async_session_maker() as db:
                execution = await crud_app_execution.get(db, execution_id)
                if execution is not None:
                    await crud_app_execution.update(
                        db,
                        execution,
                        {
                            "status": exec_status,
                            "steps_summary": {
                                "mode": "explore",
                                "goal": goal,
                                "segments": segments,
                                "steps": steps,
                                "verify_status": verify_status,
                                "error": error_msg,
                                "session_id": session_id,
                            },
                            "report_path": report_path,
                            "duration_ms": duration_ms,
                        },
                    )
            if cancelled:
                return {
                    "script_id": script_id,
                    "execution_id": execution_id,
                    "steps_count": len(steps),
                    "verify_status": verify_status,
                    "asserts": [],
                    "error": error_msg,
                }

            # ── 5/5 断言建议（TEXT 模型，增益项；注释行追加进 YAML）──
            ctx.stage("断言建议", index=5, total=5)
            ctx.progress(90)
            if want_asserts:
                asserts = await _suggest_asserts(ctx.user_id, goal, steps, summary)
                if asserts:
                    comment = ["", "# ―― AI 建议断言（人工确认后去掉行首「# 」启用）――"]
                    comment += [f'#      - aiAssert: "{_yaml_dq(a)}"' for a in asserts]
                    async with async_session_maker() as db:
                        script = await crud_app_script.get_in_project(
                            db, ctx.project_id, script_id
                        )
                        if script is not None:
                            await crud_app_script.update(
                                db,
                                script,
                                {"yaml_content": script.yaml_content + "\n" + "\n".join(comment)},
                            )
                    for a in asserts:
                        ctx.log(f"建议断言：{a}")
                else:
                    ctx.log("未获得断言建议（未配置文本模型或模型无输出），跳过")
            else:
                ctx.log("已按选项跳过断言建议")

            ctx.progress(100)
            ctx.log(f"探索完成：用例 #{script_id} · {len(steps)} 步 · 验证 {verify_status}")
            return {
                "script_id": script_id,
                "execution_id": execution_id,
                "steps_count": len(steps),
                "verify_status": verify_status,
                "asserts": asserts,
                "error": error_msg,
            }
        finally:
            # 无条件收尾：end_app_session（dispose + 清 Agent 侧内存 modelConfig，幂等）+ 释放锁
            try:
                await call_agent_rpc(
                    agent_id, "end_app_session", {"session_id": session_id}, timeout_ms=15_000
                )
            except (AgentRpcError, GatewayRpcError):
                pass
            try:
                await device_lock.release(udid, session_id)
            except Exception:  # noqa: BLE001
                pass

    graph = StateGraph(ExploreAppScriptState)
    graph.add_node("run", run)
    graph.add_edge(START, "run")
    graph.add_edge("run", END)
    return graph.compile()


def _extract_result(final_state: dict) -> tuple[Optional[dict], Optional[dict]]:
    summary = {
        "script_id": final_state.get("script_id"),
        "execution_id": final_state.get("execution_id"),
        "steps_count": final_state.get("steps_count"),
        "verify_status": final_state.get("verify_status"),
        "asserts": final_state.get("asserts"),
        "error": final_state.get("error"),
    }
    ref = {"kind": "app_script", "script_id": final_state.get("script_id")}
    return summary, ref


register(
    TaskSpec(
        task_type="explore_app_script",
        build_graph=build_graph,
        build_input=lambda params: {
            "device_udid": params["device_udid"],
            "goal": params["goal"],
            "script_name": params.get("script_name") or "",
            "app_hint": params.get("app_hint") or "",
            "verify": bool(params.get("verify", True)),
            "suggest_asserts": bool(params.get("suggest_asserts", True)),
            "cycle_limit": int(params.get("cycle_limit") or _DEFAULT_CYCLE_LIMIT),
        },
        title=lambda params: f"App 探索生成：{str(params.get('goal') or '')[:30]}",
        llm_kind="none",  # VISION 在图内直读（Agent 侧持内存态）；TEXT 惰性加载可缺省
        extract_result=_extract_result,
        kind="app_exec",  # → app_tasks 独立队列（长持设备，不挤 ai/exec 槽位）
        stream_messages=False,
        adapter_cancel=False,  # 图内协作式取消（abort 帧到真机），禁硬中断跳过收尾
    )
)
