"""
项目管理 API 端点

处理项目的 CRUD 操作、归档、恢复、删除、统计、配置等
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core import deps
from app.core.exceptions import BusinessException
from app.core.response import PageModel, PageResponseModel, ResponseModel
from app.crud.project import project as project_crud
from app.crud.project import (
    project_config,
    project_member,
    project_module,
)
from app.models.auth.user import User
from app.models.project import ProjectMember, ProjectStatus
from app.schemas.project import (
    ConfigUpdate,
    ProjectCreate,
    ProjectDetailResponse,
    ProjectResponse,
    ProjectStatisticsResponse,
    ProjectUpdate,
    UserSimple,
)
from app.services.project import project_service
from app.services.project.project_service import ProjectService

router = APIRouter()


@router.get(
    "/",
    summary="获取项目列表",
    response_model=PageResponseModel[ProjectResponse],
)
async def get_projects(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("project:view"))
    ],
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    keyword: str | None = Query(default=None, description="搜索关键词"),
    status_filter: ProjectStatus | None = Query(
        default=None, alias="status", description="状态筛选"
    ),
    is_public: bool | None = Query(default=None, description="是否公开"),
    member_id: int | None = Query(default=None, description="筛选某用户参与的项目"),
    order_by: str = Query(default="created_at", description="排序字段"),
    order: str = Query(default="desc", pattern="^(asc|desc)$", description="排序方向"),
) -> PageResponseModel[ProjectResponse]:
    """
    获取项目列表

    支持分页、搜索、筛选、排序功能：

    - **keyword**: 搜索项目名称或描述
    - **status**: 筛选项目状态（active/archived/deleted）
    - **is_public**: 筛选公开/私有项目
    - **member_id**: 筛选指定用户参与的项目
    - **order_by**: 排序字段（created_at/updated_at/name）
    - **order**: 排序方向（asc/desc）

    权限说明：
    - 系统管理员（super_admin）可以查看所有项目
    - 其他用户可查看自己参与的项目 + 所有公开项目
    """
    skip = (page - 1) * page_size

    # 检查用户是否为系统管理员
    is_super_admin = False
    for user_role in current_user.user_roles:
        if user_role.role.code == "super_admin":
            is_super_admin = True
            break

    # 非管理员：可见范围＝「本人参与 + 所有公开项目」（公开项目对任何人可见，
    # 与项目详情接口 is_public 放行同口径）；并禁止用 member_id 探测他人项目。
    accessible_by: int | None = None
    if not is_super_admin:
        accessible_by = current_user.id
        member_id = None

    projects, total = await project_crud.get_multi_projects(
        db,
        skip=skip,
        limit=page_size,
        keyword=keyword,
        status=status_filter,
        is_public=is_public,
        member_id=member_id,
        accessible_by=accessible_by,
        order_by=order_by,
        order=order,
    )

    # 构建响应数据
    items = []
    for p in projects:
        # 获取统计数据
        member_count = await project_member.count_by_project(db, project_id=p.id)
        module_count = await project_module.count_by_project(db, project_id=p.id)

        # 获取项目负责人
        from app.models.auth.role import Role

        owner_stmt = (
            select(ProjectMember)
            .join(Role, ProjectMember.project_role_id == Role.id)
            .options(selectinload(ProjectMember.user))
            .where(
                ProjectMember.project_id == p.id,
                Role.code == "project_owner",
            )
        )
        owner_result = await db.execute(owner_stmt)
        owner_member = owner_result.scalar_one_or_none()

        item = ProjectResponse(
            id=p.id,
            name=p.name,
            code=p.code,
            description=p.description,
            avatar=p.avatar,
            status=p.status,
            is_public=p.is_public,
            start_date=p.start_date,
            end_date=p.end_date,
            member_count=member_count,
            module_count=module_count,
            case_count=0,  # TODO: 实现用例统计
            bug_count=0,  # TODO: 实现 Bug 统计
            created_by=(
                UserSimple.model_validate(p.created_by) if p.created_by else None
            ),
            owner=(
                UserSimple.model_validate(owner_member.user)
                if owner_member and owner_member.user
                else None
            ),
        )
        items.append(item.model_dump())

    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

    return PageResponseModel(
        code=200,
        message="success",
        data=PageModel(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        ),
    )


@router.get(
    "/{project_id}",
    summary="获取项目详情",
    response_model=ResponseModel[ProjectDetailResponse],
)
async def get_project(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("project:view"))
    ],
    project_id: int,
) -> ResponseModel[ProjectDetailResponse]:
    """
    获取项目详情

    返回项目的完整信息，包括配置、统计数据等
    """
    project_obj = await project_crud.get_with_details(db, project_id=project_id)
    if not project_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在",
        )

    # 检查访问权限
    # 系统管理员可以访问所有项目
    is_super_admin = await ProjectService._is_super_admin(db, current_user.id)

    if not project_obj.is_public and not is_super_admin:
        if not await project_member.is_member(
            db, project_id=project_id, user_id=current_user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限访问该项目",
            )

    # 获取负责人
    owner_member = await project_member.get_owner(db, project_id=project_id)

    return ResponseModel(
        data=ProjectDetailResponse(
            id=project_obj.id,
            name=project_obj.name,
            code=project_obj.code,
            description=project_obj.description,
            avatar=project_obj.avatar,
            status=project_obj.status,
            is_public=project_obj.is_public,
            start_date=project_obj.start_date,
            end_date=project_obj.end_date,
            owner=(
                UserSimple.model_validate(owner_member.user)
                if owner_member and owner_member.user
                else None
            ),
            created_at=(
                project_obj.created_at.isoformat() if project_obj.created_at else None
            ),
            updated_at=(
                project_obj.updated_at.isoformat() if project_obj.updated_at else None
            ),
        )
    )


@router.post(
    "",
    summary="创建项目",
    response_model=ResponseModel[dict],
)
async def create_project(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("project:create"))
    ],
    obj_in: ProjectCreate,
) -> ResponseModel[dict]:
    """
    创建项目

    创建新项目，创建者自动成为项目负责人

    - **name**: 项目名称（2-100字符，唯一）
    - **code**: 项目标识（字母开头，支持字母、数字、下划线、中划线，唯一）
    - **description**: 项目描述（可选）
    - **avatar**: 项目图标URL（可选）
    - **start_date**: 计划开始日期（可选）
    - **end_date**: 计划结束日期（可选）
    - **is_public**: 是否公开项目（默认false）
    """
    try:
        project_obj = await project_service.create_project(
            db, obj_in=obj_in, creator_id=current_user.id
        )
        return ResponseModel(
            data={
                "id": project_obj.id,
                "name": project_obj.name,
                "code": project_obj.code,
            },
            message="创建成功",
        )
    except BusinessException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.message,
        )


@router.put(
    "/{project_id}",
    summary="更新项目信息",
    response_model=ResponseModel[dict],
)
async def update_project(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("project:edit"))
    ],
    project_id: int,
    obj_in: ProjectUpdate,
) -> ResponseModel[dict]:
    """
    更新项目信息

    只有项目负责人可以更新项目信息

    注意：项目标识（code）不可修改
    """
    # 获取项目
    project_obj = await project_crud.get(db, id=project_id)
    if not project_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在",
        )

    # 检查权限
    if not await project_service.can_edit_project(
        db, project_id=project_id, user_id=current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有项目负责人可以编辑项目",
        )

    try:
        await project_service.update_project(db, db_obj=project_obj, obj_in=obj_in)
        return ResponseModel(
            data={"id": project_obj.id, "name": project_obj.name},
            message="更新成功",
        )
    except BusinessException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.message,
        )


@router.post(
    "/upload-avatar",
    summary="上传项目图标",
    response_model=ResponseModel[dict],
)
async def upload_project_avatar(
    file: Annotated[UploadFile, File()],
    current_user: Annotated[
        User, Depends(deps.require_permission("project:edit"))
    ],
) -> ResponseModel[dict]:
    """
    上传项目图标（通用，不绑定项目ID）

    - 支持格式：JPG、JPEG、PNG、WEBP
    - 大小限制：2MB
    - 返回 URL 用于创建/更新项目时传入 avatar 字段
    """
    from app.utils.storage_utils import save_bytes, get_access_url

    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")
    from pathlib import Path
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in (".jpg", ".jpeg", ".png", ".webp"):
        raise HTTPException(status_code=400, detail="仅支持 JPG/PNG/WEBP 格式")

    content = await file.read()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小不能超过 2MB")

    from uuid import uuid4
    filename = f"{uuid4().hex}{file_ext}"
    storage_key = f"projects/avatars/{filename}"
    save_bytes(content, storage_key)
    avatar_url = get_access_url(storage_key)

    return ResponseModel(data={"url": avatar_url}, message="图标上传成功")


@router.post(
    "/{project_id}/archive",
    summary="归档项目",
    response_model=ResponseModel[dict],
)
async def archive_project(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("project:edit"))
    ],
    project_id: int,
) -> ResponseModel[dict]:
    """
    归档项目

    只有项目负责人可以归档项目
    """
    try:
        project_obj = await project_service.archive_project(db, project_id=project_id)
        return ResponseModel(
            data={"id": project_obj.id, "status": project_obj.status},
            message="归档成功",
        )
    except BusinessException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )


@router.post(
    "/{project_id}/restore",
    summary="恢复项目",
    response_model=ResponseModel[dict],
)
async def restore_project(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("project:edit"))
    ],
    project_id: int,
) -> ResponseModel[dict]:
    """
    恢复项目

    只有项目负责人可以恢复已归档的项目
    """
    try:
        project_obj = await project_service.restore_project(db, project_id=project_id)
        return ResponseModel(
            data={"id": project_obj.id, "status": project_obj.status},
            message="恢复成功",
        )
    except BusinessException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )


@router.delete(
    "/{project_id}",
    summary="删除项目",
    response_model=ResponseModel[None],
)
async def delete_project(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("project:delete"))
    ],
    project_id: int,
) -> ResponseModel[None]:
    """
    删除项目

    只有项目负责人可以删除项目
    软删除，有关联数据的项目需要先归档
    """
    try:
        await project_service.delete_project(db, project_id=project_id)
        return ResponseModel(message="删除成功")
    except BusinessException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )


@router.get(
    "/{project_id}/statistics",
    summary="获取项目统计",
    response_model=ResponseModel[ProjectStatisticsResponse],
)
async def get_project_statistics(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("project:view"))
    ],
    project_id: int,
    start_date: date | None = Query(default=None, description="统计开始日期"),
    end_date: date | None = Query(default=None, description="统计结束日期"),
) -> ResponseModel[ProjectStatisticsResponse]:
    """
    获取项目统计数据

    返回用例统计、Bug统计、执行趋势、成员统计等数据
    """
    # 检查访问权限
    # 系统管理员可以访问所有项目
    is_super_admin = await ProjectService._is_super_admin(db, current_user.id)

    if not is_super_admin:
        if not await project_member.is_member(
            db, project_id=project_id, user_id=current_user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限访问该项目",
            )

    statistics = await project_service.get_project_statistics(
        db,
        project_id=project_id,
        start_date=start_date,
        end_date=end_date,
    )

    return ResponseModel(data=statistics)


@router.put(
    "/{project_id}/config",
    summary="更新项目配置",
    response_model=ResponseModel[dict],
)
async def update_project_config(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("project:edit"))
    ],
    project_id: int,
    obj_in: ConfigUpdate,
) -> ResponseModel[dict]:
    """
    更新项目配置

    只有项目负责人可以更新项目配置
    """
    # 检查权限
    if not await project_service.can_edit_project(
        db, project_id=project_id, user_id=current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有项目负责人可以编辑项目配置",
        )

    config = await project_config.update_by_project(
        db, project_id=project_id, obj_in=obj_in
    )

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目配置不存在",
        )

    return ResponseModel(
        data={
            "default_env_id": config.default_env_id,
            "bug_auto_assign": config.bug_auto_assign,
        },
        message="配置更新成功",
    )
