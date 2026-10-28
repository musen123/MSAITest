"""知识库文档 CRUD"""

from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge.document import (
    KbDocSourceType,
    KbDocument,
    KbDocumentStatus,
)


class CRUDKbDocument:
    """知识库文档 CRUD"""

    async def create(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        file_name: str,
        file_size: int,
        file_ext: str,
        uploaded_by: int,
        storage_key: Optional[str] = None,
        doc_type: str = "other",
        source_type: str = KbDocSourceType.UPLOAD.value,
        source_id: Optional[int] = None,
        content_md: Optional[str] = None,
        content_hash: Optional[str] = None,
        status: str = KbDocumentStatus.PENDING.value,
    ) -> KbDocument:
        doc = KbDocument(
            project_id=project_id,
            file_name=file_name,
            file_size=file_size,
            file_ext=file_ext,
            uploaded_by=uploaded_by,
            storage_key=storage_key,
            doc_type=doc_type,
            source_type=source_type,
            source_id=source_id,
            content_md=content_md,
            content_hash=content_hash,
            status=status,
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        return doc

    async def get(self, db: AsyncSession, doc_id: int) -> Optional[KbDocument]:
        return await db.get(KbDocument, doc_id)

    async def get_by_content_hash(
        self, db: AsyncSession, *, project_id: int, content_hash: str
    ) -> Optional[KbDocument]:
        """按内容指纹取未删除文档（上传/插文本幂等去重,走 idx_kb_doc_project_hash）"""
        stmt = (
            select(KbDocument)
            .where(
                KbDocument.project_id == project_id,
                KbDocument.content_hash == content_hash,
                KbDocument.status != KbDocumentStatus.DELETED.value,
            )
            .order_by(KbDocument.id.desc())
            .limit(1)
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    async def get_by_source(
        self, db: AsyncSession, *, project_id: int, source_type: str, source_id: int
    ) -> Optional[KbDocument]:
        """按来源实体取活跃文档（func 桥幂等：同源重入库复用行而非重复建）"""
        stmt = (
            select(KbDocument)
            .where(
                KbDocument.project_id == project_id,
                KbDocument.source_type == source_type,
                KbDocument.source_id == source_id,
                KbDocument.status != KbDocumentStatus.DELETED.value,
            )
            .order_by(KbDocument.id.desc())
        )
        return (await db.execute(stmt)).scalars().first()

    async def list_by_project(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        status: Optional[str] = None,
        doc_type: Optional[str] = None,
        keyword: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[KbDocument], int]:
        cond = [
            KbDocument.project_id == project_id,
            KbDocument.status != KbDocumentStatus.DELETED.value,
        ]
        if status:
            cond.append(KbDocument.status == status)
        if doc_type:
            cond.append(KbDocument.doc_type == doc_type)
        if keyword:
            cond.append(KbDocument.file_name.like(f"%{keyword}%"))

        stmt = (
            select(KbDocument)
            .where(*cond)
            .order_by(KbDocument.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        count_stmt = select(func.count()).select_from(KbDocument).where(*cond)
        items = list((await db.execute(stmt)).scalars().all())
        total = (await db.execute(count_stmt)).scalar_one_or_none() or 0
        return items, total

    async def status_counts(
        self, db: AsyncSession, *, project_id: int
    ) -> dict[str, int]:
        """各状态文档数（列表页统计卡；本地 GROUP BY 替代 LightRAG 全局 status_counts）"""
        stmt = (
            select(KbDocument.status, func.count())
            .where(
                KbDocument.project_id == project_id,
                KbDocument.status != KbDocumentStatus.DELETED.value,
            )
            .group_by(KbDocument.status)
        )
        return {row[0]: int(row[1]) for row in (await db.execute(stmt)).all()}

    async def update_status(
        self,
        db: AsyncSession,
        *,
        doc: KbDocument,
        status: str,
        error_message: Optional[str] = None,
    ) -> KbDocument:
        doc.status = status
        if error_message is not None:
            doc.error_message = error_message
        if status == KbDocumentStatus.READY.value:
            doc.processed_at = datetime.now()
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        return doc

    async def mark_deleted(
        self, db: AsyncSession, *, doc: KbDocument
    ) -> None:
        doc.status = KbDocumentStatus.DELETED.value
        db.add(doc)
        await db.commit()

    async def count_active(
        self, db: AsyncSession, *, project_id: int
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(KbDocument)
            .where(
                KbDocument.project_id == project_id,
                KbDocument.status != KbDocumentStatus.DELETED.value,
            )
        )
        return (await db.execute(stmt)).scalar_one_or_none() or 0


crud_kb_document = CRUDKbDocument()
