"""项目知识库元信息 API

自研版全部走本地数据库（LightRAG 代理已随 P1b 下线）。
P2 增补 /settings：图谱自动抽取白名单 + 图增强检索开关（默认关，放量过评测 gate）。
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.response import ResponseModel, success_response
from app.models.auth.user import User
from app.schemas.knowledge.knowledge_base import KnowledgeBaseResponse
from app.services.knowledge.knowledge_service import (
    KB_DOC_TYPES,
    ensure_knowledge_base,
    sync_kb_stats,
)
from app.utils.project_permission import require_project_access

router = APIRouter()


class KbSettingsPatchRequest(BaseModel):
    """库级设置（P2 WP-C2）"""

    graph_doc_types: Optional[str] = Field(
        default=None, max_length=200, description="图谱自动抽取 doc_type 白名单（逗号分隔）"
    )
    graph_channel: Optional[bool] = Field(
        default=None,
        description="图增强检索第三路开关（默认关；放量前须过 ≥20 条评测 gate）",
    )


@router.get(
    "",
    summary="获取项目知识库信息",
    response_model=ResponseModel[KnowledgeBaseResponse],
)
async def get_kb(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("knowledge:view"))
    ],
) -> ResponseModel[KnowledgeBaseResponse]:
    await require_project_access(db, project_id, current_user.id)
    kb = await ensure_knowledge_base(db, project_id=project_id)
    return success_response(data=KnowledgeBaseResponse.model_validate(kb))


@router.patch(
    "/settings",
    summary="更新库级设置（图谱白名单 / 图增强检索开关）",
    response_model=ResponseModel[KnowledgeBaseResponse],
)
async def patch_kb_settings(
    project_id: int,
    payload: KbSettingsPatchRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("knowledge:manage"))
    ],
) -> ResponseModel[KnowledgeBaseResponse]:
    await require_project_access(db, project_id, current_user.id)
    kb = await ensure_knowledge_base(db, project_id=project_id)

    if payload.graph_doc_types is not None:
        types = [t.strip() for t in payload.graph_doc_types.split(",") if t.strip()]
        bad = [t for t in types if t not in KB_DOC_TYPES]
        if bad:
            raise HTTPException(status_code=400, detail=f"非法文档类型：{','.join(bad)}")
        kb.graph_doc_types = ",".join(types)

    if payload.graph_channel is not None:
        # JSON 列须整体替换才触发脏标记（SQLAlchemy 不追踪 dict 原地修改）
        settings = dict(kb.settings or {})
        settings["graph_channel"] = bool(payload.graph_channel)
        kb.settings = settings

    db.add(kb)
    await db.commit()
    await db.refresh(kb)
    return success_response(
        data=KnowledgeBaseResponse.model_validate(kb), message="已保存"
    )


@router.post(
    "/sync",
    summary="重算知识库统计（本地真实口径校准，替代旧 LightRAG 全局求和）",
    response_model=ResponseModel[KnowledgeBaseResponse],
)
async def sync_kb(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("knowledge:manage"))
    ],
) -> ResponseModel[KnowledgeBaseResponse]:
    await require_project_access(db, project_id, current_user.id)
    kb = await sync_kb_stats(db, project_id=project_id)
    return success_response(data=KnowledgeBaseResponse.model_validate(kb))
