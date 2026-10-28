"""
Bug 操作历史 API 端点
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.response import ResponseModel
from app.crud.bug.bug import crud_bug
from app.crud.bug.bug_history import crud_bug_history
from app.models.auth.user import User
from app.schemas.bug.bug_history import BugHistoryResponse
from app.utils.project_permission import require_project_access

router = APIRouter()


@router.get(
    "/{bug_id}/histories",
    summary="获取 Bug 操作历史",
    response_model=ResponseModel[list[BugHistoryResponse]],
)
async def get_bug_histories(
    project_id: int,
    bug_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.require_permission("bug:view")),
) -> ResponseModel[list[BugHistoryResponse]]:
    """获取 Bug 的完整操作历史，按时间升序排列。"""
    await require_project_access(db, project_id, current_user.id)
    bug = await crud_bug.get_active(db, bug_id, project_id)
    if not bug:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bug 不存在")

    histories = await crud_bug_history.get_by_bug(db, bug_id)

    items = []
    for h in histories:
        item = BugHistoryResponse.model_validate(h)
        if h.operator:
            item.operator_name = h.operator.username
        items.append(item)

    return ResponseModel(data=items)
