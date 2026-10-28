"""项目知识库 CRUD"""

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge.knowledge_base import (
    KnowledgeBaseStatus,
    ProjectKnowledgeBase,
)


class CRUDKnowledgeBase:
    """项目知识库 CRUD"""

    async def get_by_project(
        self, db: AsyncSession, *, project_id: int
    ) -> Optional[ProjectKnowledgeBase]:
        stmt = select(ProjectKnowledgeBase).where(
            ProjectKnowledgeBase.project_id == project_id
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    async def get_or_create(
        self, db: AsyncSession, *, project_id: int
    ) -> ProjectKnowledgeBase:
        kb = await self.get_by_project(db, project_id=project_id)
        if kb:
            return kb
        kb = ProjectKnowledgeBase(
            project_id=project_id,
            status=KnowledgeBaseStatus.EMPTY.value,
        )
        db.add(kb)
        await db.commit()
        await db.refresh(kb)
        return kb

    async def update_status(
        self,
        db: AsyncSession,
        *,
        kb: ProjectKnowledgeBase,
        status: str,
        error_message: Optional[str] = None,
    ) -> ProjectKnowledgeBase:
        kb.status = status
        kb.error_message = error_message
        if status == KnowledgeBaseStatus.READY.value:
            kb.last_built_at = datetime.now()
        db.add(kb)
        await db.commit()
        await db.refresh(kb)
        return kb

    async def update_stats(
        self,
        db: AsyncSession,
        *,
        kb: ProjectKnowledgeBase,
        total_documents: Optional[int] = None,
        total_chunks: Optional[int] = None,
        total_nodes: Optional[int] = None,
        total_edges: Optional[int] = None,
        project_summary: Optional[str] = None,
    ) -> ProjectKnowledgeBase:
        if total_documents is not None:
            kb.total_documents = total_documents
        if total_chunks is not None:
            kb.total_chunks = total_chunks
        if total_nodes is not None:
            kb.total_nodes = total_nodes
        if total_edges is not None:
            kb.total_edges = total_edges
        if project_summary is not None:
            kb.project_summary = project_summary
        db.add(kb)
        await db.commit()
        await db.refresh(kb)
        return kb

    # ── 自研检索（设计文档 §6.1）────────────────────────

    async def bump_index_version(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        delta_chunks: int = 0,
        delta_documents: int = 0,
    ) -> None:
        """索引版本 +1 并原子增量计数（一切 kb_chunk 写路径的**唯一**收口）。

        - 纯 SQL 原子 UPDATE（`total = total + :n`），并发入库不丢账——
          修正 LightRAG 时代 sync_kb_stats 全局求和 + ORM 读改写的双重错账
        - index_version 是检索向量缓存（memmap .npy）的失效键
        - 不 commit：必须与 chunk 删/插同事务提交（见 crud/knowledge/chunk.py 头注）
        """
        from sqlalchemy import text as sa_text

        # CASE WHEN 而非 GREATEST：MySQL/sqlite（单测夹具）双方言可用
        await db.execute(
            sa_text(
                "UPDATE kb_project_knowledge_base "
                "SET index_version = index_version + 1, "
                "    total_chunks = CASE WHEN total_chunks + :dc < 0 THEN 0 ELSE total_chunks + :dc END, "
                "    total_documents = CASE WHEN total_documents + :dd < 0 THEN 0 ELSE total_documents + :dd END "
                "WHERE project_id = :pid"
            ),
            {"dc": delta_chunks, "dd": delta_documents, "pid": project_id},
        )

    # ── 兼容旧 ChromaDB Celery 任务的别名 ────────────────
    async def set_ready(
        self,
        db: AsyncSession,
        kb: ProjectKnowledgeBase,
        *,
        total_chunks: int = 0,
        total_nodes: int = 0,
        total_edges: int = 0,
    ) -> ProjectKnowledgeBase:
        kb.total_chunks = total_chunks
        kb.total_nodes = total_nodes
        kb.total_edges = total_edges
        return await self.update_status(
            db, kb=kb, status=KnowledgeBaseStatus.READY.value
        )

    async def set_failed(
        self,
        db: AsyncSession,
        kb: ProjectKnowledgeBase,
        error_message: str,
    ) -> ProjectKnowledgeBase:
        return await self.update_status(
            db,
            kb=kb,
            status=KnowledgeBaseStatus.ERROR.value,
            error_message=error_message,
        )


crud_knowledge_base = CRUDKnowledgeBase()
