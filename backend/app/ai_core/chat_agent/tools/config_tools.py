"""平台配置 / 管理类补充工具

覆盖已部分接入的域里缺的「写」与「查」：
  - 定时计划：create_scheduled_job / update_scheduled_job（直连写；查询/触发/启停
    已在 query_tools / exec_tools）
  - 测试环境：create_environment / update_environment（直连写，走 EnvironmentService；
    查询已有 query_environments）
  - 知识库：kb_ingest_text（把一段文本入库，派发 kb_ingest 任务；检索已有 kb_search）
  - 成员：query_members（只读）

删除类（删环境/删计划）与项目/成员的增改属破坏性或管理操作，不做工具，由 open_page
引导到对应页面。
"""

from typing import Optional
from langchain.tools import tool
from app.ai_core.chat_agent.tools.base import (
    ctx_ids,
    navigate_action,
    task_action,
    tool_error,
    tool_json,
)
from app.db.session import async_session_maker

LIST_LIMIT = 50
_JOB_TYPES = {"app_suite"}


@tool(
    "create_scheduled_job",
    description="创建一个定时任务计划。参数：name（计划名）、job_type（要定时执行的任务类型：app_suite）、target_id（对应任务/套件/场景/计划的 ID）、schedule_type（cron 或 interval）；cron 需 cron_expr（如「0 2 * * *」每天 2 点），interval 需 interval_seconds（≥60）；可选 enabled（默认 true）。",
)
async def create_scheduled_job(
    name: str,
    job_type: str,
    target_id: int,
    schedule_type: str,
    cron_expr: Optional[str] = None,
    interval_seconds: Optional[int] = None,
    environment_id: Optional[int] = None,
    enabled: bool = True,
) -> str:
    from app.models.scheduler.scheduled_job import ScheduledJob
    from app.services.scheduler.scheduled_job_service import compute_next_run

    project_id, user_id = ctx_ids()
    name = (name or "").strip()
    job_type = (job_type or "").strip()
    schedule_type = (schedule_type or "").strip().lower()
    if not name:
        return tool_error("计划名 name 不能为空")
    if job_type not in _JOB_TYPES:
        return tool_error(f"job_type 仅支持：{' / '.join(sorted(_JOB_TYPES))}")
    if schedule_type == "cron":
        if not cron_expr:
            return tool_error(
                "schedule_type=cron 时必须提供 cron_expr（如「0 2 * * *」）"
            )
    elif schedule_type == "interval":
        if not interval_seconds or interval_seconds < 60:
            return tool_error("schedule_type=interval 时 interval_seconds 必须 ≥60")
    else:
        return tool_error("schedule_type 仅支持 cron / interval")
    params: Optional[dict] = None
    if environment_id is not None:
        if job_type in ():
            params = {"environment_id": environment_id}
        elif job_type in ():
            params = {"perf_environment_id": environment_id}
    async with async_session_maker() as db:
        job = ScheduledJob(
            project_id=project_id,
            name=name,
            job_type=job_type,
            target_id=target_id,
            params=params,
            schedule_type=schedule_type,
            cron_expr=cron_expr,
            interval_seconds=interval_seconds,
            enabled=bool(enabled),
            allow_overlap=False,
            created_by=user_id,
        )
        if enabled:
            job.next_run_at = compute_next_run(
                schedule_type=schedule_type,
                cron_expr=cron_expr,
                interval_seconds=interval_seconds,
            )
        db.add(job)
        await db.commit()
        await db.refresh(job)
    return tool_json(
        {
            "created": True,
            "id": job.id,
            "name": job.name,
            "job_type": job.job_type,
            "enabled": job.enabled,
            "next_run_at_utc": job.next_run_at,
            "message": "定时计划已创建"
            + ("（已启用，将按计划触发）" if enabled else "（未启用）"),
        },
        action=navigate_action("ScheduledJobs", "打开定时任务页"),
    )


@tool(
    "update_scheduled_job",
    description="编辑一个定时任务计划。参数：job_id（计划 ID）；可选 name、schedule_type（cron/interval）、cron_expr、interval_seconds（≥60）、enabled、description。改动调度或启停会自动重算下次运行时间。仅启停可直接用 toggle_scheduled_job。",
)
async def update_scheduled_job(
    job_id: int,
    name: Optional[str] = None,
    schedule_type: Optional[str] = None,
    cron_expr: Optional[str] = None,
    interval_seconds: Optional[int] = None,
    enabled: Optional[bool] = None,
    description: Optional[str] = None,
) -> str:
    from app.crud.scheduler.scheduled_job import crud_scheduled_job
    from app.services.scheduler.scheduled_job_service import compute_next_run

    project_id, _ = ctx_ids()
    async with async_session_maker() as db:
        job = await crud_scheduled_job.get(db, job_id)
        if not job or job.project_id != project_id:
            return tool_error(f"定时计划不存在：{job_id}")
        update: dict = {}
        for key, val in (
            ("name", name),
            ("description", description),
            ("schedule_type", schedule_type),
            ("cron_expr", cron_expr),
            ("interval_seconds", interval_seconds),
            ("enabled", enabled),
        ):
            if val is not None:
                update[key] = val
        if not update:
            return tool_error("未提供任何要更新的字段")
        job = await crud_scheduled_job.update_fields(db, job=job, **update)
        if any(
            (
                k in update
                for k in ("schedule_type", "cron_expr", "interval_seconds", "enabled")
            )
        ):
            job = await crud_scheduled_job.update_fields(
                db,
                job=job,
                next_run_at=(
                    compute_next_run(
                        schedule_type=job.schedule_type,
                        cron_expr=job.cron_expr,
                        interval_seconds=job.interval_seconds,
                    )
                    if job.enabled
                    else None
                ),
            )
    return tool_json(
        {
            "updated": True,
            "id": job.id,
            "name": job.name,
            "enabled": job.enabled,
            "next_run_at_utc": job.next_run_at,
            "message": "定时计划已更新",
        }
    )


