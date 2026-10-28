"""
Bug 操作历史 CRUD 操作
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.bug.bug_history import BugHistory


class CRUDBugHistory:
    """Bug 操作历史 CRUD 操作类"""

    async def create(
        self,
        db: AsyncSession,
        *,
        bug_id: int,
        action: str,
        operated_by: int,
        from_value: str | None = None,
        to_value: str | None = None,
        comment: str | None = None,
        commit: bool = True,
    ) -> BugHistory:
        """
        记录一条 Bug 操作历史。

        Args:
            db: 数据库会话
            bug_id: Bug ID
            action: 操作类型（BugAction 枚举值）
            operated_by: 操作人用户 ID
            from_value: 变更前的值
            to_value: 变更后的值
            comment: 操作备注
            commit: 为 True 时立即提交并 refresh；为 False 时仅 flush，
                由调用方在同一事务内与关联写入（如 Bug 本体）统一提交

        Returns:
            BugHistory: 创建的历史记录实例
        """
        record = BugHistory(
            bug_id=bug_id,
            action=action,
            from_value=from_value,
            to_value=to_value,
            comment=comment,
            operated_by=operated_by,
        )
        db.add(record)
        if commit:
            await db.commit()
            await db.refresh(record)
        else:
            await db.flush()
        return record

    async def get_by_bug(
        self,
        db: AsyncSession,
        bug_id: int,
    ) -> list[BugHistory]:
        """
        获取 Bug 的所有操作历史，按操作时间升序排列。

        Args:
            db: 数据库会话
            bug_id: Bug ID

        Returns:
            list[BugHistory]: 操作历史列表
        """
        stmt = (
            select(BugHistory)
            .where(BugHistory.bug_id == bug_id)
            .options(selectinload(BugHistory.operator))
            .order_by(BugHistory.operated_at.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())


crud_bug_history = CRUDBugHistory()

# 版权声明：此代码为木森老师自动化测试ai智能体开发课程2503期的配套代码，版权为木森老师所有，仅用于教学和学习，不用于商业用途。
# 请在进行商业用途使用前，先联系木森老师（微信：python771 或邮箱：121292679@qq.com）确认授权。
# 倒卖课程和代码将被视为侵权行为，将被法律追究。
