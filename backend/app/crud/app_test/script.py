"""AppScript（APP 自动化用例）CRUD"""

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_test.script import AppScript


class CRUDAppScript:
    """用例 CRUD（项目域）"""

    async def get(self, db: AsyncSession, script_id: int) -> Optional[AppScript]:
        return await db.get(AppScript, script_id)

    async def get_in_project(
        self, db: AsyncSession, project_id: int, script_id: int
    ) -> Optional[AppScript]:
        """项目内取用例（防跨项目越权读）"""
        stmt = select(AppScript).where(
            AppScript.id == script_id, AppScript.project_id == project_id
        )
        return (await db.execute(stmt)).scalars().first()

    async def get_list(
        self,
        db: AsyncSession,
        project_id: int,
        *,
        keyword: Optional[str] = None,
        status: Optional[str] = None,
        platform: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[AppScript], int]:
        cond = [AppScript.project_id == project_id]
        if status:
            cond.append(AppScript.status == status)
        if platform:
            cond.append(AppScript.platform == platform)
        if keyword:
            cond.append(
                AppScript.name.like(f"%{keyword}%")
                | AppScript.target_app.like(f"%{keyword}%")
            )
        stmt = (
            select(AppScript)
            .where(*cond)
            .order_by(AppScript.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        count_stmt = select(func.count()).select_from(AppScript).where(*cond)
        items = list((await db.execute(stmt)).scalars().all())
        total = (await db.execute(count_stmt)).scalar_one_or_none() or 0
        return items, total

    async def create(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        name: str,
        yaml_content: str,
        platform: str = "android",
        target_app: Optional[str] = None,
        description: Optional[str] = None,
        status: str = "draft",
        created_by: Optional[int] = None,
    ) -> AppScript:
        script = AppScript(
            project_id=project_id,
            name=name,
            yaml_content=yaml_content,
            platform=platform,
            target_app=target_app,
            description=description,
            status=status,
            created_by=created_by,
        )
        db.add(script)
        await db.commit()
        await db.refresh(script)
        return script

    async def update(
        self, db: AsyncSession, script: AppScript, changes: dict
    ) -> AppScript:
        for key, value in changes.items():
            setattr(script, key, value)
        await db.commit()
        await db.refresh(script)
        return script

    async def remove(self, db: AsyncSession, script: AppScript) -> None:
        await db.delete(script)
        await db.commit()


crud_app_script = CRUDAppScript()
