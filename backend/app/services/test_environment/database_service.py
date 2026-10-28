"""
数据库连接业务服务层

处理数据库连接相关的业务逻辑
"""

import asyncio
import json
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.test_environment.dialects import Dialect, get_dialect
from app.core.exceptions import BusinessException, NotFoundException
from app.crud.test_environment import database
from app.models.test_environment.database import DatabaseConnection
from app.schemas.test_environment.database import (
    ConnectionStatus,
    DatabaseCreate,
    DatabaseTestResponse,
    DatabaseUpdate,
)


def _cfg_from(db_obj: DatabaseConnection) -> dict:
    """DatabaseConnection ORM → 方言 connect 用的纯 dict（不持有 ORM，供线程内同步驱动用）。"""
    raw = db_obj.connection_params
    params: Any = raw
    if isinstance(raw, str):
        try:
            params = json.loads(raw)
        except Exception:  # noqa: BLE001
            params = {}
    return {
        "host": db_obj.host,
        "port": db_obj.port,
        "user": db_obj.username,
        "password": db_obj.password,
        "database": db_obj.database,
        "charset": db_obj.charset,
        "params": params if isinstance(params, dict) else {},
    }


def _require_dialect(db_obj: DatabaseConnection) -> Dialect:
    """取方言；非关系型/未支持类型抛清晰的「暂不支持」。"""
    dialect = get_dialect(db_obj.db_type)
    if dialect is None:
        raise BusinessException(
            message=(
                f"暂不支持 {db_obj.db_type} 的该操作"
                "（关系型仅 MySQL / PostgreSQL / Oracle / SQLServer；"
                "MongoDB / Redis 非 SQL，请用对应能力）"
            )
        )
    return dialect


# 表结构内省缓存：{db_id: (过期时间戳, schema dict)}。表结构不常变，短 TTL 足够；
# refresh=True 或改连接后可绕过。进程级内存缓存（单进程/多 worker 各自缓存，可接受）。
_SCHEMA_CACHE: dict[int, tuple[float, dict]] = {}
_SCHEMA_TTL = 300.0


