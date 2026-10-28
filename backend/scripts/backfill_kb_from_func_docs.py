"""LightRAG → 自研知识库 历史数据回灌脚本（一次性，设计文档 §6.1 迁移第 2 步）

两类历史数据的处置（诚实口径）：
  ① func 文档类（kb_status='ingested'，parsed_content 完好在 MySQL LONGTEXT）
     → 逐个经桥接服务重新入库（**无损，零解析 token，只重 embed**）
  ② 知识库直传类（lightrag_doc_id 非空且 storage_key 为 NULL——原件从未落平台侧）
     → 标记 deleted + 错误信息引导重传（LightRAG 架构欠的债，无源可迁）

断点续传：func 文档按 kb_document_id 是否已回写判断，跑挂了重跑自动跳过已完成；
单项目串行提交（防用户级 embed key 被批量打限流）。
任务由 celery ai_tasks worker 消化——跑本脚本前确认 worker 在线。

用法（backend/ 下）：
    uv run python scripts/backfill_kb_from_func_docs.py [--dry-run] [--project <id>]
"""

import argparse
import asyncio
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.db.session import async_session_maker, engine  # noqa: E402
from app.models.func_test.document import (  # noqa: E402
    DocumentKbStatus,
    ProjectDocument,
)
from app.models.knowledge.document import KbDocument, KbDocumentStatus  # noqa: E402


async def backfill(dry_run: bool, only_project: int | None) -> None:
    async with async_session_maker() as db:
        # ① func 文档类：LightRAG 时代已入库的（kb_status=ingested 且尚未回写新库 id）
        stmt = select(ProjectDocument).where(
            ProjectDocument.kb_status == DocumentKbStatus.INGESTED.value,
            ProjectDocument.kb_document_id.is_(None),
            ProjectDocument.parsed_content.is_not(None),
        )
        if only_project:
            stmt = stmt.where(ProjectDocument.project_id == only_project)
        func_docs = list((await db.execute(stmt)).scalars().all())

        # ② 直传类历史行：无源文件不可重放
        stmt2 = select(KbDocument).where(
            KbDocument.lightrag_doc_id.is_not(None),
            KbDocument.storage_key.is_(None),
            KbDocument.source_type == "upload",
            KbDocument.status != KbDocumentStatus.DELETED.value,
        )
        if only_project:
            stmt2 = stmt2.where(KbDocument.project_id == only_project)
        orphan_uploads = list((await db.execute(stmt2)).scalars().all())

    by_project: dict[int, list[ProjectDocument]] = defaultdict(list)
    for d in func_docs:
        by_project[d.project_id].append(d)

    print(f"待回灌 func 文档：{len(func_docs)} 份（{len(by_project)} 个项目）")
    print(f"直传类历史行（标记重传）：{len(orphan_uploads)} 份")
    if dry_run:
        for pid, docs in sorted(by_project.items()):
            print(f"  project {pid}: {[d.id for d in docs]}")
        return

    # ② 先处置直传类：标 deleted + 引导文案
    if orphan_uploads:
        async with async_session_maker() as db:
            for od in orphan_uploads:
                row = await db.get(KbDocument, od.id)
                row.status = KbDocumentStatus.DELETED.value
                row.error_message = (
                    "LightRAG 时代文档（原件未落平台侧），已随知识库自研切换下线——请重新上传"
                )
                db.add(row)
            await db.commit()
        print(f"直传类历史行已标记：{len(orphan_uploads)}")

    # ① func 文档：单项目串行提交（每份提交一个 kb_ingest 任务）
    from app.services.func_test.document_to_kb_service import ingest_document_to_kb

    ok, failed = 0, 0
    for pid, docs in sorted(by_project.items()):
        print(f"—— project {pid}（{len(docs)} 份）——")
        for d in docs:
            try:
                async with async_session_maker() as db:
                    doc = await db.get(ProjectDocument, d.id)
                    if doc.kb_document_id:  # 断点续传：已回写则跳过
                        continue
                    # 回灌只入库不抽图谱（graph_status 留 none,切换日不集中烧 token）
                    result = await ingest_document_to_kb(
                        db, doc=doc, user_id=doc.uploaded_by or 1, auto_extract=False
                    )
                ok += 1
                print(f"  ✓ doc#{d.id} → kb_document#{result['kb_document_id']} task#{result['ai_task_id']}")
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"  ✗ doc#{d.id} 提交失败：{exc}")
    print(f"\n提交完成：成功 {ok} / 失败 {failed}（入库进度看任务中心，worker 需在线）")


async def _main(dry_run: bool, only_project: int | None) -> None:
    try:
        await backfill(dry_run, only_project)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--project", type=int, default=None)
    args = parser.parse_args()
    asyncio.run(_main(args.dry_run, args.project))
