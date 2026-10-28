"""
Bug 状态流转 API 端点

处理状态变更、指派、解决/关闭/重开操作。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.response import ResponseModel
from app.crud.bug.bug import crud_bug, is_valid_transition
from app.crud.bug.bug_history import crud_bug_history
from app.models.auth.user import User
from app.models.bug.bug import BugStatus
from app.models.bug.bug_history import BugAction
from app.schemas.bug.bug_actions import (
    BugAssign,
    BugAssignResponse,
    BugResolve,
    BugStatusChange,
    BugStatusResponse,
)
from app.utils.project_permission import require_project_access

router = APIRouter()

# resolve 接口的 action → 目标状态映射
_RESOLVE_ACTION_MAP = {
    "resolve": BugStatus.RESOLVED.value,
    "close": BugStatus.CLOSED.value,
    "reopen": BugStatus.REOPENED.value,
}

# resolve 接口的 action → BugAction 枚举映射
_RESOLVE_HISTORY_MAP = {
    "resolve": BugAction.RESOLVED.value,
    "close": BugAction.CLOSED.value,
    "reopen": BugAction.REOPENED.value,
}


@router.post(
    "/{bug_id}/status",
    summary="变更 Bug 状态",
    response_model=ResponseModel[BugStatusResponse],
)
async def change_status(
    project_id: int,
    bug_id: int,
    body: BugStatusChange,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("bug:resolve"))
    ],
) -> ResponseModel[BugStatusResponse]:
    """
    变更 Bug 状态。

    状态流转规则：
    - new → assigned / postponed / wontfix
    - assigned → in_progress / postponed / wontfix
    - in_progress → resolved / postponed / wontfix
    - resolved → verified / reopened / closed
    - verified → closed / reopened
    - reopened → assigned / in_progress / postponed / wontfix
    """
    await require_project_access(db, project_id, current_user.id)
    bug = await crud_bug.get_active(db, bug_id, project_id)
    if not bug:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bug 不存在")

    if not is_valid_transition(bug.status, body.status):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"状态转换不合法：Bug 当前状态为 '{bug.status}'，不允许直接转换为 '{body.status}'",
        )

    old_status = bug.status
    bug = await crud_bug.change_status(db, bug=bug, new_status=body.status)

    await crud_bug_history.create(
        db,
        bug_id=bug.id,
        action=BugAction.STATUS_CHANGED.value,
        from_value=old_status,
        to_value=body.status,
        comment=body.comment,
        operated_by=current_user.id,
    )

    return ResponseModel(
        message="状态已更新",
        data=BugStatusResponse(
            id=bug.id,
            status=bug.status,
            updated_at=bug.updated_at.isoformat(),
        ),
    )


@router.post(
    "/{bug_id}/assign",
    summary="指派 Bug",
    response_model=ResponseModel[BugAssignResponse],
)
async def assign_bug(
    project_id: int,
    bug_id: int,
    body: BugAssign,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("bug:assign"))
    ],
) -> ResponseModel[BugAssignResponse]:
    """
    指派 Bug 给项目成员。

    若 Bug 当前状态为 new，自动流转为 assigned。
    """
    await require_project_access(db, project_id, current_user.id)
    from app.crud.project.member import project_member

    bug = await crud_bug.get_active(db, bug_id, project_id)
    if not bug:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bug 不存在")

    member = await project_member.get_by_project_and_user(
        db, project_id=project_id, user_id=body.assigned_to
    )
    if not member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="指派目标用户不是该项目成员",
        )

    old_assigned = str(bug.assigned_to) if bug.assigned_to else None
    bug = await crud_bug.assign(db, bug=bug, assigned_to=body.assigned_to)

    await crud_bug_history.create(
        db,
        bug_id=bug.id,
        action=BugAction.ASSIGNED.value,
        from_value=old_assigned,
        to_value=str(body.assigned_to),
        comment=body.comment,
        operated_by=current_user.id,
    )

    # 直接查询指派人姓名，避免 assignee 关系未加载
    from app.models.auth.user import User

    assignee_name = None
    user_result = await db.execute(select(User.username).where(User.id == body.assigned_to))
    user_row = user_result.scalar_one_or_none()
    if user_row:
        assignee_name = user_row

    return ResponseModel(
        message="指派成功",
        data=BugAssignResponse(
            id=bug.id,
            assigned_to=bug.assigned_to,
            assignee_name=assignee_name,
            status=bug.status,
            updated_at=bug.updated_at.isoformat(),
        ),
    )


@router.post(
    "/{bug_id}/resolve",
    summary="解决 / 关闭 / 重开 Bug",
    response_model=ResponseModel[BugStatusResponse],
)
async def resolve_bug(
    project_id: int,
    bug_id: int,
    body: BugResolve,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("bug:resolve"))
    ],
) -> ResponseModel[BugStatusResponse]:
    """
    解决、关闭或重新打开 Bug。

    - action=resolve：标记为已解决
    - action=close：关闭 Bug
    - action=reopen：重新打开（状态变为 reopened）
    """
    await require_project_access(db, project_id, current_user.id)
    if body.action not in _RESOLVE_ACTION_MAP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"action 不合法，允许值：{list(_RESOLVE_ACTION_MAP.keys())}",
        )

    bug = await crud_bug.get_active(db, bug_id, project_id)
    if not bug:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bug 不存在")

    target_status = _RESOLVE_ACTION_MAP[body.action]
    if not is_valid_transition(bug.status, target_status):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"状态转换不合法：Bug 当前状态为 '{bug.status}'，不允许执行 '{body.action}' 操作",
        )

    old_status = bug.status
    bug = await crud_bug.change_status(db, bug=bug, new_status=target_status)

    await crud_bug_history.create(
        db,
        bug_id=bug.id,
        action=_RESOLVE_HISTORY_MAP[body.action],
        from_value=old_status,
        to_value=target_status,
        comment=body.comment,
        operated_by=current_user.id,
    )

    action_labels = {"resolve": "已解决", "close": "已关闭", "reopen": "已重新打开"}
    return ResponseModel(
        message=f"Bug {action_labels[body.action]}",
        data=BugStatusResponse(
            id=bug.id,
            status=bug.status,
            updated_at=bug.updated_at.isoformat(),
        ),
    )
