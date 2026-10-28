"""AppSuite / AppSuiteCase / AppSuiteExecution（APP 自动化套件）CRUD"""

from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_device.device import AppDevice
from app.models.app_test.script import AppScript
from app.models.app_test.suite import AppSuite, AppSuiteCase
from app.models.app_test.suite_execution import AppSuiteExecution


class CRUDAppSuite:
    """套件 CRUD（项目域；编排 = 全量替换语义）"""

    async def get(self, db: AsyncSession, suite_id: int) -> Optional[AppSuite]:
        return await db.get(AppSuite, suite_id)

    async def get_in_project(
        self, db: AsyncSession, project_id: int, suite_id: int
    ) -> Optional[AppSuite]:
        """项目内取套件（防跨项目越权读）"""
        stmt = select(AppSuite).where(
            AppSuite.id == suite_id, AppSuite.project_id == project_id
        )
        return (await db.execute(stmt)).scalars().first()

    async def get_list(
        self,
        db: AsyncSession,
        project_id: int,
        *,
        keyword: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[tuple[AppSuite, int]], int]:
        """套件列表（附编排用例数），返回 [(suite, case_count)], total"""
        cond = [AppSuite.project_id == project_id]
        if keyword:
            cond.append(AppSuite.name.like(f"%{keyword}%"))
        count_sub = (
            select(func.count())
            .select_from(AppSuiteCase)
            .where(AppSuiteCase.suite_id == AppSuite.id)
            .scalar_subquery()
        )
        stmt = (
            select(AppSuite, count_sub)
            .where(*cond)
            .order_by(AppSuite.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        count_stmt = select(func.count()).select_from(AppSuite).where(*cond)
        rows = [(s, int(c or 0)) for s, c in (await db.execute(stmt)).all()]
        total = (await db.execute(count_stmt)).scalar_one_or_none() or 0
        return rows, total

    async def create(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        name: str,
        description: Optional[str] = None,
        device_udid: Optional[str] = None,
        failure_strategy: str = "continue",
        created_by: Optional[int] = None,
    ) -> AppSuite:
        suite = AppSuite(
            project_id=project_id,
            name=name,
            description=description,
            device_udid=device_udid,
            failure_strategy=failure_strategy,
            created_by=created_by,
        )
        db.add(suite)
        await db.commit()
        await db.refresh(suite)
        return suite

    async def update(
        self, db: AsyncSession, suite: AppSuite, changes: dict
    ) -> AppSuite:
        for key, value in changes.items():
            setattr(suite, key, value)
        await db.commit()
        await db.refresh(suite)
        return suite

    async def remove(self, db: AsyncSession, suite: AppSuite) -> None:
        await db.delete(suite)
        await db.commit()

    async def replace_cases(
        self,
        db: AsyncSession,
        suite_id: int,
        items: list[dict],
    ) -> None:
        """全量替换编排：数组顺序即 sort_order；重复 script_id 保留首次出现。"""
        await db.execute(
            delete(AppSuiteCase).where(AppSuiteCase.suite_id == suite_id)
        )
        seen: set[int] = set()
        order = 0
        for item in items:
            script_id = int(item["script_id"])
            if script_id in seen:
                continue
            seen.add(script_id)
            db.add(
                AppSuiteCase(
                    suite_id=suite_id,
                    script_id=script_id,
                    sort_order=order,
                    enabled=bool(item.get("enabled", True)),
                )
            )
            order += 1
        await db.commit()

    async def get_cases_with_script(
        self, db: AsyncSession, suite_id: int
    ) -> list[tuple[AppSuiteCase, AppScript]]:
        """套件编排（JOIN 用例，按 sort_order；用例已被删的关联行经 CASCADE 不存在）"""
        stmt = (
            select(AppSuiteCase, AppScript)
            .join(AppScript, AppSuiteCase.script_id == AppScript.id)
            .where(AppSuiteCase.suite_id == suite_id)
            .order_by(AppSuiteCase.sort_order)
        )
        return [(c, s) for c, s in (await db.execute(stmt)).all()]


class CRUDAppSuiteExecution:
    """套件执行汇总 CRUD"""

    async def get(
        self, db: AsyncSession, execution_id: int
    ) -> Optional[AppSuiteExecution]:
        return await db.get(AppSuiteExecution, execution_id)

    async def get_in_project(
        self, db: AsyncSession, project_id: int, execution_id: int
    ) -> Optional[AppSuiteExecution]:
        stmt = select(AppSuiteExecution).where(
            AppSuiteExecution.id == execution_id,
            AppSuiteExecution.project_id == project_id,
        )
        return (await db.execute(stmt)).scalars().first()

    async def get_list(
        self,
        db: AsyncSession,
        project_id: int,
        *,
        suite_id: Optional[int] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[tuple[AppSuiteExecution, str, Optional[str], Optional[str]]], int]:
        """执行汇总列表（附套件名 + 左连设备型号/平台，设备已删则 None）。

        返回 [(execution, suite_name, device_model, device_platform)], total
        """
        cond = [AppSuiteExecution.project_id == project_id]
        if suite_id is not None:
            cond.append(AppSuiteExecution.suite_id == suite_id)
        if status:
            cond.append(AppSuiteExecution.status == status)
        stmt = (
            select(AppSuiteExecution, AppSuite.name, AppDevice.model, AppDevice.platform)
            .join(AppSuite, AppSuiteExecution.suite_id == AppSuite.id)
            .outerjoin(AppDevice, AppDevice.udid == AppSuiteExecution.device_udid)
            .where(*cond)
            .order_by(AppSuiteExecution.id.desc())
            .offset(skip)
            .limit(limit)
        )
        count_stmt = (
            select(func.count()).select_from(AppSuiteExecution).where(*cond)
        )
        rows = [tuple(r) for r in (await db.execute(stmt)).all()]
        total = (await db.execute(count_stmt)).scalar_one_or_none() or 0
        return rows, total

    async def create(
        self,
        db: AsyncSession,
        *,
        suite_id: int,
        project_id: int,
        device_udid: str,
        trigger_type: str = "manual",
        ai_task_id: Optional[str] = None,
        status: str = "pending",
        created_by: Optional[int] = None,
    ) -> AppSuiteExecution:
        execution = AppSuiteExecution(
            suite_id=suite_id,
            project_id=project_id,
            device_udid=device_udid,
            trigger_type=trigger_type,
            ai_task_id=ai_task_id,
            status=status,
            created_by=created_by,
        )
        db.add(execution)
        await db.commit()
        await db.refresh(execution)
        return execution

    async def update(
        self, db: AsyncSession, execution: AppSuiteExecution, changes: dict
    ) -> AppSuiteExecution:
        for key, value in changes.items():
            setattr(execution, key, value)
        await db.commit()
        await db.refresh(execution)
        return execution


crud_app_suite = CRUDAppSuite()
crud_app_suite_execution = CRUDAppSuiteExecution()
