"""知识库分块 CRUD（自研检索核心资产的数据访问层）

设计文档《知识库自研-总体设计方案》§4.1 ③ / §6.1：

⚠ 事务约定（与仓库其他 CRUD 的刻意差异）：本文件所有**写**方法一律不 commit——
`kb_ingest` 的 index 节点要求「删旧 chunk + 插新 chunk + 更新 kb_document +
bump_index_version」必须在**同一事务**内原子完成（配合 SELECT ... FOR UPDATE
复核文档存活，堵删除竞态），事务边界归调用方（图节点 / 端点 service）所有。
读方法无状态，随用随查。

写路径唯一入口纪律：一切 kb_chunk 写操作之后必须调
`crud_knowledge_base.bump_index_version`（检索向量缓存的失效键 + 计数原子增量），
遗漏 = 检索读到旧索引 + 统计错账，code review 检查项。
"""

from typing import Optional, Sequence

from sqlalchemy import bindparam, delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge.chunk import KbChunk, KbChunkType
from app.models.knowledge.document import (
    KbDocument,
    KbDocumentStatus,
    KbDocValidity,
)


class CRUDKbChunk:
    """知识库分块 CRUD"""

    # ────────────────────────── 写（不 commit，事务归调用方） ──────────────────────────

    async def bulk_add(self, db: AsyncSession, *, chunks: Sequence[KbChunk]) -> None:
        """批量新增分块（flush 拿 id，供父子回链；不 commit）"""
        db.add_all(chunks)
        await db.flush()

    async def delete_by_document(self, db: AsyncSession, *, document_id: int) -> int:
        """删除某文档全部分块，返回删除行数（不 commit）"""
        result = await db.execute(
            delete(KbChunk).where(KbChunk.document_id == document_id)
        )
        return int(result.rowcount or 0)

    # ────────────────────────── 读 ──────────────────────────

    async def count_by_project(self, db: AsyncSession, *, project_id: int) -> int:
        """项目 chunk 总数（软/硬红线检查用，parent 也计入存储量）"""
        stmt = select(func.count(KbChunk.id)).where(KbChunk.project_id == project_id)
        return int((await db.execute(stmt)).scalar() or 0)

    async def get_by_ids(
        self, db: AsyncSession, *, project_id: int, chunk_ids: Sequence[int]
    ) -> list[KbChunk]:
        """按 id 批量取块。project_id 是硬过滤条件（归属校验铁律：
        跨项目 id 直接查不到，而非查到后再判）。"""
        if not chunk_ids:
            return []
        stmt = select(KbChunk).where(
            KbChunk.project_id == project_id,
            KbChunk.id.in_(chunk_ids),
        )
        return list((await db.execute(stmt)).scalars().all())

    async def get_by_ids_with_doc(
        self, db: AsyncSession, *, project_id: int, chunk_ids: Sequence[int]
    ) -> list[KbChunk]:
        """带所属文档预加载的批量取块（检索组装引用用；selectinload 防 MissingGreenlet）"""
        if not chunk_ids:
            return []
        from sqlalchemy.orm import selectinload

        stmt = (
            select(KbChunk)
            .options(selectinload(KbChunk.document))
            .where(
                KbChunk.project_id == project_id,
                KbChunk.id.in_(chunk_ids),
            )
        )
        return list((await db.execute(stmt)).scalars().all())

    async def fetch_recall_embeddings(
        self, db: AsyncSession, *, project_id: int
    ) -> list[tuple[int, bytes]]:
        """拉取项目全部可召回向量 (chunk_id, embedding BLOB)。

        向量缓存 miss 时的重建数据源（WP4 vector_cache 物化 .npy 用）。
        只取 child（parent 无 embedding），只取 ready 且 effective 文档的块——
        stale 向量不进热矩阵（评审吸收：已废弃文档不得占据召回候选）。
        """
        stmt = (
            select(KbChunk.id, KbChunk.embedding)
            .join(KbDocument, KbDocument.id == KbChunk.document_id)
            .where(
                KbChunk.project_id == project_id,
                KbChunk.chunk_type != KbChunkType.PARENT.value,
                KbChunk.embedding.is_not(None),
                KbDocument.status == KbDocumentStatus.READY.value,
                KbDocument.validity == KbDocValidity.EFFECTIVE.value,
            )
            .order_by(KbChunk.id)
        )
        rows = (await db.execute(stmt)).all()
        return [(int(r[0]), bytes(r[1])) for r in rows]

    async def fulltext_search(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        query: str,
        limit: int = 30,
        doc_types: Optional[Sequence[str]] = None,
    ) -> list[tuple[int, float]]:
        """全文召回：返回 [(chunk_id, score)]，按相关度降序。

        铁律（spike 实证 8.0.46/9.6 双版本）：必须 NATURAL LANGUAGE MODE——
        BOOLEAN MODE 把中文整句转 ngram 短语搜索，几乎必然零命中。
        parent 行硬排除（child 的超集，双重命中会挤占 RRF 名额）；
        <2 字符查询由调用方走 LIKE 兜底（ngram_token_size=2 单字不命中）。
        """
        if not query or len(query.strip()) < 2:
            return []
        sql = """
            SELECT c.id,
                   MATCH(c.heading_path, c.content) AGAINST(:q IN NATURAL LANGUAGE MODE) AS score
            FROM kb_chunk c
            JOIN kb_document d ON d.id = c.document_id
            WHERE c.project_id = :pid
              AND c.chunk_type != :parent_type
              AND d.status = :ready
              AND d.validity = :effective
              AND MATCH(c.heading_path, c.content) AGAINST(:q IN NATURAL LANGUAGE MODE) > 0
              {doc_type_filter}
            ORDER BY score DESC
            LIMIT :lim
        """
        params: dict = {
            "q": query.strip(),
            "pid": project_id,
            "parent_type": KbChunkType.PARENT.value,
            "ready": KbDocumentStatus.READY.value,
            "effective": KbDocValidity.EFFECTIVE.value,
            "lim": int(limit),
        }
        if doc_types:
            sql = sql.format(doc_type_filter="AND d.doc_type IN :doc_types")
            params["doc_types"] = list(doc_types)
            stmt = text(sql).bindparams(bindparam("doc_types", expanding=True))
        else:
            sql = sql.format(doc_type_filter="")
            stmt = text(sql)
        rows = (await db.execute(stmt, params)).all()
        return [(int(r[0]), float(r[1])) for r in rows]

    async def like_search(
        self,
        db: AsyncSession,
        *,
        project_id: int,
        query: str,
        limit: int = 30,
    ) -> list[tuple[int, float]]:
        """<2 字符查询的 LIKE 兜底（ngram 单字不命中；分值统一置 1.0 交给 RRF 排名）"""
        q = (query or "").strip()
        if not q:
            return []
        stmt = (
            select(KbChunk.id)
            .join(KbDocument, KbDocument.id == KbChunk.document_id)
            .where(
                KbChunk.project_id == project_id,
                KbChunk.chunk_type != KbChunkType.PARENT.value,
                KbDocument.status == KbDocumentStatus.READY.value,
                KbDocument.validity == KbDocValidity.EFFECTIVE.value,
                KbChunk.content.like(f"%{q}%"),
            )
            .limit(limit)
        )
        rows = (await db.execute(stmt)).all()
        return [(int(r[0]), 1.0) for r in rows]


crud_kb_chunk = CRUDKbChunk()
