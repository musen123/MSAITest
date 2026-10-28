"""管理/创建类工具（写库操作，调用前须确认用户意图与参数完整）

- create_bug：创建缺陷（含审计历史，与端点同口径）
- review_func_cases：批量评审功能用例（approve/reject）
- generate_func_cases：派发后台 AI 生成任务
"""

from typing import Optional
from langchain.tools import tool
from app.ai_core.chat_agent.tools.base import (
    ctx_ids,
    navigate_action,
    submit_unified_task,
    task_action,
    tool_error,
    tool_json,
)
from app.db.session import async_session_maker

BUG_SEVERITIES = ("critical", "major", "moderate", "minor", "trivial")
BUG_PRIORITIES = ("urgent", "high", "medium", "low")


@tool(
    "create_bug",
    description="在当前项目创建一个缺陷。必填：title（标题）、description（缺陷描述）、severity（critical=致命/major=严重/moderate=中等/minor=轻微/trivial=微不足道）、priority（urgent/high/medium/low）。可选：reproduction_steps（复现步骤）、expected_result（预期结果）、actual_result（实际结果）、environment（环境说明）。调用前必须与用户确认标题和严重程度。",
)
async def create_bug(
    title: str,
    description: str,
    severity: str,
    priority: str,
    reproduction_steps: Optional[str] = None,
    expected_result: Optional[str] = None,
    actual_result: Optional[str] = None,
    environment: Optional[str] = None,
) -> str:
    from app.crud.bug.bug import crud_bug
    from app.crud.bug.bug_history import crud_bug_history

    if severity not in BUG_SEVERITIES:
        return tool_error(f"severity 仅支持：{'/'.join(BUG_SEVERITIES)}")
    if priority not in BUG_PRIORITIES:
        return tool_error(f"priority 仅支持：{'/'.join(BUG_PRIORITIES)}")
    title = (title or "").strip()
    if not title or not (description or "").strip():
        return tool_error("title 和 description 不能为空")
    project_id, user_id = ctx_ids()
    async with async_session_maker() as db:
        bug = await crud_bug.create(
            db,
            project_id=project_id,
            created_by=user_id,
            title=title[:255],
            description=description,
            severity=severity,
            priority=priority,
            environment=environment or None,
            reproduction_steps=reproduction_steps or None,
            expected_result=expected_result or None,
            actual_result=actual_result or None,
        )
        await crud_bug_history.create(
            db, bug_id=bug.id, action="created", operated_by=user_id
        )
    return tool_json(
        {
            "created": True,
            "id": bug.id,
            "bug_key": bug.bug_key,
            "title": bug.title,
            "status": bug.status,
        },
        action=navigate_action("ProjectBugs", "打开缺陷管理"),
    )


@tool(
    "review_func_cases",
    description="批量评审功能测试用例（仅草稿/待评审状态可评审）。参数：case_ids（用例 ID 列表，1~200 个）、action（approve=通过 / reject=驳回）、review_comment（评审意见，驳回时建议填写）。调用前必须与用户确认评审结论。",
)
async def review_func_cases(
    case_ids: list[int], action: str, review_comment: Optional[str] = None
) -> str:
    from app.crud.func_test.test_case import crud_test_case

    if action not in ("approve", "reject"):
        return tool_error("action 仅支持 approve / reject")
    ids = list(dict.fromkeys((int(i) for i in case_ids or [] if int(i) > 0)))
    if not ids or len(ids) > 200:
        return tool_error("case_ids 需要 1~200 个用例 ID")
    comment = (review_comment or "").strip()[:500] or None
    project_id, user_id = ctx_ids()
    async with async_session_maker() as db:
        processed = await crud_test_case.batch_review(
            db,
            project_id=project_id,
            case_ids=ids,
            action=action,
            reviewer_id=user_id,
            review_comment=comment,
        )
    skipped = len(ids) - processed
    return tool_json(
        {
            "processed": processed,
            "skipped": skipped,
            "result": "已通过" if action == "approve" else "已驳回",
            "note": (
                f"{skipped} 条被跳过（非草稿/待评审状态或不属于本项目）"
                if skipped
                else None
            ),
        },
        action=navigate_action("FuncTestCases", "打开用例列表"),
    )


@tool(
    "generate_func_cases",
    description="为某个需求派发 AI 用例生成后台任务（生成→评审→覆盖率检查→保存全流程，在任务中心实时查看）。参数：requirement（需求 ID 或编号）。",
)
async def generate_func_cases(requirement: str) -> str:
    from app.ai_core.chat_agent.tools.query_tools import _resolve_requirement

    project_id, user_id = ctx_ids()
    async with async_session_maker() as db:
        req = await _resolve_requirement(db, project_id, requirement)
        if not req:
            return tool_error(f"需求不存在：{requirement}")
        sub = await submit_unified_task(
            db,
            project_id=project_id,
            user_id=user_id,
            task_type="generate_case",
            biz_ref_type="requirement",
            biz_ref_id=req.id,
            title=f"用例生成：{req.title}",
            input_params={"requirement_id": req.id, "requirement_title": req.title},
        )
    if not sub["ok"]:
        return tool_error(sub["error"])
    return tool_json(
        {
            "dispatched": True,
            "requirement": {"id": req.id, "code": req.code, "title": req.title},
            "ai_task_id": sub["ai_task_id"],
            "message": "用例生成任务已派发，完成后用例会以草稿状态保存",
        },
        action=task_action(sub["ai_task_id"], "查看生成进度"),
    )


@tool(
    "extract_requirements",
    description="AI 需求盘点：扫描本项目知识库的**全部文档**，把散落在多个文档里的需求批量提取为结构化草稿（跨文档合并同一需求、单独上传的原型图自动挂靠），已存在的需求自动跳过（可重复执行做增量盘点）。后台任务，任务中心看进度。适用：「把文档里的需求都盘出来」「批量提取需求」。无参数。",
)
async def extract_requirements() -> str:
    project_id, user_id = ctx_ids()
    async with async_session_maker() as db:
        sub = await submit_unified_task(
            db,
            project_id=project_id,
            user_id=user_id,
            task_type="extract_requirements",
            biz_ref_type="project",
            biz_ref_id=project_id,
            title="AI 需求盘点",
            input_params={"project_id": project_id},
        )
    if not sub["ok"]:
        return tool_error(sub["error"])
    return tool_json(
        {
            "dispatched": True,
            "ai_task_id": sub["ai_task_id"],
            "message": "需求盘点任务已派发：全库扫描→跨文档合并→逐条结构化→以草稿落库（已存在的自动跳过）",
        },
        action=task_action(sub["ai_task_id"], "查看盘点进度"),
    )
