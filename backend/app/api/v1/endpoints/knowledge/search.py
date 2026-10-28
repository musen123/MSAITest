"""知识库检索/问答 API（自研，P0 /search + P1a /answer /feedback）

- POST /search   同步混合检索,chunk 引用列表;deep=true 启用改写+重排
  (需查询者 TEXT 模型;未配置静默退回快速模式——深度是增强不是门槛)
- POST /answer   SSE 流式:references 事件(引用+log_id) → delta token 流 → done
  合成用查询者 TEXT 模型(未配置 400 引导),引用编号纪律见 kb_prompts
- POST /search/feedback  采纳/赞踩回写(反馈闭环,质量迭代数据源)

检索永不 502:向量/全文任一路失败降级另一路并以 degraded 标志明示。
"""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.response import ResponseModel, success_response
from app.models.auth.user import User
from app.schemas.knowledge.search import (
    KbFeedbackRequest,
    KbSearchData,
    KbSearchRequest,
)
from app.services.knowledge import retrieval_service
from app.utils.project_permission import require_project_access

router = APIRouter()


async def _resolve_text_llm(db: AsyncSession, user_id: int):
    """查询者 TEXT 模型（deep 模式/answer 合成用）；未配置返回 None"""
    from app.ai_core.llm_client import build_llm_from_config
    from app.crud.auth.user_llm_config import crud_user_llm_config
    from app.models.auth.user_llm_config import ModelType

    config = await crud_user_llm_config.get_default(
        db, user_id=user_id, model_type=ModelType.TEXT
    )
    if config is None or not config.is_active:
        return None
    return build_llm_from_config(config)


@router.post(
    "/search",
    summary="知识库混合检索（向量+全文 RRF 融合，chunk 级引用溯源）",
    response_model=ResponseModel[KbSearchData],
)
async def search_kb(
    project_id: int,
    payload: KbSearchRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("knowledge:view"))],
) -> ResponseModel[KbSearchData]:
    await require_project_access(db, project_id, current_user.id)
    text_llm = await _resolve_text_llm(db, current_user.id) if payload.deep else None
    data = await retrieval_service.search(
        db,
        project_id=project_id,
        query=payload.query,
        top_k=payload.top_k,
        doc_types=payload.doc_types,
        prefer_user_id=current_user.id,
        consumer=payload.consumer,
        deep=payload.deep and text_llm is not None,
        text_llm=text_llm,
    )
    return success_response(data=data)


@router.post(
    "/answer",
    summary="知识库问答（SSE 流式：references → delta 流 → done）",
)
async def answer_kb(
    project_id: int,
    payload: KbSearchRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("knowledge:view"))],
) -> StreamingResponse:
    await require_project_access(db, project_id, current_user.id)

    text_llm = await _resolve_text_llm(db, current_user.id)
    if text_llm is None:
        raise HTTPException(
            status_code=400,
            detail="未配置 TEXT 文本模型，请先在「用户中心 → 大模型配置」添加",
        )

    data = await retrieval_service.search(
        db,
        project_id=project_id,
        query=payload.query,
        top_k=payload.top_k,
        doc_types=payload.doc_types,
        prefer_user_id=current_user.id,
        consumer="answer",
        deep=payload.deep,
        text_llm=text_llm,
    )

    def _sse(event: str, obj: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(obj, ensure_ascii=False)}\n\n"

    async def stream():
        # 先推引用（前端立即渲染来源卡片,再等答案流）
        yield _sse(
            "references",
            {
                "hits": [h.model_dump() for h in data.hits],
                "degraded": data.degraded.model_dump(),
                "log_id": data.log_id,
                "reranked": data.reranked,
            },
        )
        if not data.hits:
            yield _sse("done", {"log_id": data.log_id, "empty": True})
            return

        from app.ai_core.prompts.kb_prompts import build_kb_answer_messages

        context = retrieval_service.format_hits_for_llm(data.hits)
        try:
            # token 原样透传（<think> 块由前端既有逻辑解析展示,与 Chat 页一致）
            async for chunk in text_llm.astream(
                build_kb_answer_messages(payload.query, context)
            ):
                content = getattr(chunk, "content", None)
                if isinstance(content, str) and content:
                    yield _sse("delta", {"text": content})
                elif isinstance(content, list):
                    for c in content:
                        piece = c if isinstance(c, str) else (c or {}).get("text") or ""
                        if piece:
                            yield _sse("delta", {"text": piece})
            yield _sse("done", {"log_id": data.log_id})
        except Exception as exc:  # noqa: BLE001 —— 流中错误以事件形式告知,连接正常关闭
            yield _sse("error", {"message": f"答案生成失败：{exc}"})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post(
    "/search/feedback",
    summary="检索反馈回写（采纳 chunk / 赞踩）",
    response_model=ResponseModel[None],
)
async def search_feedback(
    project_id: int,
    payload: KbFeedbackRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.require_permission("knowledge:view"))],
) -> ResponseModel[None]:
    await require_project_access(db, project_id, current_user.id)
    from app.models.knowledge.retrieval_log import KbRetrievalLog

    row = await db.get(KbRetrievalLog, payload.log_id)
    if row is None or row.project_id != project_id:
        raise HTTPException(status_code=404, detail="检索日志不存在")

    if payload.adopted_chunk_ids:
        merged = set(row.adopted_chunk_ids or []) | set(payload.adopted_chunk_ids)
        row.adopted_chunk_ids = sorted(merged)
    if payload.feedback is not None:
        row.feedback = payload.feedback
    db.add(row)
    await db.commit()
    return success_response(message="反馈已记录")
