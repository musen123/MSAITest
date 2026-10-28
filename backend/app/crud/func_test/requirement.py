"""测试需求 CRUD"""

from datetime import datetime
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.func_test.requirement import (
    RequirementStatus,
    TestRequirement,
)


class CRUDRequirement:
    """测试需求 CRUD"""

    async def create(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        title: str,
        created_by: int,
        code: Optional[str] = None,
        module_id: Optional[int] = None,
        priority: str = "medium",
        status: Optional[str] = None,
        description: Optional[str] = None,
        acceptance_criteria: Optional[str] = None,
        understood_content: Optional[str] = None,
        attachments: Optional[list] = None,
        source: str = "manual",
        document_id: Optional[int] = None,
    ) -> TestRequirement:
        req = TestRequirement(
            project_id=project_id,
            title=title,
            code=code or await self._generate_code(db, project_id),
            module_id=module_id,
            priority=priority,
            status=status or RequirementStatus.DRAFT.value,
            description=description,
            acceptance_criteria=acceptance_criteria,
            understood_content=understood_content,
            attachments=attachments,
            source=source,
            document_id=document_id,
            created_by=created_by,
        )
        db.add(req)
        await db.commit()
        await db.refresh(req)
        return req

    async def _generate_code(self, db: AsyncSession, project_id: int) -> str:
        """生成需求编号：REQ-{project_id}-{4位序号}"""
        stmt = select(func.count()).where(TestRequirement.project_id == project_id)
        n = await db.scalar(stmt)
        return f"REQ-{project_id}-{(n or 0) + 1:04d}"

    async def get(
        self, db: AsyncSession, req_id: int
    ) -> Optional[TestRequirement]:
        req = await db.get(TestRequirement, req_id)
        if req is None or req.is_deleted:
            return None
        return req

    async def get_by_project(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        status: Optional[str] = None,
        source: Optional[str] = None,
        module_id: Optional[int] = None,
        keyword: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[TestRequirement], int]:
        cond = [
            TestRequirement.project_id == project_id,
            TestRequirement.is_deleted == False,  # noqa: E712
        ]
        if status:
            cond.append(TestRequirement.status == status)
        if source:
            cond.append(TestRequirement.source == source)
        if module_id is not None:
            cond.append(TestRequirement.module_id == module_id)
        if keyword:
            cond.append(
                or_(
                    TestRequirement.title.like(f"%{keyword}%"),
                    TestRequirement.code.like(f"%{keyword}%"),
                )
            )

        stmt = (
            select(TestRequirement)
            .where(*cond)
            .order_by(TestRequirement.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        count_stmt = select(func.count()).select_from(TestRequirement).where(*cond)

        reqs = list((await db.execute(stmt)).scalars().all())
        total = (await db.execute(count_stmt)).scalar_one_or_none() or 0
        return reqs, total

    async def update(
        self,
        db: AsyncSession,
        *,
        req: TestRequirement,
        **kwargs,
    ) -> TestRequirement:
        for field in (
            "title",
            "code",
            "module_id",
            "priority",
            "status",
            "description",
            "acceptance_criteria",
            "understood_content",
            "attachments",
        ):
            val = kwargs.get(field)
            if val is not None:
                setattr(req, field, val)
        db.add(req)
        await db.commit()
        await db.refresh(req)
        return req

    async def soft_delete(
        self, db: AsyncSession, *, req: TestRequirement
    ) -> None:
        req.is_deleted = True
        req.deleted_at = datetime.now()
        db.add(req)
        await db.commit()

    async def review(
        self,
        db: AsyncSession,
        *,
        req: TestRequirement,
        action: str,
        reviewer_id: int,
        review_comment: Optional[str] = None,
    ) -> TestRequirement:
        """审核需求：approve→published / reject→draft"""
        req.status = (
            RequirementStatus.PUBLISHED.value
            if action == "approve"
            else RequirementStatus.DRAFT.value
        )
        req.reviewed_by = reviewer_id
        req.reviewed_at = datetime.now()
        req.review_comment = review_comment
        db.add(req)
        await db.commit()
        await db.refresh(req)
        return req


crud_requirement = CRUDRequirement()
