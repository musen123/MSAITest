"""定时计划 API

/projects/{project_id}/scheduled-jobs：CRUD + 启停 + 立即执行 +
cron 校验预览 + 派发流水。权限与项目报表同口径（超管或项目成员）。
"""

from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core import deps
from app.core.response import ResponseModel, success_response
from app.crud.ai.ai_task import crud_ai_task
from app.crud.project.member import project_member
from app.crud.scheduler.scheduled_job import crud_scheduled_job
from app.models.auth.user import User
from app.models.scheduler.scheduled_job import ScheduledJobType, ScheduleType
from app.schemas.scheduler.scheduled_job import (
    CronValidateRequest,
    CronValidateResponse,
    ScheduledJobCreate,
    ScheduledJobListResponse,
    ScheduledJobResponse,
    ScheduledJobRunListResponse,
    ScheduledJobRunResponse,
    ScheduledJobUpdate,
)
from app.services.project.project_service import ProjectService
from app.services.scheduler import scheduled_job_service as svc

router = APIRouter()
_JOB_TYPES = {t.value for t in ScheduledJobType}


async def _check_access(db: AsyncSession, project_id: int, user: User) -> None:
    if await ProjectService._is_super_admin(db, user.id):
        return
    if not await project_member.is_member(db, project_id=project_id, user_id=user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限访问该项目"
        )


def _validate_schedule(
    schedule_type: str, cron_expr: Optional[str], interval_seconds: Optional[int]
) -> None:
    if schedule_type == ScheduleType.CRON.value:
        if not cron_expr or not svc.validate_cron(cron_expr):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="cron 表达式无效（5 段格式，如 0 2 * * *）",
            )
    elif schedule_type == ScheduleType.INTERVAL.value:
        if not interval_seconds or interval_seconds < 60:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="间隔秒数无效（最小 60 秒）"
            )
    else:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="schedule_type 必须是 cron 或 interval"
        )


async def _to_response(
    db: AsyncSession, job, *, with_target: bool = True
) -> ScheduledJobResponse:
    resp = ScheduledJobResponse.model_validate(job)
    if with_target:
        resp.target_name = await svc.resolve_target_name(
            db,
            job_type=job.job_type,
            target_id=job.target_id,
            project_id=job.project_id,
        )
    return resp


@router.post(
    "", summary="创建定时计划", response_model=ResponseModel[ScheduledJobResponse]
)
async def create_job(
    project_id: int,
    body: ScheduledJobCreate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("scheduler:create"))],
) -> ResponseModel[ScheduledJobResponse]:
    await _check_access(db, project_id, current_user)
    if body.job_type not in _JOB_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"job_type 必须是 {'/'.join(sorted(_JOB_TYPES))}",
        )
    _validate_schedule(body.schedule_type, body.cron_expr, body.interval_seconds)
    target_name = await svc.resolve_target_name(
        db, job_type=body.job_type, target_id=body.target_id, project_id=project_id
    )
    if target_name is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="执行对象不存在或已删除"
        )
    from app.models.scheduler.scheduled_job import ScheduledJob

    job = ScheduledJob(
        project_id=project_id,
        name=body.name,
        description=body.description,
        job_type=body.job_type,
        target_id=body.target_id,
        params=body.params,
        schedule_type=body.schedule_type,
        cron_expr=body.cron_expr,
        interval_seconds=body.interval_seconds,
        enabled=body.enabled,
        allow_overlap=body.allow_overlap,
        created_by=current_user.id,
    )
    if body.enabled:
        job.next_run_at = svc.compute_next_run(
            schedule_type=body.schedule_type,
            cron_expr=body.cron_expr,
            interval_seconds=body.interval_seconds,
        )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    resp = await _to_response(db, job)
    resp.target_name = target_name
    return success_response(data=resp)


@router.get(
    "", summary="定时计划列表", response_model=ResponseModel[ScheduledJobListResponse]
)
async def list_jobs(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("scheduler:view"))],
    enabled: Optional[bool] = Query(default=None),
    job_type: Optional[str] = Query(default=None),
    keyword: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ResponseModel[ScheduledJobListResponse]:
    await _check_access(db, project_id, current_user)
    items, total = await crud_scheduled_job.list_by_project(
        db,
        project_id=project_id,
        enabled=enabled,
        job_type=job_type,
        keyword=keyword,
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    resp_items = [await _to_response(db, j) for j in items]
    return success_response(
        data=ScheduledJobListResponse(total=total, items=resp_items)
    )


@router.post(
    "/validate-cron",
    summary="校验 cron 表达式并预览未来运行时间",
    response_model=ResponseModel[CronValidateResponse],
)
async def validate_cron(
    project_id: int,
    body: CronValidateRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("scheduler:view"))],
) -> ResponseModel[CronValidateResponse]:
    await _check_access(db, project_id, current_user)
    valid = svc.validate_cron(body.cron_expr)
    return success_response(
        data=CronValidateResponse(
            valid=valid, next_runs=svc.preview_cron(body.cron_expr) if valid else []
        )
    )


