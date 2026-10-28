"""功能测试用例 CRUD"""

from datetime import datetime
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.func_test.test_case import (
    CaseSource,
    CaseStatus,
    FuncTestCase,
)

# 可评审状态：草稿可直接评审（与需求审核口径一致），已评审/已废弃不可改写
REVIEWABLE_STATUSES = (
    CaseStatus.DRAFT.value,
    CaseStatus.PENDING_REVIEW.value,
)


class CRUDTestCase:
    """功能测试用例 CRUD"""

    async def create(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        title: str,
        created_by: int,
        code: Optional[str] = None,
        requirement_id: Optional[int] = None,
        module_id: Optional[int] = None,
        priority: str = "medium",
        case_type: str = "functional",
        validation_level: str = "system",
        status: Optional[str] = None,
        preconditions: Optional[str] = None,
        test_data: Optional[dict] = None,
        steps: Optional[list] = None,
        expected_result: Optional[list] = None,
        tags: Optional[list] = None,
        ui_automatable: Optional[bool] = None,
        review_info: Optional[dict] = None,
        source: str = CaseSource.MANUAL.value,
    ) -> FuncTestCase:
        case = FuncTestCase(
            project_id=project_id,
            code=code or await self._generate_code(db, project_id),
            title=title,
            requirement_id=requirement_id,
            module_id=module_id,
            priority=priority,
            case_type=case_type,
            validation_level=validation_level,
            preconditions=preconditions,
            test_data=test_data,
            steps=steps,
            expected_result=expected_result,
            tags=tags,
            ui_automatable=ui_automatable,
            review_info=review_info,
            source=source,
            created_by=created_by,
        )
        if status:
            case.status = status
        db.add(case)
        await db.commit()
        await db.refresh(case)
        return case

    async def _generate_code(self, db: AsyncSession, project_id: int) -> str:
        stmt = select(func.count()).where(FuncTestCase.project_id == project_id)
        n = await db.scalar(stmt)
        return f"TC-{project_id}-{(n or 0) + 1:04d}"

    async def get(
        self, db: AsyncSession, case_id: int
    ) -> Optional[FuncTestCase]:
        case = await db.get(FuncTestCase, case_id)
        if case is None or case.is_deleted:
            return None
        return case

    async def get_by_project(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        requirement_id: Optional[int] = None,
        module_id: Optional[int] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        source: Optional[str] = None,
        keyword: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[FuncTestCase], int]:
        cond = [
            FuncTestCase.project_id == project_id,
            FuncTestCase.is_deleted == False,  # noqa: E712
        ]
        if requirement_id is not None:
            cond.append(FuncTestCase.requirement_id == requirement_id)
        if module_id is not None:
            cond.append(FuncTestCase.module_id == module_id)
        if status:
            cond.append(FuncTestCase.status == status)
        if priority:
            cond.append(FuncTestCase.priority == priority)
        if source:
            cond.append(FuncTestCase.source == source)
        if keyword:
            cond.append(
                or_(
                    FuncTestCase.title.like(f"%{keyword}%"),
                    FuncTestCase.code.like(f"%{keyword}%"),
                )
            )

        stmt = (
            select(FuncTestCase)
            .where(*cond)
            .order_by(FuncTestCase.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        count_stmt = select(func.count()).select_from(FuncTestCase).where(*cond)

        items = list((await db.execute(stmt)).scalars().all())
        total = (await db.execute(count_stmt)).scalar_one_or_none() or 0
        return items, total

    async def list_by_requirement(
        self,
        db: AsyncSession,
        *,
        requirement_id: int,
    ) -> list[FuncTestCase]:
        """获取需求关联的所有用例（用于补充生成时拿已有用例）"""
        stmt = (
            select(FuncTestCase)
            .where(
                FuncTestCase.requirement_id == requirement_id,
                FuncTestCase.is_deleted == False,  # noqa: E712
            )
            .order_by(FuncTestCase.created_at.asc())
        )
        return list((await db.execute(stmt)).scalars().all())

    async def update(
        self,
        db: AsyncSession,
        *,
        case: FuncTestCase,
        updated_by: Optional[int] = None,
        **kwargs,
    ) -> FuncTestCase:
        for field in (
            "title",
            "code",
            "requirement_id",
            "module_id",
            "priority",
            "case_type",
            "validation_level",
            "status",
            "preconditions",
            "test_data",
            "steps",
            "expected_result",
            "tags",
            "ui_automatable",
            "review_info",
        ):
            val = kwargs.get(field)
            if val is not None:
                setattr(case, field, val)
        if updated_by is not None:
            case.updated_by = updated_by
        db.add(case)
        await db.commit()
        await db.refresh(case)
        return case

    def _apply_review(
        self,
        case: FuncTestCase,
        *,
        action: str,
        reviewer_id: int,
        review_comment: Optional[str] = None,
    ) -> None:
        case.status = (
            CaseStatus.REVIEWED.value
            if action == "approve"
            else CaseStatus.DRAFT.value
        )
        case.reviewed_by = reviewer_id
        case.reviewed_at = datetime.now()
        case.review_comment = review_comment

    async def review(
        self,
        db: AsyncSession,
        *,
        case: FuncTestCase,
        action: str,
        reviewer_id: int,
        review_comment: Optional[str] = None,
    ) -> FuncTestCase:
        """评审用例：approve→reviewed / reject→draft"""
        self._apply_review(
            case,
            action=action,
            reviewer_id=reviewer_id,
            review_comment=review_comment,
        )
        db.add(case)
        await db.commit()
        await db.refresh(case)
        return case

    async def batch_review(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        case_ids: list[int],
        action: str,
        reviewer_id: int,
        review_comment: Optional[str] = None,
    ) -> int:
        """批量评审，返回实际处理条数

        仅处理本项目未删除、且处于可评审状态（draft/pending_review）
        的用例；reviewed/deprecated 直接跳过，避免已废弃用例被改写。
        """
        stmt = select(FuncTestCase).where(
            FuncTestCase.project_id == project_id,
            FuncTestCase.id.in_(case_ids),
            FuncTestCase.is_deleted == False,  # noqa: E712
            FuncTestCase.status.in_(REVIEWABLE_STATUSES),
        )
        cases = list((await db.execute(stmt)).scalars().all())
        for case in cases:
            self._apply_review(
                case,
                action=action,
                reviewer_id=reviewer_id,
                review_comment=review_comment,
            )
            db.add(case)
        await db.commit()
        return len(cases)

    async def soft_delete(
        self, db: AsyncSession, *, case: FuncTestCase
    ) -> None:
        case.is_deleted = True
        case.deleted_at = datetime.now()
        db.add(case)
        await db.commit()

    async def bulk_create(
        self,
        db: AsyncSession,
        *,
        cases: list[FuncTestCase],
    ) -> int:
        """批量插入用例（不逐条 commit，用于工作流批量写入）"""
        for c in cases:
            db.add(c)
        await db.commit()
        return len(cases)


crud_test_case = CRUDTestCase()
