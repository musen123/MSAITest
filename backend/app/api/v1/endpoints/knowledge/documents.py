"""项目知识库文档 API（自研版：上传→任务式入库，状态任务事件驱动）

路由声明顺序至关重要：FastAPI 按声明顺序匹配，所有静态/特殊路径必须
放在 ``/{kb_doc_id}`` 这种 int 路径参数之前，否则会被尝试解析为整数而 422。

自研后的变化（设计文档 §5 P0）：
  - 上传/插文本 = 原件落 storage → 建行 → 提交 kb_ingest 统一任务，
    返回 {document, ai_task_id}——进度走 AI 任务 SSE，不再有 track_status 轮询
  - 列表 = 本地 kb_document 单一数据源（终结双 id/双状态机），
    status_counts 为本地 GROUP BY
  - 删除/清空 = 取消在途任务 + 物理删 chunk + 计数回收
"""

from pathlib import Path
from typing import Annotated, Optional

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.exceptions import BusinessException
from app.core.response import ResponseModel, success_response
from app.crud.knowledge.document import crud_kb_document
from app.models.auth.user import User
from app.schemas.knowledge.document import (
    KbClearResponse,
    KbDocumentListResponse,
    KbDocumentPatchRequest,
    KbDocumentResponse,
    KbDocumentUploadResponse,
    KbInsertTextRequest,
)
from app.services.knowledge.knowledge_service import (
    clear_documents_from_kb,
    delete_document_from_kb,
    insert_text_to_kb,
    reingest_document,
    update_document_meta,
    upload_document_to_kb,
)
from app.utils.project_permission import require_project_access

router = APIRouter()


# ═════════════════════════════════════════════════════════════
# 1. 集合级操作（无路径参数）
# ═════════════════════════════════════════════════════════════


@router.get(
    "",
    summary="获取项目知识库文档列表（本地单一数据源）",
    response_model=ResponseModel[KbDocumentListResponse],
)
async def list_kb_documents(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("knowledge:view"))
    ],
    status_: Optional[str] = Query(default=None, alias="status"),
    doc_type: Optional[str] = Query(default=None),
    keyword: Optional[str] = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ResponseModel[KbDocumentListResponse]:
    await require_project_access(db, project_id, current_user.id)
    items, total = await crud_kb_document.list_by_project(
        db,
        project_id=project_id,
        status=status_,
        doc_type=doc_type,
        keyword=keyword,
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    counts = await crud_kb_document.status_counts(db, project_id=project_id)
    return success_response(
        data=KbDocumentListResponse(
            total=total,
            items=[KbDocumentResponse.model_validate(i) for i in items],
            status_counts=counts,
        )
    )


@router.post(
    "/upload",
    summary="上传文档入库（返回入库任务，进度走 AI 任务 SSE）",
    response_model=ResponseModel[KbDocumentUploadResponse],
)
async def upload_kb_document(
    project_id: int,
    file: UploadFile,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("knowledge:manage"))
    ],
    doc_type: Optional[str] = Form(default=None),
) -> ResponseModel[KbDocumentUploadResponse]:
    await require_project_access(db, project_id, current_user.id)

    file_name = file.filename or "unnamed"
    file_ext = Path(file_name).suffix.lower()
    content = await file.read()
    # 平台无全局 BusinessException 处理器（漏接会被 middleware 兜成 500），
    # 照 projects/crud.py 端点级映射惯例
    try:
        doc, task_id = await upload_document_to_kb(
            db,
            project_id=project_id,
            file_content=content,
            file_name=file_name,
            file_ext=file_ext,
            file_size=len(content),
            content_type=file.content_type or "application/octet-stream",
            uploaded_by=current_user.id,
            doc_type=doc_type,
        )
    except BusinessException as e:
        raise HTTPException(status_code=e.code, detail=e.message)
    return success_response(
        data=KbDocumentUploadResponse(
            document=KbDocumentResponse.model_validate(doc), ai_task_id=task_id
        ),
        message="已提交入库任务",
    )


@router.post(
    "/text",
    summary="插入文本入库（返回入库任务）",
    response_model=ResponseModel[KbDocumentUploadResponse],
)
async def insert_kb_text(
    project_id: int,
    body: KbInsertTextRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("knowledge:manage"))
    ],
) -> ResponseModel[KbDocumentUploadResponse]:
    await require_project_access(db, project_id, current_user.id)
    try:
        doc, task_id = await insert_text_to_kb(
            db,
            project_id=project_id,
            title=body.title,
            content=body.content,
            uploaded_by=current_user.id,
            doc_type=body.doc_type,
        )
    except BusinessException as e:
        raise HTTPException(status_code=e.code, detail=e.message)
    return success_response(
        data=KbDocumentUploadResponse(
            document=KbDocumentResponse.model_validate(doc), ai_task_id=task_id
        ),
        message="已提交入库任务",
    )


