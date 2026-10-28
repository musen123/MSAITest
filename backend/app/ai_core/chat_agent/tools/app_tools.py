"""App 自动化类工具（安卓 / 鸿蒙 / iOS 真机）

分两类：
  - 查询（只读）：query_app_assets（用例/套件/执行记录）、query_app_devices（接入设备）
  - 执行（产生真机回放/探索，须确认用户意图）：run_app_case / run_app_suite / explore_app

写操作全部复用平台执行端点的提交语义：
  - run_app_case / run_app_suite 走 base.submit_unified_task（六步：提交锁→设备维度去重
    →预创建执行记录→建统一任务→投递→失败补偿），device_udid 传入使「同一用例可在不同
    设备并行、同设备重复提交仍拦」，与 App 执行端点一致。
  - explore_app 无单一业务对象可去重（新建用例），并发由 Agent 侧 Redis 设备锁串行化，
    故内联最小提交（镜像 /app/automation/explore 端点），不走去重路径。

设备的「占用/手动触控操作台」属有副作用的直接控制，不做成工具——用 open_page 引导到
设备管理页由用户自行操作。删除用例同理（引导到 App 用例库）。
"""

from typing import Optional

from langchain.tools import tool

from app.ai_core.chat_agent.tools.base import (
    ctx_ids,
    navigate_action,
    page_bounds,
    paged_result,
    submit_unified_task,
    task_action,
    tool_error,
    tool_json,
)
from app.db.session import async_session_maker

LIST_LIMIT = 50

# 列表工具通用翻页说明（拼进 description）
_PAGE_HINT = (
    "可选 page（页码，从 1 开始，每页 50 条；返回里 has_more=true 时用 "
    "next_page 的值继续取更多，数据量大时优先用 keyword 收窄）。"
)


# ============================================================================
# 查询（只读，免确认）
# ============================================================================
@tool(
    "query_app_assets",
    description=(
        "查询 App 自动化资产。参数：kind（cases=App 用例 / suites=测试套件 / "
        "executions=执行记录）；可选 keyword 模糊搜索。回放用例/套件前先用 "
        "kind=cases 或 kind=suites 查到目标 ID。" + _PAGE_HINT
    ),
)
async def query_app_assets(
    kind: str, keyword: Optional[str] = None, page: int = 1
) -> str:
    project_id, _ = ctx_ids()
    kind = (kind or "").strip().lower()
    skip, limit = page_bounds(page)
    async with async_session_maker() as db:
        if kind == "cases":
            from app.crud.app_test.script import crud_app_script

            rows, total = await crud_app_script.get_list(
                db, project_id, keyword=keyword or None, skip=skip, limit=limit
            )
            items = [
                {
                    "id": r.id,
                    "name": r.name,
                    "platform": r.platform,
                    "status": getattr(r, "status", None),
                }
                for r in rows
            ]
        elif kind == "suites":
            from app.crud.app_test.suite import crud_app_suite

            rows, total = await crud_app_suite.get_list(
                db, project_id, keyword=keyword or None, skip=skip, limit=limit
            )
            items = [
                {
                    "id": s.id,
                    "name": s.name,
                    "case_count": cnt,
                    "device_udid": getattr(s, "device_udid", None),
                }
                for s, cnt in rows
            ]
        elif kind == "executions":
            from app.crud.app_test.execution import crud_app_execution

            rows, total = await crud_app_execution.get_list(
                db, project_id, skip=skip, limit=limit
            )
            items = [
                {
                    "id": e.id,
                    "script_name": sname,
                    "platform": splat,
                    "device_model": dmodel,
                    "status": e.status,
                    "created_at": e.created_at,
                }
                for e, sname, splat, dmodel, _dplat in rows
            ]
        else:
            return tool_error("kind 仅支持 cases / suites / executions")
    return tool_json(paged_result(total, items, page=page, kind=kind))


@tool(
    "query_app_devices",
    description=(
        "查询接入平台的移动设备列表（安卓/鸿蒙/iOS 真机或模拟器，含平台、型号、"
        "在线状态）。回放 App 用例前用它确认可用的 device_udid（online=true 才能跑）。"
        + _PAGE_HINT
    ),
)
async def query_app_devices(page: int = 1) -> str:
    from app.crud.app_device.device import crud_app_device

    ctx_ids()  # 确权：仅项目工作区内可用
    skip, limit = page_bounds(page)
    async with async_session_maker() as db:
        rows, total = await crud_app_device.get_list(db, skip=skip, limit=limit)
    items = [
        {
            "udid": d.udid,
            "model": d.model,
            "brand": getattr(d, "brand", None),
            "platform": d.platform,
            "state": d.state,
            "online": d.state == "device",
            "resolution": getattr(d, "resolution", None),
        }
        for d in rows
    ]
    return tool_json(
        paged_result(total, items, page=page),
        action=navigate_action("AppDevices", "打开设备管理"),
    )


