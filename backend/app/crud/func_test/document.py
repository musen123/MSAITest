"""项目文档 CRUD"""

from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.func_test.document import DocumentStatus, ProjectDocument


class CRUDDocument:
    """项目文档 CRUD"""

    async def create(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        name: str,
        doc_type: str,
        file_name: str,
        file_path: str,
        file_size: int,
        file_ext: str,
        uploaded_by: int,
        description: Optional[str] = None,
        version: Optional[str] = None,
    ) -> ProjectDocument:
        doc = ProjectDocument(
            project_id=project_id,
            name=name,
            doc_type=doc_type,
            file_name=file_name,
            file_path=file_path,
            file_size=file_size,
            file_ext=file_ext,
            uploaded_by=uploaded_by,
            description=description,
            version=version,
            status=DocumentStatus.ACTIVE.value,
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        return doc

    async def get(
        self, db: AsyncSession, doc_id: int
    ) -> Optional[ProjectDocument]:
        doc = await db.get(ProjectDocument, doc_id)
        if doc is None or doc.is_deleted:
            return None
        return doc

    async def get_by_project(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        doc_type: Optional[str] = None,
        keyword: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[ProjectDocument], int]:
        cond = [
            ProjectDocument.project_id == project_id,
            ProjectDocument.is_deleted == False,  # noqa: E712
        ]
        if doc_type:
            cond.append(ProjectDocument.doc_type == doc_type)
        if keyword:
            cond.append(ProjectDocument.name.like(f"%{keyword}%"))

        stmt = (
            select(ProjectDocument)
            .where(*cond)
            .order_by(ProjectDocument.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        count_stmt = select(func.count()).select_from(ProjectDocument).where(*cond)

        result = await db.execute(stmt)
        docs = list(result.scalars().all())

        total = (await db.execute(count_stmt)).scalar_one_or_none() or 0
        return docs, total

    async def update(
        self,
        db: AsyncSession,
        *,
        doc: ProjectDocument,
        name: Optional[str] = None,
        doc_type: Optional[str] = None,
        description: Optional[str] = None,
        version: Optional[str] = None,
    ) -> ProjectDocument:
        if name is not None:
            doc.name = name
        if doc_type is not None:
            doc.doc_type = doc_type
        if description is not None:
            doc.description = description
        if version is not None:
            doc.version = version
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        return doc

    async def soft_delete(
        self, db: AsyncSession, *, doc: ProjectDocument
    ) -> None:
        doc.is_deleted = True
        doc.deleted_at = datetime.now()
        doc.status = DocumentStatus.DELETED.value
        db.add(doc)
        await db.commit()


crud_document = CRUDDocument()
