"""
Bug AI 智能分析 API 端点

处理 AI 分析任务的触发、状态查询和结果获取。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.response import ResponseModel
from app.crud.bug.bug import crud_bug
from app.crud.bug.bug_ai_analysis import crud_bug_ai_analysis
from app.models.auth.user import User
from app.schemas.bug.bug_ai_analysis import (
    AiAnalysisResponse,
    AiAnalysisStatusResponse,
    AiAnalysisTrigger,
)
from app.utils.project_permission import require_project_access

router = APIRouter()


@router.post(
    "/{bug_id}/ai-analysis",
    summary="触发 AI 分析",
    response_model=ResponseModel,
)
async def trigger_ai_analysis(
    project_id: int,
    bug_id: int,
    body: AiAnalysisTrigger = AiAnalysisTrigger(),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.require_permission("bug:view")),
) -> ResponseModel:
    """
    触发 Bug AI 智能分析。

    若已存在分析记录则覆盖重新分析。
    当前为同步占位实现，后续接入 AI 服务后可改为异步任务。
    """
    await require_project_access(db, project_id, current_user.id)
    bug = await crud_bug.get_active(db, bug_id, project_id)
    if not bug:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bug 不存在")

    analysis = await crud_bug_ai_analysis.create_or_reset(db, bug_id=bug_id)

    return ResponseModel(
        message="AI 分析已触发",
        data={
            "analysis_id": analysis.analysis_id,
            "status": analysis.analysis_status,
        },
    )


@router.get(
    "/{bug_id}/ai-analysis/status",
    summary="查询 AI 分析状态",
    response_model=ResponseModel[AiAnalysisStatusResponse],
)
async def get_ai_analysis_status(
    project_id: int,
    bug_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.require_permission("bug:view")),
) -> ResponseModel[AiAnalysisStatusResponse]:
    """查询 Bug AI 分析的当前状态。"""
    await require_project_access(db, project_id, current_user.id)
    bug = await crud_bug.get_active(db, bug_id, project_id)
    if not bug:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bug 不存在")

    analysis = await crud_bug_ai_analysis.get_by_bug(db, bug_id)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="该 Bug 尚未触发 AI 分析"
        )

    return ResponseModel(data=AiAnalysisStatusResponse.model_validate(analysis))


@router.get(
    "/{bug_id}/ai-analysis",
    summary="获取 AI 分析结果",
    response_model=ResponseModel[AiAnalysisResponse],
)
async def get_ai_analysis_result(
    project_id: int,
    bug_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.require_permission("bug:view")),
) -> ResponseModel[AiAnalysisResponse]:
    """获取 Bug AI 分析的完整结果。"""
    await require_project_access(db, project_id, current_user.id)
    bug = await crud_bug.get_active(db, bug_id, project_id)
    if not bug:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bug 不存在")

    analysis = await crud_bug_ai_analysis.get_by_bug(db, bug_id)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="该 Bug 尚未触发 AI 分析"
        )

    return ResponseModel(data=AiAnalysisResponse.model_validate(analysis))