# ============================================================================
# 执行（产生真实真机回放/探索，调用前须确认用户意图明确）
# ============================================================================
async def _resolve_online_device(db, udid: str):
    """按 udid 取设备并校验在线（state=='device'）。返回 (device, error_str)。"""
    from app.crud.app_device.device import crud_app_device

    device = await crud_app_device.get_by_udid(db, udid)
    if not device:
        return None, f"设备不存在：{udid}，请用 query_app_devices 查看可用设备"
    if device.state != "device":
        return None, f"设备当前不可用（状态 {device.state}），请确认设备已连接并在线"
    return device, None


@tool(
    "run_app_case",
    description=(
        "回放一个 App 测试用例到指定真机（异步，立即返回任务链接，可在任务中心实时"
        "观看设备画面）。参数：script_id（App 用例 ID，用 query_app_assets kind=cases "
        "查）、device_udid（目标设备，用 query_app_devices 查，需 online）。用例平台须与"
        "设备平台一致。"
    ),
)
async def run_app_case(script_id: int, device_udid: str) -> str:
    from app.crud.app_test.execution import crud_app_execution
    from app.crud.app_test.script import crud_app_script

    project_id, user_id = ctx_ids()
    device_udid = (device_udid or "").strip()
    state: dict = {}
    async with async_session_maker() as db:
        script = await crud_app_script.get(db, script_id)
        if not script or script.project_id != project_id:
            return tool_error(f"App 用例不存在：{script_id}")
        device, err = await _resolve_online_device(db, device_udid)
        if err:
            return tool_error(err)
        if (
            script.platform
            and device.platform
            and script.platform != device.platform
        ):
            return tool_error(
                f"用例平台（{script.platform}）与设备平台（{device.platform}）"
                "不一致，请选择匹配平台的设备"
            )
        device_platform = device.platform or "android"

        async def precreate(db_):
            execution = await crud_app_execution.create(
                db_, script_id=script_id, device_udid=device_udid, status="pending"
            )
            await db_.commit()
            state["execution"] = execution
            state["execution_id"] = execution.id
            return {"execution_id": execution.id}

        async def compensate(db_):
            exe = state.get("execution")
            if exe is not None:
                await crud_app_execution.update(db_, exe, {"status": "failed"})

        try:
            sub = await submit_unified_task(
                db,
                project_id=project_id,
                user_id=user_id,
                task_type="run_app_script",
                biz_ref_type="app_script",
                biz_ref_id=script_id,
                title=f"App 回放：{script.name}",
                input_params={
                    "script_id": script_id,
                    "device_udid": device_udid,
                    "platform": device_platform,
                    "script_name": script.name,
                },
                device_udid=device_udid,
                precreate=precreate,
                compensate=compensate,
            )
        except Exception as exc:  # noqa: BLE001
            return tool_error(f"无法执行：{getattr(exc, 'message', exc)}")
    if not sub["ok"]:
        return tool_error(sub["error"])
    return tool_json(
        {
            "dispatched": True,
            "script_name": script.name,
            "device": device.model or device_udid,
            "ai_task_id": sub["ai_task_id"],
            "execution_id": state.get("execution_id"),
            "message": "已开始回放，可在任务中心实时观看设备画面与进度",
        },
        action=task_action(sub["ai_task_id"], "查看回放进度"),
    )


