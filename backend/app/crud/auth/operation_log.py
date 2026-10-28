"""
操作日志CRUD操作

提供操作日志的数据库操作功能
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth.operation_log import OperationLog


class OperationLogCRUD:
    """操作日志CRUD类"""

    async def create(
        self, db: AsyncSession, *, obj_in: dict[str, Any]
    ) -> OperationLog:
        """创建操作日志"""
        db_obj = OperationLog(**obj_in)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def get(self, db: AsyncSession, *, id: int) -> Optional[OperationLog]:
        """根据ID获取操作日志"""
        result = await db.execute(
            select(OperationLog).where(OperationLog.id == id)
        )
        return result.scalars().first()

    async def get_multi(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
        **kwargs: Any,
    ) -> tuple[list[OperationLog], int]:
        """获取操作日志列表，支持筛选"""
        query = select(OperationLog)

        for key, value in kwargs.items():
            if "__" in key:
                field_name, operator = key.split("__", 1)
                field = getattr(OperationLog, field_name, None)
                if field is None:
                    continue
                if operator == "gte":
                    query = query.where(field >= value)
                elif operator == "lte":
                    query = query.where(field <= value)
            else:
                field = getattr(OperationLog, key, None)
                if field is None:
                    continue
                query = query.where(field == value)

        # 计算总数
        count_query = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_query)).scalar() or 0

        # 按创建时间倒序
        query = query.order_by(OperationLog.created_at.desc())
        query = query.offset(skip).limit(limit)

        result = await db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def delete(self, db: AsyncSession, *, id: int) -> Optional[OperationLog]:
        """删除操作日志"""
        db_obj = await self.get(db, id=id)
        if db_obj:
            await db.delete(db_obj)
            await db.commit()
        return db_obj

    async def get_stats(
        self,
        db: AsyncSession,
        *,
        start_time: int,
        end_time: int,
        include_prev: bool = True,
    ) -> dict[str, Any]:
        """获取操作日志聚合统计指标

        在单个 SQL 中聚合：
          - total:    总数
          - users:    不重复的操作用户数
          - actions:  不重复的操作类型数
          - abnormal: 异常操作数（response_status >= 400）

        可选计算 prev_*（与当前区间等长的上一窗口），便于前端展示环比。

        Args:
            start_time: Unix 秒起始时间
            end_time:   Unix 秒结束时间
            include_prev: 是否同时计算上一窗口指标

        Returns:
            dict 包含 total / users / actions / abnormal 及 prev_* 字段
        """
        start_dt = datetime.fromtimestamp(start_time)
        end_dt = datetime.fromtimestamp(end_time)

        async def _calc(start: datetime, end: datetime) -> dict[str, int]:
            stmt = select(
                func.count().label("total"),
                func.count(func.distinct(OperationLog.username)).label("users"),
                func.count(func.distinct(OperationLog.action)).label("actions"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                OperationLog.response_status >= 400,
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("abnormal"),
            ).where(
                OperationLog.created_at >= start,
                OperationLog.created_at <= end,
            )
            result = await db.execute(stmt)
            row = result.one()
            return {
                "total": int(row.total or 0),
                "users": int(row.users or 0),
                "actions": int(row.actions or 0),
                "abnormal": int(row.abnormal or 0),
            }

        current = await _calc(start_dt, end_dt)

        if include_prev and start_dt < end_dt:
            delta = end_dt - start_dt
            prev_end = start_dt
            prev_start = start_dt - delta
            prev = await _calc(prev_start, prev_end)
            current["prev_total"] = prev["total"]
            current["prev_users"] = prev["users"]
            current["prev_actions"] = prev["actions"]
            current["prev_abnormal"] = prev["abnormal"]

        return current


operation_log_crud = OperationLogCRUD()