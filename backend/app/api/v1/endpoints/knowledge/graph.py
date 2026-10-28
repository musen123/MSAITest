"""知识图谱 API（P1b WP-B4，自研替代 LightRAG graph 代理）

查询面 = knowledge:view，维护面 = knowledge:manage（权限口径 §4.3，不新增码）。
每端点：require_project_access + BusinessException→HTTPException 端点级映射
（平台无全局处理器，漏接会被 middleware 兜成 500——P0 教训铁律）。

路由顺序：/graph/labels/* /graph/entity/merge 等静态段在 /graph/entity/{id}
之前声明（FastAPI 顺序匹配纪律）。
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.exceptions import BusinessException
from app.core.response import ResponseModel, success_response
from app.models.auth.user import User
from app.models.knowledge.document import (
    KbDocument,
    KbDocumentStatus,
    KbDocValidity,
)
from app.models.knowledge.graph import KbGraphStatus
from app.schemas.knowledge.graph import (
    KbEntityCreateRequest,
    KbEntityDetailData,
    KbEntityMergeRequest,
    KbEntityPatchRequest,
    KbExtractBatchData,
    KbGraphLabelsData,
    KbGraphNode,
    KbGraphStatsData,
    KbRelationPatchRequest,
    KbSubgraphData,
)
from app.services.knowledge import graph_extract, graph_service
from app.utils.project_permission import require_project_access

router = APIRouter()

# 批量提取单次派发上限（防一次点击打爆队列；剩余量返回给前端提示再点）
EXTRACT_BATCH_CAP = 100


# ═════════════════════════════ 查询面（view） ═════════════════════════════


@router.get(
    "/graph",
    summary="子图查询（label 起点 BFS，预算截断 ≤500 节点/≤3 层）",
    response_model=ResponseModel[KbSubgraphData],
)
async def get_subgraph(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("knowledge:view"))],
    label: Optional[str] = Query(default=None, description="起点实体名；空或 * = 全量图谱（含孤立实体，预算截断）"),
    max_depth: int = Query(default=3, ge=1, le=3),
    max_nodes: int = Query(default=200, ge=1, le=500),
) -> ResponseModel[KbSubgraphData]:
    await require_project_access(db, project_id, current_user.id)
    data = await graph_service.get_subgraph(
        db, project_id=project_id, label=label, max_depth=max_depth, max_nodes=max_nodes
    )
    return success_response(data=KbSubgraphData(**data))


@router.get(
    "/graph/labels/popular",
    summary="热门实体标签（ref_count 降序）",
    response_model=ResponseModel[KbGraphLabelsData],
)
async def popular_labels(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("knowledge:view"))],
    limit: int = Query(default=100, ge=1, le=300),
) -> ResponseModel[KbGraphLabelsData]:
    await require_project_access(db, project_id, current_user.id)
    from app.crud.knowledge.graph import crud_kb_graph

    rows = await crud_kb_graph.list_popular_entities(
        db, project_id=project_id, limit=limit
    )
    return success_response(data=KbGraphLabelsData(labels=[e.name for e in rows]))


@router.get(
    "/graph/labels/search",
    summary="实体标签搜索",
    response_model=ResponseModel[KbGraphLabelsData],
)
async def search_labels(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("knowledge:view"))],
    q: str = Query(min_length=1, max_length=100),
    limit: int = Query(default=50, ge=1, le=200),
) -> ResponseModel[KbGraphLabelsData]:
    await require_project_access(db, project_id, current_user.id)
    from app.crud.knowledge.graph import crud_kb_graph

    rows = await crud_kb_graph.search_entities(
        db, project_id=project_id, keyword=q, limit=limit
    )
    return success_response(data=KbGraphLabelsData(labels=[e.name for e in rows]))


@router.get(
    "/graph/entities",
    summary="实体搜索（返回 id+name，合并目标选择器用）",
    response_model=ResponseModel[list[KbGraphNode]],
)
async def search_entities(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("knowledge:view"))],
    q: str = Query(min_length=1, max_length=100),
    limit: int = Query(default=20, ge=1, le=50),
) -> ResponseModel[list[KbGraphNode]]:
    await require_project_access(db, project_id, current_user.id)
    from app.crud.knowledge.graph import crud_kb_graph

    rows = await crud_kb_graph.search_entities(
        db, project_id=project_id, keyword=q, limit=limit
    )
    return success_response(
        data=[KbGraphNode.model_validate(e, from_attributes=True) for e in rows]
    )


@router.get(
    "/graph/stats",
    summary="图谱统计（点边数 + 各抽取状态文档数）",
    response_model=ResponseModel[KbGraphStatsData],
)
async def graph_stats(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("knowledge:view"))],
) -> ResponseModel[KbGraphStatsData]:
    await require_project_access(db, project_id, current_user.id)
    data = await graph_service.get_graph_stats(db, project_id=project_id)
    return success_response(data=KbGraphStatsData(**data))


# ═════════════════════════════ 维护面（manage） ═════════════════════════════
# 静态段 /graph/entity/merge 与 /graph/extract-batch 先于 /{entity_id} 声明


@router.post(
    "/graph/entity/merge",
    summary="合并实体（source 并入 target，留重定向指针）",
    response_model=ResponseModel[KbGraphNode],
)
async def merge_entities(
    project_id: int,
    payload: KbEntityMergeRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("knowledge:manage"))
    ],
) -> ResponseModel[KbGraphNode]:
    await require_project_access(db, project_id, current_user.id)
    try:
        winner = await graph_service.merge_entities(
            db,
            project_id=project_id,
            source_id=payload.source_id,
            target_id=payload.target_id,
        )
    except BusinessException as e:
        raise HTTPException(status_code=e.code, detail=e.message)
    return success_response(
        data=KbGraphNode.model_validate(winner, from_attributes=True),
        message="合并完成",
    )


@router.post(
    "/graph/extract-batch",
    summary="批量提取（未抽取/失败的就绪文档，单次上限 100）",
    response_model=ResponseModel[KbExtractBatchData],
)
async def extract_batch(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("knowledge:manage"))
    ],
) -> ResponseModel[KbExtractBatchData]:
    await require_project_access(db, project_id, current_user.id)
    stmt = (
        select(KbDocument)
        .where(
            KbDocument.project_id == project_id,
            KbDocument.status == KbDocumentStatus.READY.value,
            KbDocument.validity == KbDocValidity.EFFECTIVE.value,
            KbDocument.graph_status.in_(
                [KbGraphStatus.NONE.value, KbGraphStatus.FAILED.value]
            ),
            KbDocument.content_md.isnot(None),
        )
        .order_by(KbDocument.id)
    )
    docs = list((await db.execute(stmt)).scalars().all())
    task_ids: list[int] = []
    dispatched = 0
    for doc in docs[:EXTRACT_BATCH_CAP]:
        try:
            task_ids.append(
                await graph_extract.submit_extract(
                    db, project_id=project_id, user_id=current_user.id, doc=doc
                )
            )
            dispatched += 1
        except BusinessException:
            continue  # 单文档投递失败不阻塞其余（broker 抖动等）
    remaining = max(0, len(docs) - EXTRACT_BATCH_CAP)
    return success_response(
        data=KbExtractBatchData(
            dispatched=dispatched, remaining=remaining, task_ids=task_ids
        ),
        message=f"已派发 {dispatched} 个提取任务"
        + (f"，剩余 {remaining} 份可再次批量提取" if remaining else ""),
    )


@router.post(
    "/graph/entity",
    summary="手工创建实体（created_by 非空，永不 GC）",
    response_model=ResponseModel[KbGraphNode],
)
async def create_entity(
    project_id: int,
    payload: KbEntityCreateRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("knowledge:manage"))
    ],
) -> ResponseModel[KbGraphNode]:
    await require_project_access(db, project_id, current_user.id)
    try:
        row = await graph_service.create_entity(
            db,
            project_id=project_id,
            user_id=current_user.id,
            name=payload.name,
            entity_type=payload.entity_type,
            description=payload.description,
        )
    except BusinessException as e:
        raise HTTPException(status_code=e.code, detail=e.message)
    return success_response(
        data=KbGraphNode.model_validate(row, from_attributes=True), message="创建成功"
    )


@router.get(
    "/graph/entity/{entity_id}",
    summary="实体详情（mentions 溯源 + 邻接关系）",
    response_model=ResponseModel[KbEntityDetailData],
)
async def entity_detail(
    project_id: int,
    entity_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("knowledge:view"))],
) -> ResponseModel[KbEntityDetailData]:
    await require_project_access(db, project_id, current_user.id)
    try:
        data = await graph_service.get_entity_detail(
            db, project_id=project_id, entity_id=entity_id
        )
    except BusinessException as e:
        raise HTTPException(status_code=e.code, detail=e.message)
    return success_response(data=KbEntityDetailData(**data))


@router.patch(
    "/graph/entity/{entity_id}",
    summary="编辑实体（置 human_edited 保护位；改名留旧名重定向）",
    response_model=ResponseModel[KbGraphNode],
)
async def update_entity(
    project_id: int,
    entity_id: int,
    payload: KbEntityPatchRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("knowledge:manage"))
    ],
) -> ResponseModel[KbGraphNode]:
    await require_project_access(db, project_id, current_user.id)
    try:
        row = await graph_service.update_entity(
            db,
            project_id=project_id,
            entity_id=entity_id,
            name=payload.name,
            entity_type=payload.entity_type,
            description=payload.description,
        )
    except BusinessException as e:
        raise HTTPException(status_code=e.code, detail=e.message)
    return success_response(
        data=KbGraphNode.model_validate(row, from_attributes=True), message="已保存"
    )


@router.delete(
    "/graph/entity/{entity_id}",
    summary="删除实体（软删墓碑，防自动抽取复活；连带关系墓碑）",
    response_model=ResponseModel[None],
)
async def delete_entity(
    project_id: int,
    entity_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("knowledge:manage"))
    ],
) -> ResponseModel[None]:
    await require_project_access(db, project_id, current_user.id)
    try:
        await graph_service.delete_entity(
            db, project_id=project_id, entity_id=entity_id
        )
    except BusinessException as e:
        raise HTTPException(status_code=e.code, detail=e.message)
    return success_response(message="已删除")


@router.patch(
    "/graph/relation/{relation_id}",
    summary="编辑关系（置 human_edited）",
    response_model=ResponseModel[None],
)
async def update_relation(
    project_id: int,
    relation_id: int,
    payload: KbRelationPatchRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("knowledge:manage"))
    ],
) -> ResponseModel[None]:
    await require_project_access(db, project_id, current_user.id)
    try:
        await graph_service.update_relation(
            db,
            project_id=project_id,
            relation_id=relation_id,
            keywords=payload.keywords,
            description=payload.description,
        )
    except BusinessException as e:
        raise HTTPException(status_code=e.code, detail=e.message)
    return success_response(message="已保存")


@router.delete(
    "/graph/relation/{relation_id}",
    summary="删除关系（软删墓碑）",
    response_model=ResponseModel[None],
)
async def delete_relation(
    project_id: int,
    relation_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("knowledge:manage"))
    ],
) -> ResponseModel[None]:
    await require_project_access(db, project_id, current_user.id)
    try:
        await graph_service.delete_relation(
            db, project_id=project_id, relation_id=relation_id
        )
    except BusinessException as e:
        raise HTTPException(status_code=e.code, detail=e.message)
    return success_response(message="已删除")
