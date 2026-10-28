"""测试数据集 CRUD

镜像 crud/perf_test/dataset.py 风格（软删 deleted_at；行明文存读，内部测试平台）。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.test_data.dataset import TestDataset


def _cols_to_jsonable(columns) -> list[dict]:
    """TestDatasetColumn / dict 混合 → 纯 dict（可 JSON 落库）。"""
    out: list[dict] = []
    for c in columns or []:
        if hasattr(c, "model_dump"):
            out.append(c.model_dump())
        elif isinstance(c, dict):
            out.append(c)
    return out


class CRUDTestDataset:
    async def get(self, db: AsyncSession, dataset_id: int) -> Optional[TestDataset]:
        return await db.get(TestDataset, dataset_id)

    async def get_detail(
        self, db: AsyncSession, *, dataset_id: int, project_id: int
    ) -> Optional[TestDataset]:
        """按项目归属取数据集（鉴权后读取，未软删）。"""
        stmt = select(TestDataset).where(
            TestDataset.id == dataset_id,
            TestDataset.project_id == project_id,
            TestDataset.deleted_at.is_(None),
        )
        return (await db.execute(stmt)).scalars().first()

    async def get_by_name(
        self, db: AsyncSession, *, project_id: int, name: str
    ) -> Optional[TestDataset]:
        stmt = select(TestDataset).where(
            TestDataset.project_id == project_id,
            TestDataset.name == name,
            TestDataset.deleted_at.is_(None),
        )
        return (await db.execute(stmt)).scalars().first()

    async def list_by_project(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        keyword: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[TestDataset], int]:
        cond = [
            TestDataset.project_id == project_id,
            TestDataset.deleted_at.is_(None),
        ]
        if keyword:
            cond.append(TestDataset.name.like(f"%{keyword}%"))
        stmt = (
            select(TestDataset)
            .where(*cond)
            .order_by(TestDataset.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        count_stmt = select(func.count()).select_from(TestDataset).where(*cond)
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
        columns: Optional[list] = None,
        rows: Optional[list] = None,
        description: Optional[str] = None,
        source: str = "manual",
        ai_task_id: Optional[int] = None,
    ) -> TestDataset:
        rows = rows or []
        obj = TestDataset(
            project_id=project_id,
            created_by=created_by,
            name=name,
            description=description,
            columns=_cols_to_jsonable(columns),
            rows=rows,
            row_count=len(rows),
            source=source,
            ai_task_id=ai_task_id,
        )
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj

    async def update(
        self, db: AsyncSession, *, db_obj: TestDataset, values: dict
    ) -> TestDataset:
        """更新。values 含 rows 时回填 row_count。"""
        if "columns" in values:
            values["columns"] = _cols_to_jsonable(values["columns"])
        if "rows" in values:
            values["rows"] = values["rows"] or []
            values["row_count"] = len(values["rows"])
        for field, value in values.items():
            setattr(db_obj, field, value)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def soft_delete(
        self, db: AsyncSession, *, dataset_id: int, project_id: int
    ) -> bool:
        stmt = (
            update(TestDataset)
            .where(
                TestDataset.id == dataset_id,
                TestDataset.project_id == project_id,
                TestDataset.deleted_at.is_(None),
            )
            .values(deleted_at=datetime.utcnow())
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0


crud_test_dataset = CRUDTestDataset()