@router.delete(
    "",
    summary="清空本项目知识库文档（含分块与计数回收）",
    response_model=ResponseModel[KbClearResponse],
)
async def clear_kb_documents(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("knowledge:manage"))
    ],
) -> ResponseModel[KbClearResponse]:
    await require_project_access(db, project_id, current_user.id)
    result = await clear_documents_from_kb(db, project_id=project_id)
    return success_response(
        data=KbClearResponse(**result), message="知识库已清空"
    )


# ═════════════════════════════════════════════════════════════
# 2. 单文档操作（int 路径参数，声明在静态路径之后）
# ═════════════════════════════════════════════════════════════


@router.get(
    "/{kb_doc_id}",
    summary="获取文档详情（状态由入库任务事件驱动，无远端轮询）",
    response_model=ResponseModel[KbDocumentResponse],
)
async def get_kb_document(
    project_id: int,
    kb_doc_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("knowledge:view"))
    ],
) -> ResponseModel[KbDocumentResponse]:
    await require_project_access(db, project_id, current_user.id)
    doc = await crud_kb_document.get(db, kb_doc_id)
    if not doc or doc.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="文档不存在")
    return success_response(data=KbDocumentResponse.model_validate(doc))


@router.patch(
    "/{kb_doc_id}",
    summary="编辑文档元信息 / 显式废弃（deprecated 同事务删分块，检索即时不可见）",
    response_model=ResponseModel[KbDocumentResponse],
)
async def patch_kb_document(
    project_id: int,
    kb_doc_id: int,
    body: KbDocumentPatchRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("knowledge:manage"))
    ],
) -> ResponseModel[KbDocumentResponse]:
    await require_project_access(db, project_id, current_user.id)
    try:
        doc = await update_document_meta(
            db,
            project_id=project_id,
            kb_doc_id=kb_doc_id,
            file_name=body.file_name,
            doc_type=body.doc_type,
            validity=body.validity,
        )
    except BusinessException as e:
        raise HTTPException(status_code=e.code, detail=e.message)
    return success_response(data=KbDocumentResponse.model_validate(doc))


@router.post(
    "/{kb_doc_id}/reingest",
    summary="重新入库（废弃恢复 / 失败重试 / 分块策略升级后重建，任务式）",
    response_model=ResponseModel[KbDocumentUploadResponse],
)
async def reingest_kb_document(
    project_id: int,
    kb_doc_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("knowledge:manage"))
    ],
    scanned_pdf: bool = Query(
        default=False,
        description="扫描件解析：无文本层 PDF 逐页 VLM 转写（需 VISION 模型，成本高，逐次显式开启）",
    ),
) -> ResponseModel[KbDocumentUploadResponse]:
    await require_project_access(db, project_id, current_user.id)
    try:
        doc, task_id = await reingest_document(
            db,
            project_id=project_id,
            kb_doc_id=kb_doc_id,
            user_id=current_user.id,
            scanned_pdf=scanned_pdf,
        )
    except BusinessException as e:
        raise HTTPException(status_code=e.code, detail=e.message)
    return success_response(
        data=KbDocumentUploadResponse(
            document=KbDocumentResponse.model_validate(doc), ai_task_id=task_id
        ),
        message="已提交重新入库任务",
    )


@router.post(
    "/{kb_doc_id}/extract",
    summary="手动提取图谱（任务式；不受 graph_doc_types 白名单限制）",
    response_model=ResponseModel[dict],
)
async def extract_kb_document(
    project_id: int,
    kb_doc_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("knowledge:manage"))
    ],
) -> ResponseModel[dict]:
    await require_project_access(db, project_id, current_user.id)
    from app.models.knowledge.document import KbDocumentStatus as _S
    from app.services.knowledge import graph_extract

    doc = await crud_kb_document.get(db, kb_doc_id)
    if not doc or doc.project_id != project_id or doc.status == _S.DELETED.value:
        raise HTTPException(status_code=404, detail="文档不存在")
    if doc.status != _S.READY.value:
        raise HTTPException(
            status_code=400, detail="文档尚未入库完成，无法提取图谱"
        )
    if not (doc.content_md or "").strip():
        raise HTTPException(status_code=400, detail="文档无解析内容，无法提取")
    try:
        task_id = await graph_extract.submit_extract(
            db, project_id=project_id, user_id=current_user.id, doc=doc
        )
    except BusinessException as e:
        raise HTTPException(status_code=e.code, detail=e.message)
    return success_response(data={"ai_task_id": task_id}, message="已提交图谱提取任务")


@router.delete(
    "/{kb_doc_id}",
    summary="删除文档（取消在途任务 + 物理删分块 + 计数回收）",
    response_model=ResponseModel[None],
)
async def delete_kb_document(
    project_id: int,
    kb_doc_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("knowledge:manage"))
    ],
) -> ResponseModel[None]:
    await require_project_access(db, project_id, current_user.id)
    try:
        await delete_document_from_kb(db, project_id=project_id, kb_doc_id=kb_doc_id)
    except BusinessException as e:
        raise HTTPException(status_code=e.code, detail=e.message)
    return success_response(message="文档已删除")
