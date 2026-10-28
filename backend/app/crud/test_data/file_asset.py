"""测试文件资产 CRUD

``name`` 是项目内引用键（${{file:名}}），服务层保证未删除记录内唯一
（不加 DB 唯一约束——软删后重名再建合法）。软删走 deleted_at；
文件本体删除由端点层在软删成功后按需处理（v1 保留存储便于恢复）。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.test_data.file_asset import TestFileAsset


class CRUDTestFileAsset:
    async def get(self, db: AsyncSession, asset_id: int) -> Optional[TestFileAsset]:
        return await db.get(TestFileAsset, asset_id)

    async def get_detail(
        self, db: AsyncSession, *, asset_id: int, project_id: int
    ) -> Optional[TestFileAsset]:
        stmt = select(TestFileAsset).where(
            TestFileAsset.id == asset_id,
            TestFileAsset.project_id == project_id,
            TestFileAsset.deleted_at.is_(None),
        )
        return (await db.execute(stmt)).scalars().first()

    async def get_by_name(
        self, db: AsyncSession, *, project_id: int, name: str
    ) -> Optional[TestFileAsset]:
        """按引用键取资产（${{file:名}} 渲染期解析用）。"""
        stmt = select(TestFileAsset).where(
            TestFileAsset.project_id == project_id,
            TestFileAsset.name == name,
            TestFileAsset.deleted_at.is_(None),
        )
        return (await db.execute(stmt)).scalars().first()

    async def get_by_file_name(
        self, db: AsyncSession, *, project_id: int, file_name: str
    ) -> Optional[TestFileAsset]:
        """按原始文件名兜底解析（${{file:资产名}} 渲染期 get_by_name 未命中时用）。

        AI 生成/人工编写脚本时容易把「原始文件名」（如 product_main.png）误当成
        「资产名」（如 商品主图）引用——两者在数据中心目录里都展示过，一眼看去都像
        标识符。项目内该文件名若唯一，按它兜底找到同一份资产；若多个资产同名文件
        （如两次分别上传了同名 png），不猜，交回调用方按未命中处理，避免误绑错误文件。
        """
        stmt = select(TestFileAsset).where(
            TestFileAsset.project_id == project_id,
            TestFileAsset.file_name == file_name,
            TestFileAsset.deleted_at.is_(None),
        )
        rows = list((await db.execute(stmt)).scalars().all())
        return rows[0] if len(rows) == 1 else None

    async def list_by_project(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        keyword: Optional[str] = None,
        source: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[TestFileAsset], int]:
        cond = [
            TestFileAsset.project_id == project_id,
            TestFileAsset.deleted_at.is_(None),
        ]
        if keyword:
            cond.append(TestFileAsset.name.like(f"%{keyword}%"))
        if source:
            cond.append(TestFileAsset.source == source)
        stmt = (
            select(TestFileAsset)
            .where(*cond)
            .order_by(TestFileAsset.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        count_stmt = select(func.count()).select_from(TestFileAsset).where(*cond)
        items = list((await db.execute(stmt)).scalars().all())
        total = (await db.execute(count_stmt)).scalar_one_or_none() or 0
        return items, total

    async def create(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        created_by: Optional[int],
        name: str,
        file_name: str,
        storage_key: str,
        mime: Optional[str] = None,
        size_bytes: Optional[int] = None,
        source: str = "manual",
        spec: Optional[str] = None,
        ai_task_id: Optional[int] = None,
    ) -> TestFileAsset:
        obj = TestFileAsset(
            project_id=project_id,
            created_by=created_by,
            name=name,
            file_name=file_name,
            storage_key=storage_key,
            mime=mime,
            size_bytes=size_bytes,
            source=source,
            spec=spec,
            ai_task_id=ai_task_id,
        )
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj

    async def update(
        self, db: AsyncSession, *, db_obj: TestFileAsset, values: dict
    ) -> TestFileAsset:
        for field, value in values.items():
            if value is not None:
                setattr(db_obj, field, value)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def soft_delete(
        self, db: AsyncSession, *, asset_id: int, project_id: int
    ) -> bool:
        stmt = (
            update(TestFileAsset)
            .where(
                TestFileAsset.id == asset_id,
                TestFileAsset.project_id == project_id,
                TestFileAsset.deleted_at.is_(None),
            )
            .values(deleted_at=datetime.utcnow())
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0


crud_test_file_asset = CRUDTestFileAsset()