@tool(
    "run_app_suite",
    description=(
        "回放一个 App 测试套件（批量执行套件内用例，异步）。参数：suite_id（套件 ID，用 "
        "query_app_assets kind=suites 查）；可选 device_udid（缺省用套件绑定的默认设备，"
        "都没有则报错）。设备需 online。"
    ),
)
async def run_app_suite(suite_id: int, device_udid: Optional[str] = None) -> str:
    from app.crud.app_test.suite import crud_app_suite, crud_app_suite_execution

    project_id, user_id = ctx_ids()
    state: dict = {}
    async with async_session_maker() as db:
        suite = await crud_app_suite.get(db, suite_id)
        if not suite or suite.project_id != project_id:
            return tool_error(f"App 套件不存在：{suite_id}")
        udid = (device_udid or "").strip() or (suite.device_udid or "")
        if not udid:
            return tool_error(
                "该套件未绑定默认设备，请指定 device_udid（用 query_app_devices 查）"
            )
        device, err = await _resolve_online_device(db, udid)
        if err:
            return tool_error(err)
        device_platform = device.platform or "android"

        async def precreate(db_):
            execution = await crud_app_suite_execution.create(
                db_,
                suite_id=suite_id,
                project_id=project_id,
                device_udid=udid,
                trigger_type="manual",
                status="pending",
                created_by=user_id,
            )
            await db_.commit()
            state["execution"] = execution
            state["execution_id"] = execution.id
            return {"suite_execution_id": execution.id}

        async def compensate(db_):
            exe = state.get("execution")
            if exe is not None:
                await crud_app_suite_execution.update(
                    db_, exe, {"status": "failed"}
                )

        try:
            sub = await submit_unified_task(
                db,
                project_id=project_id,
                user_id=user_id,
                task_type="run_app_suite",
                biz_ref_type="app_suite",
                biz_ref_id=suite_id,
                title=f"App 套件执行：{suite.name}",
                input_params={
                    "suite_id": suite_id,
                    "device_udid": udid,
                    "platform": device_platform,
                    "suite_name": suite.name,
                    "trigger_type": "manual",
                },
                device_udid=udid,
                precreate=precreate,
                compensate=compensate,
            )
        except Exception as exc:  # noqa: BLE001
            return tool_error(f"无法执行：{getattr(exc, 'message', exc)}")
    if not sub["ok"]:
        return tool_error(sub["error"])
    return tool_json(
        {
            "dispatched": True,
            "suite_name": suite.name,
            "device": device.model or udid,
            "ai_task_id": sub["ai_task_id"],
            "execution_id": state.get("execution_id"),
            "message": "已开始批量回放，可在任务中心实时查看进度",
        },
        action=task_action(sub["ai_task_id"], "查看执行进度"),
    )


@tool(
    "explore_app",
    description=(
        "让 AI 在真机上自主探索并生成一条 App 用例（异步，探索完成后自动沉淀为可复用"
        "用例）。参数：goal（要完成的操作目标，至少 4 字，越具体越好，如「打开设置搜索"
        "蓝牙并开启」）、device_udid（目标设备，需 online）；可选 script_name（生成用例的"
        "命名）、app_hint（被测 App 的包名/说明，帮助更快定位）。"
    ),
)
async def explore_app(
    goal: str,
    device_udid: str,
    script_name: Optional[str] = None,
    app_hint: Optional[str] = None,
) -> str:
    from app.crud.ai.ai_task import crud_ai_task
    from app.tasks.ai_task import safe_dispatch

    project_id, user_id = ctx_ids()
    goal = (goal or "").strip()
    device_udid = (device_udid or "").strip()
    if len(goal) < 4:
        return tool_error("探索目标 goal 至少 4 个字符，请更具体地描述要完成的操作")
    async with async_session_maker() as db:
        device, err = await _resolve_online_device(db, device_udid)
        if err:
            return tool_error(err)
        # 无单一业务对象可去重（新建用例），并发由 Agent 侧 Redis 设备锁串行化，
        # 故内联最小提交，镜像 /app/automation/explore 端点，不走 find_active 去重。
        task = await crud_ai_task.create(
            db,
            project_id=project_id,
            created_by=user_id,
            task_type="explore_app_script",
            title=f"App 探索生成：{goal[:30]}",
            input_params={
                "device_udid": device_udid,
                "platform": device.platform or "android",
                "goal": goal,
                "script_name": (script_name or "").strip(),
                "app_hint": (app_hint or "").strip(),
                "verify": True,
                "suggest_asserts": True,
            },
            biz_ref_type="app_explore",
        )
        await db.commit()
        async_result = safe_dispatch("explore_app_script", task.id)
        if async_result is None:
            await crud_ai_task.set_failed(
                db, task_id=task.id, error_message="任务投递失败（broker 不可用）"
            )
            await db.commit()
            return tool_error("任务投递失败，请检查 Celery/Redis 服务")
        try:
            await crud_ai_task.set_celery_task_id(
                db, task_id=task.id, celery_task_id=async_result.id
            )
        except Exception:  # noqa: BLE001
            pass
    return tool_json(
        {
            "dispatched": True,
            "goal": goal,
            "device": device.model or device_udid,
            "ai_task_id": task.id,
            "message": "已开始 AI 探索，可在任务中心实时观看设备画面与推理过程，"
            "完成后会自动生成用例",
        },
        action=task_action(task.id, "查看探索进度"),
    )
