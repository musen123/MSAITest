"""
Bug CRUD 操作
"""

from datetime import date, datetime
from uuid import uuid4
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.bug.bug import Bug, BugStatus

# 合法的状态流转映射
_VALID_TRANSITIONS: dict[str, set[str]] = {
    BugStatus.NEW.value: {
        BugStatus.ASSIGNED.value,
        BugStatus.POSTPONED.value,
        BugStatus.WONTFIX.value,
    },
    BugStatus.ASSIGNED.value: {
        BugStatus.IN_PROGRESS.value,
        BugStatus.POSTPONED.value,
        BugStatus.WONTFIX.value,
    },
    BugStatus.IN_PROGRESS.value: {
        BugStatus.RESOLVED.value,
        BugStatus.POSTPONED.value,
        BugStatus.WONTFIX.value,
    },
    BugStatus.RESOLVED.value: {
        BugStatus.VERIFIED.value,
        BugStatus.REOPENED.value,
        BugStatus.CLOSED.value,
    },
    BugStatus.VERIFIED.value: {
        BugStatus.CLOSED.value,
        BugStatus.REOPENED.value,
    },
    BugStatus.REOPENED.value: {
        BugStatus.ASSIGNED.value,
        BugStatus.IN_PROGRESS.value,
        BugStatus.POSTPONED.value,
        BugStatus.WONTFIX.value,
    },
    BugStatus.CLOSED.value: set(),
    BugStatus.POSTPONED.value: {
        BugStatus.ASSIGNED.value,
        BugStatus.WONTFIX.value,
    },
    BugStatus.WONTFIX.value: set(),
}


def is_valid_transition(from_status: str, to_status: str) -> bool:
    """检查状态流转是否合法。"""
    return to_status in _VALID_TRANSITIONS.get(from_status, set())


