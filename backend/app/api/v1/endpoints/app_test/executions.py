"""APP 自动化执行端点（项目域，P2）

/projects/{project_id}/app/executions：执行记录列表 / 详情 / 报告展示。
回放提交在 scripts 路由（POST /app/scripts/{script_id}/run）。

报告安全（G9 红线）：Midscene HTML 是第三方带 JS 的报告且含设备屏幕截图，
绝不落 /uploads 静态挂载、绝不进同源 iframe（localStorage JWT 会被窃）——
经本鉴权端点返回，并带 `Content-Security-Policy: sandbox allow-scripts`
（沙箱化：允许执行报告自身 JS，禁 same-origin/表单/弹窗/顶层导航）。
"""

from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.config import settings
from app.core.response import ResponseModel, page_response
from app.crud.app_test import crud_app_execution
from app.models.auth.user import User
from app.schemas.app_test import AppExecutionOut
from app.utils.project_permission import require_project_access

router = APIRouter()


async def _ensure_execution_in_project(
    db: AsyncSession, *, project_id: int, execution_id: int, user_id: int
):
    """项目成员校验 + 执行记录归属断言（join script，防 IDOR）。"""
    await require_project_access(db, project_id, user_id)
    execution = await crud_app_execution.get_in_project(db, project_id, execution_id)
    if execution is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="执行记录不存在")
    return execution


@router.get("", summary="执行记录列表（项目内）")
async def list_executions(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_test:view"))],
    script_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    await require_project_access(db, project_id, current_user.id)
    rows, total = await crud_app_execution.get_list(
        db,
        project_id,
        script_id=script_id,
        status=status_filter,
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    items = []
    for execution, script_name, script_platform, device_model, device_platform in rows:
        out = AppExecutionOut.model_validate(execution)
        out.script_name = script_name
        out.script_platform = script_platform
        out.device_name = device_model
        out.device_platform = device_platform
        items.append(out.model_dump(mode="json"))
    return page_response(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{execution_id}",
    summary="执行记录详情",
    response_model=ResponseModel[AppExecutionOut],
)
async def get_execution(
    project_id: int,
    execution_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_test:view"))],
):
    execution = await _ensure_execution_in_project(
        db, project_id=project_id, execution_id=execution_id, user_id=current_user.id
    )
    return ResponseModel(data=AppExecutionOut.model_validate(execution))


@router.get(
    "/{execution_id}/report-url",
    summary="签发报告独立源访问 URL（P4-D，契约 §3.6）",
    response_model=ResponseModel[dict],
)
async def get_execution_report_url(
    project_id: int,
    execution_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_test:view"))],
) -> ResponseModel[dict]:
    """报告经网关独立源展示（跨源 iframe，报告 JS 全量水合且摸不到平台
    JWT）；此端点做完整 RBAC 后签短时效 HMAC URL，iframe src 直连网关。"""
    from app.services.app_device.report_sign import REPORT_URL_TTL_S, build_report_url

    execution = await _ensure_execution_in_project(
        db, project_id=project_id, execution_id=execution_id, user_id=current_user.id
    )
    if not execution.report_path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="该执行无报告")
    report_dir = Path(settings.APP_REPORT_DIR).resolve()
    if not (report_dir / f"{execution_id}.html").is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="报告文件不存在")
    return ResponseModel(
        data={"url": build_report_url(execution_id), "ttl_s": REPORT_URL_TTL_S}
    )


@router.get(
    "/{execution_id}/report",
    summary="Midscene HTML 报告（鉴权 + CSP sandbox，契约 §3.2；下载兜底用）",
    response_class=Response,
)
async def get_execution_report(
    project_id: int,
    execution_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("app_test:view"))],
) -> Response:
    execution = await _ensure_execution_in_project(
        db, project_id=project_id, execution_id=execution_id, user_id=current_user.id
    )
    if not execution.report_path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="该执行无报告")
    # report_path 只存文件名（图内生成），拼配置目录 + 防目录穿越
    report_dir = Path(settings.APP_REPORT_DIR).resolve()
    file_path = (report_dir / execution.report_path).resolve()
    if not str(file_path).startswith(str(report_dir)) or not file_path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="报告文件不存在")
    return Response(
        content=file_path.read_bytes(),
        media_type="text/html; charset=utf-8",
        headers={
            # 沙箱化第三方报告 JS：无 same-origin（拿不到平台 cookie/storage）、
            # 禁表单/弹窗/顶层导航；仅允许报告自身脚本渲染
            "Content-Security-Policy": "sandbox allow-scripts",
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
