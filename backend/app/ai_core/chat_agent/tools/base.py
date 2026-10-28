"""助手工具公共辅助

约定：
  - 工具一律返回 JSON 字符串（ensure_ascii=False），顶层可带 "_action" 字段，
    orchestrator 在 on_tool_end 时取出，前端渲染为可点击的动作卡片。
  - _action 结构：{"kind": "navigate", "route_name", "params", "label"}
    route_name/params 为前端 vue-router 命名路由（params 不含项目 id，前端补）。
  - 所有查数工具自行做 project_id 确权与软删过滤（crud 不带过滤的需手动比对）。
"""

import json
from typing import Any, Optional
from app.ai_core.chat_agent.agent_context import get_agent_context

PAGE_MAP: dict[str, tuple[str, str]] = {
    "overview": ("ProjectOverview", "项目概览"),
    "requirements": ("FuncTestRequirements", "需求管理"),
    "func_cases": ("FuncTestCases", "功能用例"),
    "api_report": ("ApiReport", "接口测试报表"),
    "bugs": ("ProjectBugs", "缺陷管理"),
    "reports": ("ProjectReports", "执行汇总报表"),
    "report_assets": ("ReportAssets", "测试资产报表"),
    "report_quality": ("ReportQuality", "缺陷质量报表"),
    "report_ai": ("ReportAi", "AI 提效报表"),
    "scheduled_jobs": ("ScheduledJobs", "定时任务"),
    "task_center": ("AiTaskCenter", "任务中心"),
    "knowledge": ("KnowledgeDocuments", "知识库"),
    "environments": ("Environments", "测试环境"),
    "members": ("ProjectMembers", "项目成员"),
    "app_cases": ("AppCases", "App 用例库"),
    "app_suites": ("AppSuites", "App 测试套件"),
    "app_executions": ("AppExecutions", "App 执行记录"),
    "app_devices": ("AppDevices", "设备管理"),
}


def tool_json(data: dict | list, *, action: Optional[dict] = None) -> str:
    """序列化工具结果；action 非空时附加 _action 供前端渲染动作卡片"""
    if action is not None:
        if isinstance(data, list):
            data = {"items": data}
        data = {**data, "_action": action}
    return json.dumps(data, ensure_ascii=False, default=str)


def tool_error(message: str) -> str:
    return json.dumps({"error": message}, ensure_ascii=False)


def navigate_action(route_name: str, label: str, params: Optional[dict] = None) -> dict:
    return {
        "kind": "navigate",
        "route_name": route_name,
        "params": params or {},
        "label": label,
    }


def task_action(ai_task_id: int, label: str = "查看任务进度") -> dict:
    """任务中心详情页动作卡片（执行/生成派发后必带）"""
    return navigate_action("AiTaskDetail", label, {"taskId": ai_task_id})


def clip(text: Any, limit: int = 200) -> Optional[str]:
    """长文本裁剪（列表场景防 token 爆炸）"""
    if text is None:
        return None
    s = str(text)
    return s if len(s) <= limit else s[:limit] + "…"


DEFAULT_PAGE_SIZE = 50


def page_bounds(page: Any, size: int = DEFAULT_PAGE_SIZE) -> tuple[int, int]:
    """1-based 页码 → (skip, limit)。page 缺省/非法一律按第 1 页处理。"""
    try:
        p = int(page)
    except (TypeError, ValueError):
        p = 1
    if p < 1:
        p = 1
    return ((p - 1) * size, size)


def paged_result(
    total: int, items: list, *, page: Any = 1, size: int = DEFAULT_PAGE_SIZE, **extra
) -> dict:
    """列表工具的标准分页返回体。

    total 是全量条数（与页码无关的 COUNT），items 是本页数据。除 total/items 外
    还给出 page/page_size/shown；当本页之后仍有数据时补 has_more/next_page/hint，
    明确告诉模型「用 page=N 继续翻，或用 keyword 精确搜索收窄」——否则模型只看到
    前 50 条却当成全部（这是"只能查到前 50 条"的根因）。extra 塞 kind 等附加字段。
    """
    try:
        p = int(page)
    except (TypeError, ValueError):
        p = 1
    if p < 1:
        p = 1
    has_more = (p - 1) * size + len(items) < total
    out: dict = {
        "total": total,
        "page": p,
        "page_size": size,
        "shown": len(items),
        "items": items,
        **extra,
    }
    if has_more:
        out["has_more"] = True
        out["next_page"] = p + 1
        out["hint"] = (
            f"共 {total} 条，这是第 {p} 页（每页 {size}）；还有更多未显示——用 page={p + 1} 继续翻页，或用 keyword 精确搜索收窄结果"
        )
    return out


