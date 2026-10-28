"""
数据库连接管理 API 端点

处理数据库连接的 CRUD、测试连接等操作
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.exceptions import BusinessException
from app.core.response import ResponseModel
from app.crud.project import project as project_crud
from app.crud.test_environment import database
from app.models.auth.user import User
from app.schemas.test_environment.database import (
    DatabaseCreate,
    DatabaseResponse,
    DatabaseTestRequest,
    DatabaseTestResponse,
    DatabaseUpdate,
)
from app.services.test_environment.database_service import DatabaseService

router = APIRouter()


async def check_project_access(
    db: AsyncSession,
    project_id: int,
    user_id: int,
) -> bool:
    """
    检查用户是否有项目访问权限

    系统管理员可以访问所有项目
    """
    project_obj = await project_crud.get(db, id=project_id)
    if not project_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在",
        )

    # 系统管理员可以访问所有项目
    from app.services.project.project_service import ProjectService

    if await ProjectService._is_super_admin(db, user_id):
        return True

    from app.crud.project import project_member

    return await project_member.is_member(db, project_id=project_id, user_id=user_id)


@router.get(
    "",
    summary="获取数据库连接列表",
    response_model=ResponseModel[list[DatabaseResponse]],
)
async def get_databases(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("environment:view"))
    ],
    project_id: Annotated[int, Path(description="项目ID")],
    db_type: str | None = Query(default=None, description="数据库类型筛选"),
    keyword: str | None = Query(default=None, description="搜索关键词"),
) -> ResponseModel[list[DatabaseResponse]]:
    """
    获取数据库连接列表

    返回项目的所有数据库连接

    - **db_type**: 数据库类型筛选
    - **keyword**: 搜索关键词
    """
    # 检查访问权限
    if not await check_project_access(db, project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问该项目",
        )

    # 获取数据库连接列表
    db_conns, _ = await database.get_multi_by_project(
        db, project_id=project_id, db_type=db_type, keyword=keyword
    )

    # 转换为响应格式
    items = []
    for db_conn in db_conns:
        # 处理 last_test_time（Unix 时间戳转为 ISO 格式字符串）
        last_test_time_str = None
        if db_conn.last_test_time is not None:
            try:
                last_test_time_str = datetime.fromtimestamp(
                    db_conn.last_test_time
                ).isoformat()
            except (OSError, OverflowError, ValueError):
                # 如果时间戳无效，保持为 None
                last_test_time_str = None

        items.append(
            DatabaseResponse(
                id=db_conn.id,
                project_id=db_conn.project_id,
                name=db_conn.name,
                db_type=db_conn.db_type,
                host=db_conn.host,
                port=db_conn.port,
                database=db_conn.database,
                username=db_conn.username,
                password=db_conn.password,
                charset=db_conn.charset,
                connection_params=(
                    db_conn.connection_params
                    if isinstance(db_conn.connection_params, dict)
                    else {}
                ),
                allow_write=bool(db_conn.allow_write),
                connection_status=db_conn.connection_status,
                last_test_time=last_test_time_str,
                last_test_result=db_conn.last_test_result,
                created_at=db_conn.created_at.isoformat() if db_conn.created_at else "",
                updated_at=db_conn.updated_at.isoformat() if db_conn.updated_at else "",
            )
        )

    return ResponseModel(data=items)


@router.get(
    "/{db_id}",
    summary="获取数据库连接详情",
    response_model=ResponseModel[DatabaseResponse],
)
async def get_database_detail(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("environment:view"))
    ],
    db_id: Annotated[int, Path(description="数据库连接ID")],
    project_id: Annotated[int, Path(description="项目ID")],
) -> ResponseModel[DatabaseResponse]:
    """
    获取数据库连接详情

    返回数据库连接的完整信息
    """
    # 检查访问权限
    if not await check_project_access(db, project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问该项目",
        )

    # 获取数据库连接
    db_conn = await database.get(db, id=db_id)
    if not db_conn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据库连接不存在",
        )

    # 转换为响应格式
    # 处理 last_test_time（Unix 时间戳转为 ISO 格式字符串）
    last_test_time_str = None
    if db_conn.last_test_time is not None:
        try:
            last_test_time_str = datetime.fromtimestamp(
                db_conn.last_test_time
            ).isoformat()
        except (OSError, OverflowError, ValueError):
            last_test_time_str = None

    response_data = DatabaseResponse(
        id=db_conn.id,
        project_id=db_conn.project_id,
        name=db_conn.name,
        db_type=db_conn.db_type,
        host=db_conn.host,
        port=db_conn.port,
        database=db_conn.database,
        username=db_conn.username,
        password=db_conn.password,
        charset=db_conn.charset,
        connection_params=(
            db_conn.connection_params
            if isinstance(db_conn.connection_params, dict)
            else {}
        ),
        allow_write=bool(db_conn.allow_write),
        connection_status=db_conn.connection_status,
        last_test_time=last_test_time_str,
        last_test_result=db_conn.last_test_result,
        created_at=db_conn.created_at.isoformat() if db_conn.created_at else "",
        updated_at=db_conn.updated_at.isoformat() if db_conn.updated_at else "",
    )

    return ResponseModel(data=response_data)


@router.post(
    "",
    summary="创建数据库连接",
    response_model=ResponseModel[dict],
)
async def create_database(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("environment:create"))
    ],
    obj_in: DatabaseCreate,
    project_id: Annotated[int, Path(description="项目ID")],
) -> ResponseModel[dict]:
    """
    创建数据库连接

    - **name**: 连接名称
    - **db_type**: 数据库类型（MySQL/PostgreSQL/Oracle/SQLServer/MongoDB/Redis）
    - **host**: 数据库地址
    - **port**: 端口号
    - **database**: 数据库名
    - **username**: 用户名
    - **password**: 密码
    - **charset**: 字符集
    - **connection_params**: 额外连接参数
    """
    # 检查访问权限
    if not await check_project_access(db, project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问该项目",
        )

    try:
        db_conn = await DatabaseService.create_database(
            db, obj_in=obj_in, project_id=project_id
        )
        return ResponseModel(
            data={"id": db_conn.id, "name": db_conn.name},
            message="创建成功",
        )
    except BusinessException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )


@router.put(
    "/{db_id}",
    summary="更新数据库连接",
    response_model=ResponseModel[dict],
)
async def update_database(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("environment:edit"))
    ],
    db_id: Annotated[int, Path(description="数据库连接ID")],
    obj_in: DatabaseUpdate,
    project_id: Annotated[int, Path(description="项目ID")],
) -> ResponseModel[dict]:
    """
    更新数据库连接

    可以更新连接的部分或全部字段
    """
    # 检查访问权限
    if not await check_project_access(db, project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问该项目",
        )

    # 获取数据库连接
    db_conn = await database.get(db, id=db_id)
    if not db_conn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据库连接不存在",
        )

    try:
        updated_conn = await DatabaseService.update_database(
            db, db_obj=db_conn, obj_in=obj_in
        )
        return ResponseModel(
            data={"id": updated_conn.id, "name": updated_conn.name},
            message="更新成功",
        )
    except BusinessException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )


@router.post(
    "/{db_id}/test",
    summary="测试数据库连接",
    response_model=ResponseModel[DatabaseTestResponse],
)
async def test_database_connection(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("environment:view"))
    ],
    db_id: Annotated[int, Path(description="数据库连接ID")],
    test_request: DatabaseTestRequest,
    project_id: Annotated[int, Path(description="项目ID")],
) -> ResponseModel[DatabaseTestResponse]:
    """
    测试数据库连接

    测试数据库连接是否可用，返回连接状态和响应时间
    """
    # 检查访问权限
    if not await check_project_access(db, project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问该项目",
        )

    # 获取数据库连接
    db_conn = await database.get(db, id=db_id)
    if not db_conn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据库连接不存在",
        )

    # 测试连接
    result = await DatabaseService.test_database_connection(db, db_obj=db_conn)

    # 根据测试结果返回不同的状态码和消息
    if result.status == "connected":
        return ResponseModel(data=result, message="连接成功")
    else:
        return ResponseModel(code=400, data=result, message="连接失败")


@router.get(
    "/{db_id}/schema",
    summary="内省数据库表结构",
    response_model=ResponseModel[dict],
)
async def get_database_schema(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("environment:view"))
    ],
    db_id: Annotated[int, Path(description="数据库连接ID")],
    project_id: Annotated[int, Path(description="项目ID")],
    refresh: bool = Query(default=False, description="绕过缓存强制刷新"),
) -> ResponseModel[dict]:
    """内省被测库的表结构（表 + 字段，只读，当前仅 MySQL）。供 NL→SQL 上下文与前端展示。"""
    if not await check_project_access(db, project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问该项目",
        )
    db_conn = await database.get(db, id=db_id)
    if not db_conn or db_conn.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据库连接不存在",
        )
    schema = await DatabaseService.get_schema(db_conn, refresh=refresh)
    return ResponseModel(data=schema)


@router.get(
    "/{db_id}/tables/{table_name}/rows",
    summary="分页查看表数据",
    response_model=ResponseModel[dict],
)
async def get_table_rows(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("environment:view"))
    ],
    db_id: Annotated[int, Path(description="数据库连接ID")],
    project_id: Annotated[int, Path(description="项目ID")],
    table_name: Annotated[str, Path(description="表名（须在内省清单中）")],
    limit: int = Query(default=20, ge=1, le=100, description="每页行数"),
    offset: int = Query(default=0, ge=0, description="偏移量"),
) -> ResponseModel[dict]:
    """只读分页查看表数据。表名过内省白名单防注入；LIMIT 多取一行判 has_more，
    不做大表致命的精确 COUNT(*)。返回 {columns, rows, has_more}。"""
    if not await check_project_access(db, project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问该项目",
        )
    db_conn = await database.get(db, id=db_id)
    if not db_conn or db_conn.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据库连接不存在",
        )
    data = await DatabaseService.get_table_rows(
        db_conn, table=table_name, limit=limit, offset=offset
    )
    return ResponseModel(data=data)


@router.delete(
    "/{db_id}",
    summary="删除数据库连接",
    response_model=ResponseModel[None],
)
async def delete_database(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("environment:delete"))
    ],
    db_id: Annotated[int, Path(description="数据库连接ID")],
    project_id: Annotated[int, Path(description="项目ID")],
) -> ResponseModel[None]:
    """
    删除数据库连接
    """
    # 检查访问权限
    if not await check_project_access(db, project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问该项目",
        )

    try:
        await DatabaseService.delete_database(db, db_id=db_id)
        return ResponseModel(message="删除成功")
    except BusinessException as e:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
                if e.code == 404
                else status.HTTP_400_BAD_REQUEST
            ),
            detail=e.message,
        )