@tool(
    "create_environment",
    description="创建一个测试环境。参数：name（环境名）、base_url（环境基础 URL，须以 http:// 或 https:// 开头）；可选 description。创建后可在执行接口/Web 测试时选用。",
)
async def create_environment(
    name: str, base_url: str, description: Optional[str] = None
) -> str:
    from pydantic import ValidationError
    from app.schemas.test_environment.environment import EnvironmentCreate
    from app.services.test_environment.environment_service import EnvironmentService

    project_id, _ = ctx_ids()
    try:
        obj_in = EnvironmentCreate(
            name=(name or "").strip(),
            base_url=(base_url or "").strip(),
            description=description,
        )
    except ValidationError as exc:
        msg = exc.errors()[0].get("msg", str(exc)) if exc.errors() else str(exc)
        return tool_error(f"参数无效：{msg}")
    async with async_session_maker() as db:
        try:
            env = await EnvironmentService.create_environment(
                db, obj_in=obj_in, project_id=project_id
            )
        except Exception as exc:
            return tool_error(f"创建失败：{getattr(exc, 'message', exc)}")
    return tool_json(
        {
            "created": True,
            "id": env.id,
            "name": env.name,
            "base_url": env.base_url,
            "message": "测试环境已创建",
        },
        action=navigate_action("Environments", "打开测试环境页"),
    )


@tool(
    "update_environment",
    description="编辑一个测试环境。参数：env_id（环境 ID）；可选 name、base_url（http/https）、description。只能改本项目的环境（全局环境请到环境页编辑）。",
)
async def update_environment(
    env_id: int,
    name: Optional[str] = None,
    base_url: Optional[str] = None,
    description: Optional[str] = None,
) -> str:
    from pydantic import ValidationError
    from app.crud.test_environment import environment as crud_env
    from app.schemas.test_environment.environment import EnvironmentUpdate
    from app.services.test_environment.environment_service import EnvironmentService

    project_id, _ = ctx_ids()
    fields = {
        k: v
        for (k, v) in (
            ("name", name),
            ("base_url", base_url),
            ("description", description),
        )
        if v is not None
    }
    if not fields:
        return tool_error("未提供任何要更新的字段")
    try:
        obj_in = EnvironmentUpdate(**fields)
    except ValidationError as exc:
        msg = exc.errors()[0].get("msg", str(exc)) if exc.errors() else str(exc)
        return tool_error(f"参数无效：{msg}")
    async with async_session_maker() as db:
        env = await crud_env.get_with_variables(db, env_id=env_id)
        if not env or getattr(env, "is_deleted", False) or env.project_id != project_id:
            return tool_error(f"测试环境不存在或不属于本项目：{env_id}")
        try:
            env = await EnvironmentService.update_environment(
                db, db_obj=env, obj_in=obj_in
            )
        except Exception as exc:
            return tool_error(f"更新失败：{getattr(exc, 'message', exc)}")
    return tool_json(
        {
            "updated": True,
            "id": env.id,
            "name": env.name,
            "base_url": env.base_url,
            "message": "测试环境已更新",
        }
    )


@tool(
    "kb_ingest_text",
    description="把一段文本内容入库到本项目知识库（分块+向量化，完成后即可被 kb_search 检索）。参数：title（文档标题）、content（正文文本）；可选 doc_type（requirement / api_doc / design / test_case / bug_review / meeting / other）。适合把说明/规则/会议纪要等沉淀进知识库；上传文件请到知识库页操作。",
)
async def kb_ingest_text(
    title: str, content: str, doc_type: Optional[str] = None
) -> str:
    from app.services.knowledge.knowledge_service import insert_text_to_kb

    project_id, user_id = ctx_ids()
    title = (title or "").strip()
    content = (content or "").strip()
    if not title or not content:
        return tool_error("title 和 content 均不能为空")
    async with async_session_maker() as db:
        try:
            doc, task_id = await insert_text_to_kb(
                db,
                project_id=project_id,
                title=title,
                content=content,
                uploaded_by=user_id,
                doc_type=doc_type,
            )
        except Exception as exc:
            return tool_error(f"入库失败：{getattr(exc, 'message', exc)}")
    data = {
        "ingested": True,
        "document_id": getattr(doc, "id", None),
        "title": title,
        "ai_task_id": task_id,
        "message": "已提交知识库入库，完成后即可被 kb_search 检索到",
    }
    if task_id:
        return tool_json(data, action=task_action(int(task_id), "查看入库进度"))
    return tool_json(data)


@tool(
    "query_members",
    description="查询当前项目的成员列表（用户名、姓名、项目角色）。无参数。",
)
async def query_members() -> str:
    from app.crud.project.member import project_member

    project_id, _ = ctx_ids()
    async with async_session_maker() as db:
        members = await project_member.get_members_by_project(db, project_id=project_id)
    items = []
    for m in members:
        user = getattr(m, "user", None)
        items.append(
            {
                "user_id": m.user_id,
                "username": (
                    getattr(user, "username", None)
                    if user
                    else getattr(m, "username", None)
                ),
                "real_name": (
                    getattr(user, "real_name", None)
                    if user
                    else getattr(m, "real_name", None)
                ),
                "project_role": getattr(m, "project_role", None)
                or getattr(getattr(m, "role", None), "code", None),
            }
        )
    return tool_json(
        {"total": len(items), "items": items},
        action=navigate_action("ProjectMembers", "打开项目成员页"),
    )