class CRUDBug:
    """Bug CRUD 操作类"""

    async def create(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        created_by: int,
        title: str,
        description: str,
        severity: str,
        priority: str,
        module_id: Optional[int] = None,
        test_case_id: Optional[int] = None,
        test_case_type: Optional[str] = None,
        assigned_to: Optional[int] = None,
        environment: Optional[str] = None,
        reproduction_steps: Optional[str] = None,
        expected_result: Optional[str] = None,
        actual_result: Optional[str] = None,
        tags: Optional[list] = None,
        external_bug_key: Optional[str] = None,
        commit: bool = True,
    ) -> Bug:
        """
        创建 Bug，自动生成 bug_key。

        Args:
            db: 数据库会话
            project_id: 项目 ID
            created_by: 创建人用户 ID
            title: Bug 标题
            description: 详细描述
            severity: 严重程度
            priority: 优先级
            module_id: 关联模块 ID
            test_case_id: 关联测试用例 ID
            test_case_type: 用例类型
            assigned_to: 指派给用户 ID
            environment: 发现环境
            reproduction_steps: 复现步骤
            expected_result: 预期结果
            actual_result: 实际结果
            tags: 标签列表
            external_bug_key: 外部系统编号
            commit: 为 True 时立即提交并 refresh；为 False 时仅 flush
                （拿到自增主键），由调用方在同一事务内串联后续写入后统一提交

        Returns:
            Bug: 创建的 Bug 实例
        """
        initial_status = (
            BugStatus.ASSIGNED.value if assigned_to else BugStatus.NEW.value
        )

        bug = Bug(
            project_id=project_id,
            # 先用事务内唯一占位值 flush 拿到 DB 自增 ID；
            # 再由 ID 生成最终编号，避免 count/max 后 insert 的并发冲突。
            bug_key=f"PENDING-{uuid4().hex}",
            title=title,
            description=description,
            severity=severity,
            priority=priority,
            status=initial_status,
            module_id=module_id,
            test_case_id=test_case_id,
            test_case_type=test_case_type,
            assigned_to=assigned_to,
            environment=environment,
            reproduction_steps=reproduction_steps,
            expected_result=expected_result,
            actual_result=actual_result,
            tags=tags,
            external_bug_key=external_bug_key,
            is_archived=False,
            created_by=created_by,
        )
        db.add(bug)
        await db.flush()
        bug.bug_key = f"BUG-{date.today():%Y%m%d}-{bug.id:04d}"
        if commit:
            await db.commit()
            await db.refresh(bug)
        else:
            # 仅 flush 落库拿到自增主键，不结束事务，
            # 让调用方在同一事务内串联后续写入（如历史记录）后统一提交。
            await db.flush()
        return bug

    async def get(self, db: AsyncSession, bug_id: int) -> Optional[Bug]:
        """根据 ID 获取 Bug（含软删除记录）。"""
        return await db.get(Bug, bug_id)

    async def get_active(
        self, db: AsyncSession, bug_id: int, project_id: int
    ) -> Optional[Bug]:
        """
        获取未删除的 Bug，并校验项目归属。

        Returns:
            Bug 实例，不存在或已删除返回 None
        """
        bug = await db.get(Bug, bug_id)
        if not bug or bug.project_id != project_id or bug.deleted_at is not None:
            return None
        return bug

    async def get_list(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        priority: Optional[str] = None,
        assigned_to: Optional[int] = None,
        module_id: Optional[int] = None,
        created_by: Optional[int] = None,
        keyword: Optional[str] = None,
        is_archived: bool = False,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Bug], int]:
        """
        获取 Bug 列表，支持多条件筛选与分页。

        Returns:
            tuple[list[Bug], int]: (Bug 列表, 总数)
        """
        conditions = [
            Bug.project_id == project_id,
            Bug.deleted_at.is_(None),
            Bug.is_archived.is_(is_archived),
        ]

        if status:
            conditions.append(Bug.status == status)
        if severity:
            conditions.append(Bug.severity == severity)
        if priority:
            conditions.append(Bug.priority == priority)
        if assigned_to is not None:
            conditions.append(Bug.assigned_to == assigned_to)
        if module_id is not None:
            conditions.append(Bug.module_id == module_id)
        if created_by is not None:
            conditions.append(Bug.created_by == created_by)
        if keyword:
            conditions.append(
                Bug.title.ilike(f"%{keyword}%") | Bug.bug_key.ilike(f"%{keyword}%")
            )

        stmt = (
            select(Bug)
            .where(*conditions)
            .options(
                selectinload(Bug.assignee),
                selectinload(Bug.module),
                selectinload(Bug.creator),
            )
            .order_by(Bug.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        count_stmt = select(func.count()).select_from(Bug).where(*conditions)

        result = await db.execute(stmt)
        bugs = list(result.scalars().all())

        count_result = await db.execute(count_stmt)
        total = count_result.scalar_one_or_none() or 0

        return bugs, total

    async def update(
        self,
        db: AsyncSession,
        *,
        bug: Bug,
        title: Optional[str] = None,
        description: Optional[str] = None,
        severity: Optional[str] = None,
        priority: Optional[str] = None,
        module_id: Optional[int] = None,
        test_case_id: Optional[int] = None,
        test_case_type: Optional[str] = None,
        environment: Optional[str] = None,
        reproduction_steps: Optional[str] = None,
        expected_result: Optional[str] = None,
        actual_result: Optional[str] = None,
        tags: Optional[list] = None,
        external_bug_key: Optional[str] = None,
    ) -> Bug:
        """
        更新 Bug 基本信息（不包含状态和指派人）。

        Returns:
            Bug: 更新后的 Bug 实例
        """
        if title is not None:
            bug.title = title
        if description is not None:
            bug.description = description
        if severity is not None:
            bug.severity = severity
        if priority is not None:
            bug.priority = priority
        if module_id is not None:
            bug.module_id = module_id
        if test_case_id is not None:
            bug.test_case_id = test_case_id
        if test_case_type is not None:
            bug.test_case_type = test_case_type
        if environment is not None:
            bug.environment = environment
        if reproduction_steps is not None:
            bug.reproduction_steps = reproduction_steps
        if expected_result is not None:
            bug.expected_result = expected_result
        if actual_result is not None:
            bug.actual_result = actual_result
        if tags is not None:
            bug.tags = tags
        if external_bug_key is not None:
            bug.external_bug_key = external_bug_key

        bug.updated_at = datetime.utcnow()
        db.add(bug)
        await db.commit()
        await db.refresh(bug)
        return bug

    async def change_status(
        self,
        db: AsyncSession,
        *,
        bug: Bug,
        new_status: str,
    ) -> Bug:
        """
        变更 Bug 状态（不校验合法性，由调用方保证）。

        Returns:
            Bug: 更新后的 Bug 实例
        """
        bug.status = new_status
        bug.updated_at = datetime.utcnow()
        db.add(bug)
        await db.commit()
        await db.refresh(bug)
        return bug

    async def assign(
        self,
        db: AsyncSession,
        *,
        bug: Bug,
        assigned_to: int,
    ) -> Bug:
        """
        指派 Bug，若当前状态为 new 则自动流转为 assigned。

        Returns:
            Bug: 更新后的 Bug 实例
        """
        bug.assigned_to = assigned_to
        if bug.status == BugStatus.NEW.value:
            bug.status = BugStatus.ASSIGNED.value
        bug.updated_at = datetime.utcnow()
        db.add(bug)
        await db.commit()
        await db.refresh(bug)
        return bug

    async def archive(
        self,
        db: AsyncSession,
        *,
        bug: Bug,
        is_archived: bool,
    ) -> Bug:
        """
        归档或取消归档 Bug。

        Returns:
            Bug: 更新后的 Bug 实例
        """
        bug.is_archived = is_archived
        bug.updated_at = datetime.utcnow()
        db.add(bug)
        await db.commit()
        await db.refresh(bug)
        return bug

    async def soft_delete(self, db: AsyncSession, *, bug: Bug) -> None:
        """软删除 Bug（设置 deleted_at 和 is_deleted）。"""
        bug.deleted_at = datetime.utcnow()
        bug.is_deleted = True
        db.add(bug)
        await db.commit()

    async def get_statistics(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> dict:
        """
        获取 Bug 统计数据。

        Returns:
            dict: 包含各维度统计的字典
        """
        base_cond = [Bug.project_id == project_id, Bug.deleted_at.is_(None)]
        if start_date:
            base_cond.append(
                Bug.created_at >= datetime.combine(start_date, datetime.min.time())
            )
        if end_date:
            base_cond.append(
                Bug.created_at <= datetime.combine(end_date, datetime.max.time())
            )

        total_stmt = select(func.count()).select_from(Bug).where(*base_cond)
        total_result = await db.execute(total_stmt)
        total = total_result.scalar_one_or_none() or 0

        status_stmt = (
            select(Bug.status, func.count().label("cnt"))
            .where(*base_cond)
            .group_by(Bug.status)
        )
        severity_stmt = (
            select(Bug.severity, func.count().label("cnt"))
            .where(*base_cond)
            .group_by(Bug.severity)
        )
        priority_stmt = (
            select(Bug.priority, func.count().label("cnt"))
            .where(*base_cond)
            .group_by(Bug.priority)
        )

        status_result = await db.execute(status_stmt)
        severity_result = await db.execute(severity_stmt)
        priority_result = await db.execute(priority_stmt)

        by_status = {row.status: row.cnt for row in status_result.all()}
        by_severity = {row.severity: row.cnt for row in severity_result.all()}
        by_priority = {row.priority: row.cnt for row in priority_result.all()}

        resolved_count = (
            by_status.get("resolved", 0)
            + by_status.get("verified", 0)
            + by_status.get("closed", 0)
        )
        resolution_rate = round(resolved_count / total * 100, 1) if total > 0 else 0.0

        return {
            "total": total,
            "by_status": by_status,
            "by_severity": by_severity,
            "by_priority": by_priority,
            "resolution_rate": resolution_rate,
            "avg_resolution_hours": None,
        }

    async def get_trends(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        days: int = 30,
    ) -> dict:
        """
        获取近 N 天的 Bug 趋势数据。

        Returns:
            dict: dates/created/resolved/closed 三条时间序列
        """
        from datetime import timedelta

        today = date.today()
        date_list = [today - timedelta(days=i) for i in range(days - 1, -1, -1)]
        date_strs = [d.strftime("%Y-%m-%d") for d in date_list]
        date_set = set(date_strs)

        start_dt = datetime.combine(today - timedelta(days=days - 1), datetime.min.time())
        end_dt = datetime.combine(today, datetime.max.time())

        # 一次性查询：按日期+状态分组统计创建数
        created_stmt = (
            select(
                func.date(Bug.created_at).label("date"),
                func.count().label("cnt"),
            )
            .where(
                Bug.project_id == project_id,
                Bug.created_at >= start_dt,
                Bug.created_at <= end_dt,
                Bug.deleted_at.is_(None),
            )
            .group_by(func.date(Bug.created_at))
        )
        created_result = await db.execute(created_stmt)
        created_map = {str(row.date): row.cnt for row in created_result.all()}

        # 一次性查询：按日期+状态分组统计解决/关闭数
        trends_stmt = (
            select(
                func.date(Bug.updated_at).label("date"),
                Bug.status,
                func.count().label("cnt"),
            )
            .where(
                Bug.project_id == project_id,
                Bug.updated_at >= start_dt,
                Bug.updated_at <= end_dt,
                Bug.deleted_at.is_(None),
                Bug.status.in_([BugStatus.RESOLVED.value, BugStatus.CLOSED.value]),
            )
            .group_by(func.date(Bug.updated_at), Bug.status)
        )
        trends_result = await db.execute(trends_stmt)

        resolved_map: dict[str, int] = {}
        closed_map: dict[str, int] = {}
        for row in trends_result.all():
            d = str(row.date)
            if row.status == BugStatus.RESOLVED.value:
                resolved_map[d] = row.cnt
            elif row.status == BugStatus.CLOSED.value:
                closed_map[d] = row.cnt

        created_counts = [created_map.get(d, 0) for d in date_strs]
        resolved_counts = [resolved_map.get(d, 0) for d in date_strs]
        closed_counts = [closed_map.get(d, 0) for d in date_strs]

        return {
            "dates": date_strs,
            "created": created_counts,
            "resolved": resolved_counts,
            "closed": closed_counts,
        }


crud_bug = CRUDBug()

# 版权声明：此代码为木森老师自动化测试ai智能体开发课程2503期的配套代码，版权为木森老师所有，仅用于教学和学习，不用于商业用途。
# 请在进行商业用途使用前，先联系木森老师（微信：python771 或邮箱：121292679@qq.com）确认授权。
# 倒卖课程和代码将被视为侵权行为，将被法律追究。