@router.get(
    "/{job_id}",
    summary="定时计划详情",
    response_model=ResponseModel[ScheduledJobResponse],
)
async def get_job(
    project_id: int,
    job_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("scheduler:view"))],
) -> ResponseModel[ScheduledJobResponse]:
    await _check_access(db, project_id, current_user)
    job = await crud_scheduled_job.get(db, job_id)
    if not job or job.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="计划不存在")
    return success_response(data=await _to_response(db, job))


@router.put(
    "/{job_id}",
    summary="更新定时计划",
    response_model=ResponseModel[ScheduledJobResponse],
)
async def update_job(
    project_id: int,
    job_id: int,
    body: ScheduledJobUpdate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("scheduler:edit"))],
) -> ResponseModel[ScheduledJobResponse]:
    await _check_access(db, project_id, current_user)
    job = await crud_scheduled_job.get(db, job_id)
    if not job or job.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="计划不存在")
    update = body.model_dump(exclude_unset=True)
    if "job_type" in update and update["job_type"] not in _JOB_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"job_type 必须是 {'/'.join(sorted(_JOB_TYPES))}",
        )
    schedule_type = update.get("schedule_type", job.schedule_type)
    cron_expr = update.get("cron_expr", job.cron_expr)
    interval_seconds = update.get("interval_seconds", job.interval_seconds)
    _validate_schedule(schedule_type, cron_expr, interval_seconds)
    if "job_type" in update or "target_id" in update:
        target_name = await svc.resolve_target_name(
            db,
            job_type=update.get("job_type", job.job_type),
            target_id=update.get("target_id", job.target_id),
            project_id=project_id,
        )
        if target_name is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="执行对象不存在或已删除"
            )
    final_job_type = update.get("job_type", job.job_type)
    final_params = update.get("params", job.params)
    schedule_changed = any(
        (
            k in update
            for k in ("schedule_type", "cron_expr", "interval_seconds", "enabled")
        )
    )
    job = await crud_scheduled_job.update_fields(db, job=job, **update)
    if schedule_changed:
        job = await crud_scheduled_job.update_fields(
            db,
            job=job,
            next_run_at=(
                svc.compute_next_run(
                    schedule_type=job.schedule_type,
                    cron_expr=job.cron_expr,
                    interval_seconds=job.interval_seconds,
                )
                if job.enabled
                else None
            ),
        )
    return success_response(data=await _to_response(db, job))


@router.post(
    "/{job_id}/toggle",
    summary="启用/停用定时计划",
    response_model=ResponseModel[ScheduledJobResponse],
)
async def toggle_job(
    project_id: int,
    job_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("scheduler:execute"))
    ],
) -> ResponseModel[ScheduledJobResponse]:
    await _check_access(db, project_id, current_user)
    job = await crud_scheduled_job.get(db, job_id)
    if not job or job.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="计划不存在")
    enabled = not job.enabled
    job = await crud_scheduled_job.update_fields(
        db,
        job=job,
        enabled=enabled,
        next_run_at=(
            svc.compute_next_run(
                schedule_type=job.schedule_type,
                cron_expr=job.cron_expr,
                interval_seconds=job.interval_seconds,
            )
            if enabled
            else None
        ),
    )
    return success_response(
        data=await _to_response(db, job), message="已启用" if enabled else "已停用"
    )


@router.post(
    "/{job_id}/run-now",
    summary="立即执行一次（不影响调度节奏）",
    response_model=ResponseModel[dict],
)
async def run_now(
    project_id: int,
    job_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("scheduler:execute"))
    ],
) -> ResponseModel[dict]:
    await _check_access(db, project_id, current_user)
    job = await crud_scheduled_job.get(db, job_id)
    if not job or job.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="计划不存在")
    result = await svc.fire_job(db, job=job, manual=True)
    if result["status"] == "skipped_overlap":
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=result.get("note", "执行中")
        )
    if result["status"] == "failed":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=result.get("note", "派发失败")
        )
    return success_response(data=result, message="已触发执行")


@router.get(
    "/{job_id}/runs",
    summary="派发流水（含执行终态）",
    response_model=ResponseModel[ScheduledJobRunListResponse],
)
async def list_runs(
    project_id: int,
    job_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("scheduler:view"))],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ResponseModel[ScheduledJobRunListResponse]:
    await _check_access(db, project_id, current_user)
    job = await crud_scheduled_job.get(db, job_id)
    if not job or job.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="计划不存在")
    items, total = await crud_scheduled_job.list_runs(
        db, job_id=job_id, skip=(page - 1) * page_size, limit=page_size
    )
    resp_items = []
    for r in items:
        resp = ScheduledJobRunResponse.model_validate(r)
        if r.ai_task_id:
            task = await crud_ai_task.get(db, r.ai_task_id)
            resp.task_status = task.status if task else None
        resp_items.append(resp)
    return success_response(
        data=ScheduledJobRunListResponse(total=total, items=resp_items)
    )


@router.delete("/{job_id}", summary="删除定时计划", response_model=ResponseModel)
async def delete_job(
    project_id: int,
    job_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("scheduler:delete"))],
) -> ResponseModel:
    await _check_access(db, project_id, current_user)
    job = await crud_scheduled_job.get(db, job_id)
    if not job or job.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="计划不存在")
    await crud_scheduled_job.soft_delete(db, job=job)
    return success_response(message="计划已删除")
