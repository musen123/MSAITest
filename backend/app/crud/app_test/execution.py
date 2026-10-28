"""AppExecution（APP 自动化执行记录）CRUD"""

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_device.device import AppDevice
from app.models.app_test.execution import AppExecution
from app.models.app_test.script import AppScript


class CRUDAppExecution:
    """执行记录 CRUD（经 script 归属项目）"""

    async def get(self, db: AsyncSession, execution_id: int) -> Optional[AppExecution]:
        return await db.get(AppExecution, execution_id)

    async def get_in_project(
        self, db: AsyncSession, project_id: int, execution_id: int
    ) -> Optional[AppExecution]:
        """项目内取执行记录（join script 防跨项目越权读）"""
        stmt = (
            select(AppExecution)
            .join(AppScript, AppExecution.script_id == AppScript.id)
            .where(AppExecution.id == execution_id, AppScript.project_id == project_id)
        )
        return (await db.execute(stmt)).scalars().first()

    async def get_list(
        self,
        db: AsyncSession,
        project_id: int,
        *,
        script_id: Optional[int] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[tuple[AppExecution, str, str, Optional[str], Optional[str]]], int]:
        """执行记录列表（附用例名/用例平台 + 左连设备型号/平台，设备已删则 None）。

        返回 [(execution, script_name, script_platform, device_model, device_platform)], total
        """
        cond = [AppScript.project_id == project_id]
        if script_id is not None:
            cond.append(AppExecution.script_id == script_id)
        if status:
            cond.append(AppExecution.status == status)
        stmt = (
            select(
                AppExecution,
                AppScript.name,
                AppScript.platform,
                AppDevice.model,
                AppDevice.platform,
            )
            .join(AppScript, AppExecution.script_id == AppScript.id)
            .outerjoin(AppDevice, AppDevice.udid == AppExecution.device_udid)
            .where(*cond)
            .order_by(AppExecution.id.desc())
            .offset(skip)
            .limit(limit)
        )
        count_stmt = (
            select(func.count())
            .select_from(AppExecution)
            .join(AppScript, AppExecution.script_id == AppScript.id)
            .where(*cond)
        )
        rows = [tuple(r) for r in (await db.execute(stmt)).all()]
        total = (await db.execute(count_stmt)).scalar_one_or_none() or 0
        return rows, total

    async def get_by_suite_execution(
        self, db: AsyncSession, suite_execution_id: int
    ) -> list[tuple[AppExecution, str]]:
        """套件执行汇总下的用例级明细（附用例名，按 id 升序=执行顺序）"""
        stmt = (
            select(AppExecution, AppScript.name)
            .join(AppScript, AppExecution.script_id == AppScript.id)
            .where(AppExecution.suite_execution_id == suite_execution_id)
            .order_by(AppExecution.id.asc())
        )
        return [(e, n) for e, n in (await db.execute(stmt)).all()]

    async def create(
        self,
        db: AsyncSession,
        *,
        script_id: int,
        device_udid: str,
        ai_task_id: Optional[str] = None,
        status: str = "pending",
        retry_index: int = 0,
        suite_execution_id: Optional[int] = None,
    ) -> AppExecution:
        execution = AppExecution(
            script_id=script_id,
            device_udid=device_udid,
            ai_task_id=ai_task_id,
            status=status,
            retry_index=retry_index,
            suite_execution_id=suite_execution_id,
        )
        db.add(execution)
        await db.commit()
        await db.refresh(execution)
        return execution

    async def update(
        self, db: AsyncSession, execution: AppExecution, changes: dict
    ) -> AppExecution:
        for key, value in changes.items():
            setattr(execution, key, value)
        await db.commit()
        await db.refresh(execution)
        return execution


crud_app_execution = CRUDAppExecution()