def ctx_ids() -> tuple[int, int]:
    """(project_id, user_id)"""
    ctx = get_agent_context()
    return (ctx.project_id, ctx.user_id)


async def check_environment(db, environment_id: int, project_id: int):
    """校验执行环境：存在、未删、本项目或全局。返回 env 或 None"""
    from app.crud.test_environment import environment as crud_env

    env = await crud_env.get_with_variables(db, env_id=environment_id)
    if not env or getattr(env, "is_deleted", False):
        return None
    if not env.is_global and env.project_id != project_id:
        return None
    return env


async def submit_unified_task(
    db,
    *,
    project_id: int,
    user_id: int,
    task_type: str,
    biz_ref_type: str,
    biz_ref_id: int,
    title: str,
    input_params: dict,
    device_udid: Optional[str] = None,
    precreate=None,
    compensate=None,
) -> dict:
    """统一任务提交六步模式（与平台执行端点同序）：
    提交锁 → 活跃去重（含僵尸回收）→ precreate 预创建业务执行记录
    → 建 ai_task → 投递 → 失败补偿。

    precreate(db) 在锁内、去重通过后才调用——锁占用/去重命中时业务记录
    根本不会被创建（端点零残留口径）；其返回 dict 会合入 input_params。
    投递失败时回调 compensate(db) 把已预创建的业务记录标失败。
    返回 {ok: True, ai_task_id, extra} 或 {ok: False, error, [ai_task_id]}。
    """
    from app.ai_core.runtime import event_bus, registry as task_registry
    from app.core.config import settings
    from app.crud.ai.ai_task import crud_ai_task
    from app.tasks.ai_task import safe_dispatch

    spec = task_registry.get(task_type)
    dedupe = spec.dedupe if spec is not None else True
    lock_key = f"{project_id}:{task_type}:{biz_ref_id}"
    if not await event_bus.acquire_submit_lock(lock_key):
        return {"ok": False, "error": "该目标正在提交执行，请稍后重试"}
    try:
        if dedupe:
            existing = await crud_ai_task.find_active(
                db,
                project_id=project_id,
                task_type=task_type,
                biz_ref_id=biz_ref_id,
                device_udid=device_udid,
            )
            if existing:
                revived = await crud_ai_task.fail_if_zombie(
                    db, task=existing, timeout_s=settings.AI_TASK_ZOMBIE_TIMEOUT_S
                )
                if not revived:
                    return {
                        "ok": False,
                        "error": f"该目标已有进行中的任务（任务 #{existing.id}），不能重复执行",
                        "ai_task_id": existing.id,
                    }
                from app.services.ai_task_finalize import finalize_biz_records

                await finalize_biz_records(db, existing, canceled=False)
        extra: dict = {}
        if precreate is not None:
            extra = await precreate(db) or {}
            input_params = {**input_params, **extra}
        task = await crud_ai_task.create(
            db,
            project_id=project_id,
            created_by=user_id,
            task_type=task_type,
            title=title,
            input_params=input_params,
            biz_ref_type=biz_ref_type,
            biz_ref_id=biz_ref_id,
        )
        await db.commit()
        async_result = safe_dispatch(task_type, task.id)
        if async_result is None:
            await crud_ai_task.set_failed(
                db, task_id=task.id, error_message="任务投递失败（broker 不可用）"
            )
            if compensate is not None:
                try:
                    await compensate(db)
                except Exception:
                    pass
            await db.commit()
            return {"ok": False, "error": "任务投递失败，请检查 Celery/Redis 服务"}
        try:
            await crud_ai_task.set_celery_task_id(
                db, task_id=task.id, celery_task_id=async_result.id
            )
        except Exception:
            pass
        return {"ok": True, "ai_task_id": task.id, "extra": extra}
    finally:
        await event_bus.release_submit_lock(lock_key)
