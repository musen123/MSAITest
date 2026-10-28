"""数据查询类工具（只读，免确认）

覆盖：项目概况 / 需求 / 功能用例 / 缺陷 /
环境 / 定时计划 / AI 任务 / 执行汇总报表 / 知识库。
所有列表限量返回（防 token 爆炸），并附带 total 提示还有多少。
"""

import json
from typing import Optional
from langchain.tools import tool
from app.ai_core.chat_agent.tools.base import (
    clip,
    ctx_ids,
    navigate_action,
    page_bounds,
    paged_result,
    tool_error,
    tool_json,
)
from app.db.session import async_session_maker

LIST_LIMIT = 50
_PAGE_HINT = "可选 page（页码，从 1 开始，每页 50 条；返回里 has_more=true 时用 next_page 的值继续取更多，数据量大时优先用 keyword 收窄）。"


async def _resolve_requirement(db, project_id: int, ident: str):
    """把"ID 或编号"解析成需求 ORM 对象（限本项目）"""
    from sqlalchemy import select
    from app.crud.func_test.requirement import crud_requirement
    from app.models.func_test.requirement import TestRequirement

    ident = str(ident).strip()
    if not ident:
        return None
    if ident.isdigit():
        req = await crud_requirement.get(db, int(ident))
        if req and req.project_id == project_id:
            return req
        return None
    stmt = select(TestRequirement).where(
        TestRequirement.project_id == project_id,
        TestRequirement.code == ident,
        TestRequirement.is_deleted == False,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


@tool(
    "get_project_overview",
    description="查询当前项目的需求、功能用例和缺陷统计概况。无参数。",
)
async def get_project_overview() -> str:
    from app.services.project.module_stats_service import MODULES, get_module_stats

    project_id, _ = ctx_ids()
    out = {}
    async with async_session_maker() as db:
        for m in MODULES:
            out[m] = await get_module_stats(db, project_id=project_id, module=m)
    return tool_json(out)


@tool(
    "query_requirements",
    description="查询当前项目的功能需求列表。可选参数：keyword（标题模糊搜索）、status（draft/pending_review/reviewed/published/deprecated）。"
    + _PAGE_HINT,
)
async def query_requirements(
    keyword: Optional[str] = None, status: Optional[str] = None, page: int = 1
) -> str:
    from app.crud.func_test.requirement import crud_requirement

    project_id, _ = ctx_ids()
    skip, limit = page_bounds(page)
    async with async_session_maker() as db:
        reqs, total = await crud_requirement.get_by_project(
            db,
            project_id=project_id,
            status=status or None,
            keyword=keyword or None,
            skip=skip,
            limit=limit,
        )
    items = [
        {
            "id": r.id,
            "code": r.code,
            "title": r.title,
            "status": r.status,
            "priority": r.priority,
            "source": r.source,
        }
        for r in reqs
    ]
    return tool_json(paged_result(total, items, page=page))


@tool(
    "get_requirement_detail",
    description="按需求 ID 或编号查询需求详情（描述、验收标准、AI 理解结果）。参数：requirement（ID 或编号，如 5 或 REQ-1-0001）",
)
async def get_requirement_detail(requirement: str) -> str:
    project_id, _ = ctx_ids()
    async with async_session_maker() as db:
        req = await _resolve_requirement(db, project_id, requirement)
        if not req:
            return tool_error(f"需求不存在：{requirement}")
        data = {
            "id": req.id,
            "code": req.code,
            "title": req.title,
            "description": req.description,
            "acceptance_criteria": req.acceptance_criteria,
            "understood_content": clip(req.understood_content, 2000),
            "priority": req.priority,
            "status": req.status,
        }
    return tool_json(
        data,
        action=navigate_action(
            "FuncTestRequirementDetail", "打开需求详情", {"reqId": req.id}
        ),
    )


@tool(
    "query_func_cases",
    description="查询当前项目的功能测试用例列表。可选参数：keyword（标题/编号模糊）、status（draft/pending_review/reviewed/deprecated）、requirement（需求 ID 或编号，查某需求下的用例）。"
    + _PAGE_HINT,
)
async def query_func_cases(
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    requirement: Optional[str] = None,
    page: int = 1,
) -> str:
    from app.crud.func_test.test_case import crud_test_case

    project_id, _ = ctx_ids()
    skip, limit = page_bounds(page)
    async with async_session_maker() as db:
        requirement_id = None
        if requirement:
            req = await _resolve_requirement(db, project_id, requirement)
            if not req:
                return tool_error(f"需求不存在：{requirement}")
            requirement_id = req.id
        cases, total = await crud_test_case.get_by_project(
            db,
            project_id=project_id,
            requirement_id=requirement_id,
            status=status or None,
            keyword=keyword or None,
            skip=skip,
            limit=limit,
        )
    items = [
        {
            "id": c.id,
            "code": c.code,
            "title": c.title,
            "status": c.status,
            "priority": c.priority,
            "source": c.source,
        }
        for c in cases
    ]
    return tool_json(paged_result(total, items, page=page))


@tool(
    "query_bugs",
    description="查询当前项目的缺陷列表。可选参数：status（new/assigned/in_progress/resolved/verified/reopened/closed/postponed/wontfix）、severity（critical/major/moderate/minor/trivial）、keyword（标题模糊）。"
    + _PAGE_HINT,
)
async def query_bugs(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = 1,
) -> str:
    from app.crud.bug.bug import crud_bug

    project_id, _ = ctx_ids()
    skip, limit = page_bounds(page)
    async with async_session_maker() as db:
        bugs, total = await crud_bug.get_list(
            db,
            project_id=project_id,
            status=status or None,
            severity=severity or None,
            priority=None,
            assigned_to=None,
            module_id=None,
            created_by=None,
            keyword=keyword or None,
            skip=skip,
            limit=limit,
        )
        items = [
            {
                "id": b.id,
                "bug_key": b.bug_key,
                "title": b.title,
                "status": b.status,
                "severity": b.severity,
                "priority": b.priority,
                "assignee": (
                    b.assignee.real_name or b.assignee.username if b.assignee else None
                ),
            }
            for b in bugs
        ]
    return tool_json(paged_result(total, items, page=page))


@tool(
    "query_environments",
    description="查询当前项目可用的测试环境列表（含全局环境）。执行测试前用它确认 environment_id。"
    + _PAGE_HINT,
)
async def query_environments(page: int = 1) -> str:
    from app.crud.test_environment import environment as crud_env

    project_id, _ = ctx_ids()
    skip, limit = page_bounds(page)
    async with async_session_maker() as db:
        envs, total = await crud_env.get_multi_by_project(
            db, project_id=project_id, skip=skip, limit=limit
        )
    items = [
        {
            "id": e.id,
            "name": e.name,
            "base_url": getattr(e, "base_url", None),
            "is_default": getattr(e, "is_default", False),
            "is_global": getattr(e, "is_global", False),
        }
        for e in envs
    ]
    return tool_json(paged_result(total, items, page=page))


@tool(
    "query_scheduled_jobs",
    description="查询当前项目的定时任务计划列表（类型、目标、调度规则、启停状态、下次运行时间）。"
    + _PAGE_HINT,
)
async def query_scheduled_jobs(page: int = 1) -> str:
    from app.crud.scheduler.scheduled_job import crud_scheduled_job

    project_id, _ = ctx_ids()
    skip, limit = page_bounds(page)
    async with async_session_maker() as db:
        jobs, total = await crud_scheduled_job.list_by_project(
            db, project_id=project_id, skip=skip, limit=limit
        )
    items = [
        {
            "id": j.id,
            "name": j.name,
            "job_type": j.job_type,
            "target_id": j.target_id,
            "schedule": (
                j.cron_expr
                if j.schedule_type == "cron"
                else f"每 {j.interval_seconds}s"
            ),
            "enabled": j.enabled,
            "next_run_at_utc": j.next_run_at,
            "last_status": j.last_status,
            "total_runs": j.total_runs,
        }
        for j in jobs
    ]
    return tool_json(
        paged_result(total, items, page=page),
        action=navigate_action("ScheduledJobs", "打开定时任务页"),
    )


@tool(
    "query_ai_tasks",
    description="查询任务中心的任务列表（AI 生成任务与测试执行任务）。可选参数：kind（ai=生成类 / exec=执行类）、status（pending/running/succeeded/failed/canceled）。按创建时间倒序，每页 20 条；可选 page 翻页看更早的任务（返回 has_more=true 时用 next_page）。",
)
async def query_ai_tasks(
    kind: Optional[str] = None, status: Optional[str] = None, page: int = 1
) -> str:
    from app.ai_core.runtime import registry as task_registry
    from app.crud.ai.ai_task import crud_ai_task

    project_id, _ = ctx_ids()
    if status:
        status = {"completed": "succeeded", "cancelled": "canceled"}.get(status, status)
    exec_types = frozenset(task_registry.exec_task_types())
    task_types = exclude = None
    if kind == "exec":
        task_types = exec_types
    elif kind == "ai":
        exclude = exec_types
    skip, limit = page_bounds(page, size=20)
    async with async_session_maker() as db:
        tasks, total = await crud_ai_task.list_by_project(
            db,
            project_id=project_id,
            task_types=task_types,
            exclude_task_types=exclude,
            status=status or None,
            skip=skip,
            limit=limit,
        )
    items = [
        {
            "id": t.id,
            "task_type": t.task_type,
            "title": t.title,
            "status": t.status,
            "progress": t.progress,
            "created_at": t.created_at,
            "error_message": clip(t.error_message, 150),
        }
        for t in tasks
    ]
    return tool_json(
        paged_result(total, items, page=page, size=20),
        action=navigate_action("AiTaskCenter", "打开任务中心"),
    )


@tool(
    "get_execution_report",
    description="查询项目执行汇总报表：执行次数、通过率、功能测试与 App 自动化对比、执行人排行、失败重灾用例。参数：days（统计窗口天数，默认 30）。",
)
async def get_execution_report(days: int = 30) -> str:
    from app.services.project.report_center_service import (
        get_execution_report as svc_report,
    )

    project_id, _ = ctx_ids()
    days = days if days in (7, 14, 30, 90) else 30
    async with async_session_maker() as db:
        data = await svc_report(db, project_id=project_id, days=days)
    slim = {
        "days": days,
        "cards": data.get("cards"),
        "modules": data.get("modules"),
        "result_dist": data.get("result_dist"),
        "executor_rank": (data.get("executor_rank") or [])[:5],
        "top_failures": (data.get("top_failures") or [])[:5],
    }
    return tool_json(slim, action=navigate_action("ProjectReports", "打开执行汇总报表"))


@tool(
    "kb_search",
    description="从本项目知识库检索文档片段（需求说明、表结构、接口规范、业务规则等知识性问题），返回带来源标注的原文片段（[n]《文档》› 章节），由你综合后回答并保留引用编号。仅检索当前项目，结果天然隔离。参数：query（必须是**自包含**的完整问句——多轮对话里先把『它的超时呢』这类指代改写成完整问题再调用）；doc_types（可选，按类型过滤：requirement/api_doc/design/test_case/bug_review/meeting/other）",
)
async def kb_search(query: str, doc_types: Optional[list[str]] = None) -> str:
    """自研混合检索（向量+全文 RRF）：本地 service 直调，P95 <1s，
    不再有 LightRAG 120s 超时卡死整轮对话的风险。project_id 从会话
    上下文注入，LLM 无法指定他项目（防注入越权）。"""
    from app.services.knowledge import retrieval_service

    project_id, user_id = ctx_ids()
    try:
        async with async_session_maker() as db:
            data = await retrieval_service.search(
                db,
                project_id=project_id,
                query=query,
                top_k=6,
                doc_types=doc_types,
                prefer_user_id=user_id,
                consumer="chat",
            )
    except Exception as exc:
        return tool_error(f"知识库检索失败：{exc}")
    if not data.hits:
        hint = "知识库暂无相关内容"
        if data.degraded.vector:
            hint += "（向量检索降级中，仅全文匹配）"
        return json.dumps(
            {"result": hint, "suggest": "可提示用户到「项目知识库」上传相关文档"},
            ensure_ascii=False,
        )
    context = retrieval_service.format_hits_for_llm(data.hits)
    if data.degraded.vector:
        context = "（注：向量检索降级，以下为全文匹配结果）\n" + context
    return context


@tool(
    "query_kb_graph",
    description="查询知识图谱里某个实体的结构化事实：类型、描述、邻接关系（它与哪些模块/接口/规则/数据对象相关联及关系动词）、以及来源出处（在哪些文档的哪些章节被提及）。适合回答『下单流程涉及哪些接口和规则』『优惠券模块关联什么』这类**关系型/影响面**问题——比 kb_search 返回散落片段更精准，给的是从文档自动抽取并去重的实体关系网。参数：entity（实体名，如『订单模块』『创建订单』『优惠券抵扣计算』，支持模糊匹配取最相关一个）。仅查当前项目，结果天然隔离。",
)
async def query_kb_graph(entity: str) -> str:
    """图谱实体详情：本地 graph_service 直调，返回实体+邻接关系+文档溯源。
    project_id 从会话上下文注入（防越权指定他项目）。"""
    from app.crud.knowledge.graph import crud_kb_graph
    from app.services.knowledge import graph_service

    project_id, _ = ctx_ids()
    kw = (entity or "").strip()
    if len(kw) < 2:
        return tool_error("实体名至少 2 个字")
    try:
        async with async_session_maker() as db:
            matches = await crud_kb_graph.search_entities(
                db, project_id=project_id, keyword=kw, limit=1
            )
            if not matches:
                return tool_json(
                    {
                        "found": False,
                        "message": f"图谱中未找到与「{kw}」匹配的实体",
                        "suggest": "换个说法，或提示用户先在「项目文档」提取图谱",
                    }
                )
            detail = await graph_service.get_entity_detail(
                db, project_id=project_id, entity_id=matches[0].id
            )
    except Exception as exc:
        return tool_error(f"图谱查询失败：{exc}")
    relations = [
        {
            "关系": f"{r.get('source_name')} {r.get('keywords') or '相关'} {r.get('target_name')}"
        }
        for r in (detail.get("relations") or [])[:30]
    ]
    mentions = [
        {"文档": m.get("doc_name"), "章节": clip(m.get("heading_path") or "", 80)}
        for m in (detail.get("mentions") or [])[:10]
    ]
    return tool_json(
        {
            "found": True,
            "entity": detail.get("name"),
            "type": detail.get("entity_type"),
            "description": clip(detail.get("description") or "", 300),
            "ref_count": detail.get("ref_count"),
            "relations": relations,
            "relations_total": len(detail.get("relations") or []),
            "sources": mentions,
            "message": "以上为该实体的关系网与来源出处，可据此回答关系型问题",
        }
    )


@tool(
    "analyze_change_impact",
    description="变更影响分析：当某个模块/接口/规则/数据对象发生变更时，沿知识图谱关系边推演受影响面，并给出**建议回归的功能用例清单**。回答『改了 XX 要回归哪些用例』『XX 变更会影响什么』这类问题。链路：变更实体 → 图谱 1-hop 邻域（受影响实体）→ 提及这些实体的需求 → 需求关联的用例。参数：entity（发生变更的对象名，如『创建订单』『优惠券抵扣计算』『支付回调』）。仅查当前项目。",
)
async def analyze_change_impact(entity: str) -> str:
    """变更影响分析：本地 graph_service 直调。实体↔用例经需求文本启发式桥接
    （非精确映射，结果供参考）。project_id 从会话上下文注入。"""
    from app.crud.knowledge.graph import crud_kb_graph
    from app.services.knowledge import graph_service

    project_id, _ = ctx_ids()
    kw = (entity or "").strip()
    if len(kw) < 2:
        return tool_error("变更对象名至少 2 个字")
    try:
        async with async_session_maker() as db:
            matches = await crud_kb_graph.search_entities(
                db, project_id=project_id, keyword=kw, limit=1
            )
            if not matches:
                return tool_json(
                    {
                        "found": False,
                        "message": f"图谱中未找到与「{kw}」匹配的实体，无法分析影响面",
                        "suggest": "确认对象名，或先在「项目文档」提取图谱",
                    }
                )
            res = await graph_service.analyze_change_impact(
                db, project_id=project_id, entity_id=matches[0].id, hops=1
            )
    except Exception as exc:
        return tool_error(f"变更影响分析失败：{exc}")
    return tool_json(
        {
            "found": True,
            "changed": res["seed"]["name"],
            "impacted_entities": res["impacted_entities"],
            "impacted_requirements": [
                {"title": r["title"]} for r in res["impacted_requirements"]
            ],
            "regression_cases": [
                {"code": c["code"], "title": c["title"], "priority": c["priority"]}
                for c in res["regression_cases"][:30]
            ],
            "regression_case_count": res["regression_case_count"],
            "note": "回归清单经『需求文本提及实体』启发式关联，供参考；无命中用例可能是该影响面下暂无关联用例",
        }
    )