class DatabaseService:
    """
    数据库连接业务服务类
    """

    @staticmethod
    async def get_schema(db_obj: DatabaseConnection, *, refresh: bool = False) -> dict:
        """内省被测库表结构（MySQL / PostgreSQL / Oracle / SQLServer）。

        返回 ``{"database": 库名, "tables": [{name, comment, columns: [
        {name, type, nullable, key, comment}]}]}``。只读，各方言走各自的系统目录/
        INFORMATION_SCHEMA。同步驱动 → to_thread，避免卡事件循环。
        """
        dialect = _require_dialect(db_obj)

        now = time.time()
        cached = _SCHEMA_CACHE.get(db_obj.id)
        if not refresh and cached and cached[0] > now:
            return cached[1]

        cfg = _cfg_from(db_obj)

        def _introspect() -> dict:
            conn = dialect.connect(cfg, autocommit=False, timeout=10)
            try:
                return dialect.introspect(conn, db_obj.database)
            finally:
                conn.close()

        try:
            schema = await asyncio.to_thread(_introspect)
        except Exception as exc:  # noqa: BLE001
            raise BusinessException(
                message=f"读取表结构失败：{exc}（请检查连接可用性与账号的 "
                "INFORMATION_SCHEMA 读取权限）"
            ) from exc

        _SCHEMA_CACHE[db_obj.id] = (now + _SCHEMA_TTL, schema)
        return schema

    _CELL_LIMIT = 1024  # 单元格截断（长文本/JSON 防炸前端）

    @staticmethod
    async def get_table_rows(
        db_obj: DatabaseConnection, *, table: str, limit: int = 20, offset: int = 0
    ) -> dict:
        """分页查看表数据（只读，MySQL / PostgreSQL / Oracle / SQLServer）。

        表名先对照 get_schema 内省清单做白名单校验（表名不可参数化，白名单是注入的
        唯一正解）；多取一行判断 has_more，不做大表致命的精确 COUNT(*)。分页语法与
        标识符引用按方言（LIMIT/OFFSET vs OFFSET/FETCH）。
        返回 ``{"columns": [名...], "rows": [{列: 值}], "has_more": bool}``。
        """
        dialect = _require_dialect(db_obj)
        limit = max(1, min(int(limit or 20), 100))
        offset = max(0, int(offset or 0))
        schema = await DatabaseService.get_schema(db_obj)
        allowed = {t["name"] for t in schema.get("tables", [])}
        if table not in allowed:
            raise BusinessException(message=f"表 {table} 不存在（或不在当前库中）")

        cfg = _cfg_from(db_obj)

        def _cell(v: Any) -> Any:
            if isinstance(v, (bytes, bytearray)):
                return f"<二进制 {len(v)} 字节>"
            if isinstance(v, str) and len(v) > DatabaseService._CELL_LIMIT:
                return (
                    v[: DatabaseService._CELL_LIMIT] + f"…（已截断，共 {len(v)} 字符）"
                )
            if v is None or isinstance(v, (int, float, bool, str)):
                return v
            return str(v)  # datetime/Decimal 等

        def _query() -> dict:
            conn = dialect.connect(cfg, autocommit=False, timeout=10)
            try:
                cur = dialect.new_cursor(conn)
                try:
                    # 表名已过白名单 + 方言引用兜底；多取一行判 has_more
                    sql, bind = dialect.page_query(table, limit + 1, offset)
                    cur.execute(sql, bind)
                    raw = dialect.rows(cur)
                    columns = [d[0] for d in (cur.description or [])]
                finally:
                    cur.close()
            finally:
                conn.close()
            has_more = len(raw) > limit
            rows = [{k: _cell(v) for k, v in r.items()} for r in raw[:limit]]
            return {"columns": columns, "rows": rows, "has_more": has_more}

        try:
            return await asyncio.to_thread(_query)
        except BusinessException:
            raise
        except Exception as exc:  # noqa: BLE001
            raise BusinessException(message=f"查询表数据失败：{exc}") from exc

    @staticmethod
    async def create_database(
        db: AsyncSession,
        *,
        obj_in: DatabaseCreate,
        project_id: int,
    ) -> DatabaseConnection:
        """
        创建数据库连接

        Args:
            db: 数据库会话
            obj_in: 创建数据
            project_id: 项目ID

        Returns:
            DatabaseConnection: 创建的数据库连接

        Raises:
            BusinessException: 连接名称已存在且未被删除
        """
        # 检查是否存在同名连接（包括已删除的）
        stmt = select(DatabaseConnection).where(
            DatabaseConnection.project_id == project_id,
            DatabaseConnection.name == obj_in.name,
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            if existing.is_deleted:
                # 如果是已删除的记录，恢复它
                existing.name = obj_in.name
                existing.db_type = obj_in.db_type
                existing.host = obj_in.host
                existing.port = obj_in.port
                existing.database = obj_in.database
                existing.username = obj_in.username
                existing.password = obj_in.password
                existing.charset = obj_in.charset
                existing.connection_params = obj_in.connection_params
                existing.allow_write = obj_in.allow_write
                existing.connection_status = "unknown"
                existing.is_deleted = False
                existing.deleted_at = None
                db.add(existing)
                await db.commit()
                await db.refresh(existing)
                return existing
            else:
                # 如果是未删除的记录，报错
                raise BusinessException("连接名称已存在")

        return await database.create(db, obj_in=obj_in, project_id=project_id)

    @staticmethod
    async def update_database(
        db: AsyncSession,
        *,
        db_obj: DatabaseConnection,
        obj_in: DatabaseUpdate,
    ) -> DatabaseConnection:
        """
        更新数据库连接

        Args:
            db: 数据库会话
            db_obj: 数据库中的连接
            obj_in: 更新数据

        Returns:
            DatabaseConnection: 更新后的连接

        Raises:
            BusinessException: 连接名称已存在
        """
        # 如果更新名称，检查是否重复
        if obj_in.name and obj_in.name != db_obj.name:
            if await database.name_exists(
                db, project_id=db_obj.project_id, name=obj_in.name, exclude_id=db_obj.id
            ):
                raise BusinessException("连接名称已存在")

        return await database.update(db, db_obj=db_obj, obj_in=obj_in)

    @staticmethod
    async def delete_database(
        db: AsyncSession,
        *,
        db_id: int,
    ) -> bool:
        """
        删除数据库连接

        Args:
            db: 数据库会话
            db_id: 连接ID

        Returns:
            bool: 是否删除成功

        Raises:
            NotFoundException: 连接不存在
        """
        db_conn = await database.get(db, id=db_id)
        if not db_conn:
            raise NotFoundException("数据库连接不存在")

        return await database.soft_delete(db, id=db_id)

    @staticmethod
    async def test_database_connection(
        db: AsyncSession,
        *,
        db_obj: DatabaseConnection,
    ) -> DatabaseTestResponse:
        """
        测试数据库连接

        Args:
            db: 数据库会话
            db_obj: 数据库连接对象

        Returns:
            DatabaseTestResponse: 测试结果
        """
        start_time = time.time()
        tested_at = int(start_time * 1000)

        try:
            # 关系型统一走方言连接 + 探测 SQL；非关系型（MongoDB/Redis）暂由各自能力承接
            result = await DatabaseService._test_connection(db_obj)

            # 计算响应时间
            response_time = int((time.time() - start_time) * 1000)

            if result["success"]:
                # 更新连接状态为成功
                await database.update_connection_status(
                    db,
                    db_obj=db_obj,
                    status=ConnectionStatus.CONNECTED,
                    test_result="连接成功",
                    test_time=tested_at,
                )

                return DatabaseTestResponse(
                    status=ConnectionStatus.CONNECTED,
                    response_time=response_time,
                    message="连接成功",
                    tested_at=str(tested_at),
                )
            else:
                # 更新连接状态为失败
                await database.update_connection_status(
                    db,
                    db_obj=db_obj,
                    status=ConnectionStatus.DISCONNECTED,
                    test_result=result.get("error", "连接失败"),
                    test_time=tested_at,
                )

                return DatabaseTestResponse(
                    status=ConnectionStatus.DISCONNECTED,
                    message="连接失败",
                    error=result.get("error", "连接失败"),
                    tested_at=str(tested_at),
                )

        except Exception as e:
            # 更新连接状态为失败
            await database.update_connection_status(
                db,
                db_obj=db_obj,
                status=ConnectionStatus.DISCONNECTED,
                test_result=str(e),
                test_time=tested_at,
            )

            response_time = int((time.time() - start_time) * 1000)

            return DatabaseTestResponse(
                status=ConnectionStatus.DISCONNECTED,
                message="连接失败",
                error=str(e),
                tested_at=str(tested_at),
            )

    @staticmethod
    async def _test_connection(db_obj: DatabaseConnection) -> dict[str, Any]:
        """连通性测试：关系型统一走方言 connect + 探测 SQL（同步驱动 → to_thread）。

        非关系型（MongoDB/Redis）无方言 → 返回明确「暂由对应能力承接」。返回
        ``{"success": bool, "error"?: str}``，异常收敛为 error 文本。
        """
        dialect = get_dialect(db_obj.db_type)
        if dialect is None:
            return {
                "success": False,
                "error": (
                    f"{db_obj.db_type} 连接测试请用对应能力"
                    "（关系型仅 MySQL / PostgreSQL / Oracle / SQLServer）"
                ),
            }

        cfg = _cfg_from(db_obj)

        def _probe() -> dict[str, Any]:
            try:
                conn = dialect.connect(cfg, autocommit=True, timeout=5)
                try:
                    cur = dialect.new_cursor(conn)
                    try:
                        cur.execute(dialect.test_query())
                        cur.fetchone()
                    finally:
                        cur.close()
                finally:
                    conn.close()
                return {"success": True}
            except Exception as e:  # noqa: BLE001
                return {"success": False, "error": str(e)}

        return await asyncio.to_thread(_probe)


# 创建服务实例
database_service = DatabaseService()
