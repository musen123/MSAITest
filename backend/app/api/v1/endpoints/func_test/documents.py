"""项目文档管理 API"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import deps
from app.core.exceptions import BusinessException
from app.core.response import ResponseModel, success_response
from app.crud.func_test.document import crud_document
from app.models.auth.user import User
from app.schemas.func_test.document import (
    DocumentListResponse,
    DocumentParseRequest,
    DocumentPreviewResponse,
    DocumentResponse,
    DocumentUpdate,
)
from app.services.func_test.document_parse_service import (
    _IMAGE_EXTS,
    parse_document_to_markdown,
)
from app.services.func_test.document_preview_service import build_preview
from app.services.func_test.document_to_kb_service import (
    ingest_document_to_kb,
    remove_document_from_kb,
)
from app.utils.document_storage import (
    delete_document_file,
    get_document_url,
    save_document_file,
)
from app.utils.project_permission import require_project_access

router = APIRouter()


def _to_response(doc) -> DocumentResponse:
    data = DocumentResponse.model_validate(doc)
    try:
        data.download_url = get_document_url(doc.file_path)
    except Exception:
        data.download_url = None
    # parsed_content 在列表中不返回（太大），仅详情/预览返回
    return data


# ═════════════════════════════════════════════════════════════
# 1. 集合级
# ═════════════════════════════════════════════════════════════


@router.post(
    "",
    summary="上传项目文档",
    response_model=ResponseModel[DocumentResponse],
)
async def upload_document(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("test_case:create"))
    ],
    file: UploadFile,
    name: str = Form(..., description="文档名称"),
    doc_type: str = Form(default="other"),
    description: Optional[str] = Form(default=None),
    version: Optional[str] = Form(default=None),
) -> ResponseModel[DocumentResponse]:
    await require_project_access(db, project_id, current_user.id)
    if doc_type not in ("requirement", "prototype", "db_dict", "other"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="doc_type 必须是 requirement/prototype/db_dict/other",
        )

    file_path, file_size, file_ext = await save_document_file(file, project_id)

    doc = await crud_document.create(
        db,
        project_id=project_id,
        name=name,
        doc_type=doc_type,
        file_name=file.filename or name,
        file_path=file_path,
        file_size=file_size,
        file_ext=file_ext,
        uploaded_by=current_user.id,
        description=description,
        version=version,
    )
    resp = _to_response(doc)
    resp.parsed_content = None  # 上传时不返回大字段
    return success_response(data=resp)


@router.get(
    "",
    summary="获取文档列表",
    response_model=ResponseModel[DocumentListResponse],
)
async def list_documents(
    project_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("test_case:view"))
    ],
    doc_type: Optional[str] = Query(default=None),
    keyword: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ResponseModel[DocumentListResponse]:
    await require_project_access(db, project_id, current_user.id)
    docs, total = await crud_document.get_by_project(
        db,
        project_id=project_id,
        doc_type=doc_type,
        keyword=keyword,
        skip=(page - 1) * page_size,
        limit=page_size,
    )

    items = []
    for d in docs:
        r = _to_response(d)
        r.parsed_content = None  # 列表不返回大字段
        items.append(r)
    return success_response(data=DocumentListResponse(total=total, items=items))


# ═════════════════════════════════════════════════════════════
# 2. 单文档（int 路径参数）
# ═════════════════════════════════════════════════════════════


@router.get(
    "/{doc_id}",
    summary="获取文档详情（包含 parsed_content）",
    response_model=ResponseModel[DocumentResponse],
)
async def get_document(
    project_id: int,
    doc_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("test_case:view"))
    ],
) -> ResponseModel[DocumentResponse]:
    await require_project_access(db, project_id, current_user.id)
    doc = await crud_document.get(db, doc_id)
    if not doc or doc.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="文档不存在")
    return success_response(data=_to_response(doc))


@router.put(
    "/{doc_id}",
    summary="更新文档",
    response_model=ResponseModel[DocumentResponse],
)
async def update_document(
    project_id: int,
    doc_id: int,
    body: DocumentUpdate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("test_case:edit"))
    ],
) -> ResponseModel[DocumentResponse]:
    await require_project_access(db, project_id, current_user.id)
    doc = await crud_document.get(db, doc_id)
    if not doc or doc.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="文档不存在")
    doc = await crud_document.update(
        db,
        doc=doc,
        name=body.name,
        doc_type=body.doc_type,
        description=body.description,
        version=body.version,
    )
    return success_response(data=_to_response(doc))


@router.delete(
    "/{doc_id}",
    summary="删除文档（若已入库则同步删除 LightRAG 中的副本）",
    response_model=ResponseModel,
)
async def delete_document(
    project_id: int,
    doc_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("test_case:delete"))
    ],
) -> ResponseModel:
    await require_project_access(db, project_id, current_user.id)
    doc = await crud_document.get(db, doc_id)
    if not doc or doc.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="文档不存在")
    # 同步移除知识库（若已入库）
    if doc.kb_document_id:
        try:
            await remove_document_from_kb(db, doc=doc)
        except Exception:
            pass
    delete_document_file(doc.file_path)
    await crud_document.soft_delete(db, doc=doc)
    return success_response(message="文档已删除")


# ═════════════════════════════════════════════════════════════
# 3. 文档操作：预览 / AI解析 / 入库 / 出库
#    /{doc_id}/xxx 形式，与 GET /{doc_id} 不冲突（HTTP 方法+路径区分）
# ═════════════════════════════════════════════════════════════


@router.get(
    "/{doc_id}/preview",
    summary="文档在线预览（PDF/图片返回 url；Word→html；MD/TXT→content）",
    response_model=ResponseModel[DocumentPreviewResponse],
)
async def preview_document(
    project_id: int,
    doc_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("test_case:view"))
    ],
) -> ResponseModel[DocumentPreviewResponse]:
    await require_project_access(db, project_id, current_user.id)
    doc = await crud_document.get(db, doc_id)
    if not doc or doc.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="文档不存在")
    data = build_preview(doc)
    return success_response(data=data)


@router.post(
    "/{doc_id}/parse",
    summary="AI 解析为知识库 Markdown（同步执行）",
    response_model=ResponseModel[DocumentResponse],
)
async def parse_document_for_kb(
    project_id: int,
    doc_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("test_case:edit"))
    ],
    _llm: Annotated[object, Depends(deps.get_user_llm)],
    body: DocumentParseRequest = DocumentParseRequest(),  # noqa: B008
) -> ResponseModel[DocumentResponse]:
    await require_project_access(db, project_id, current_user.id)
    doc = await crud_document.get(db, doc_id)
    if not doc or doc.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="文档不存在")

    # 图片类文档走视觉模型，按需注入（未配置时给出友好提示）
    ext = (doc.file_ext or "").lower()
    if not ext.startswith("."):
        ext = "." + ext
    if ext in _IMAGE_EXTS:
        await deps.get_user_vision_llm(current_user=current_user, db=db)

    try:
        await parse_document_to_markdown(
            db, doc=doc, custom_prompt=body.custom_prompt
        )
    except Exception as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail=f"AI 解析失败：{exc}"
        )
    # 重新拉一次保证最新
    doc = await crud_document.get(db, doc_id)
    return success_response(data=_to_response(doc))


@router.post(
    "/{doc_id}/to-knowledge",
    summary="导入到项目知识库（要求已 AI 解析）",
    response_model=ResponseModel[DocumentResponse],
)
async def ingest_to_knowledge(
    project_id: int,
    doc_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("test_case:edit"))
    ],
) -> ResponseModel[DocumentResponse]:
    await require_project_access(db, project_id, current_user.id)
    doc = await crud_document.get(db, doc_id)
    if not doc or doc.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="文档不存在")
    try:
        await ingest_document_to_kb(db, doc=doc, user_id=current_user.id)
    except BusinessException as exc:
        raise HTTPException(status_code=exc.code, detail=exc.message)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    doc = await crud_document.get(db, doc_id)
    return success_response(data=_to_response(doc))


@router.post(
    "/{doc_id}/remove-from-knowledge",
    summary="从项目知识库中移除（不删本地文档）",
    response_model=ResponseModel[DocumentResponse],
)
async def remove_from_knowledge(
    project_id: int,
    doc_id: int,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_user: Annotated[
        User, Depends(deps.require_permission("test_case:edit"))
    ],
) -> ResponseModel[DocumentResponse]:
    await require_project_access(db, project_id, current_user.id)
    doc = await crud_document.get(db, doc_id)
    if not doc or doc.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="文档不存在")
    await remove_document_from_kb(db, doc=doc)
    doc = await crud_document.get(db, doc_id)
    return success_response(data=_to_response(doc))
