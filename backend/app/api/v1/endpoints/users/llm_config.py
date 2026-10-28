"""用户大模型配置接口"""

import time
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user, get_db
from app.core.response import ResponseModel
from app.crud.auth.user_llm_config import crud_user_llm_config
from app.models.auth.user import User
from app.models.auth.user_llm_config import ModelType
from app.schemas.auth.user_llm_config import (
    UserLlmConfigCreate,
    UserLlmConfigResponse,
    UserLlmConfigUpdate,
)

router = APIRouter()

VALID_TYPES = {ModelType.TEXT, ModelType.EMBED, ModelType.VISION}


class TestConnectionRequest(BaseModel):
    provider: str = Field(..., description="模型提供商")
    model: str = Field(..., description="模型名称")
    api_key: str = Field(..., description="API Key")
    base_url: Optional[str] = Field(None, description="自定义 Base URL")
    model_type: str = Field(default="text", description="模型类型: text/embed/vision")


def _mask(config: UserLlmConfigResponse) -> UserLlmConfigResponse:
    config.api_key = UserLlmConfigResponse.mask_api_key(config.api_key)
    return config


@router.get(
    "/me/llm-configs",
    response_model=ResponseModel[List[UserLlmConfigResponse]],
    summary="获取当前用户的大模型配置（可按类型过滤）",
)
async def list_llm_configs(
    model_type: Optional[str] = Query(default=None, description="按类型过滤: text/embed/vision，不传则返回全部"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if model_type is not None and model_type not in VALID_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"model_type 只支持: {', '.join(VALID_TYPES)}",
        )
    if model_type is None:
        configs = await crud_user_llm_config.get_all_by_user(db, user_id=current_user.id)
    else:
        configs = await crud_user_llm_config.list_by_user_and_type(
            db, user_id=current_user.id, model_type=model_type
        )
    return ResponseModel(
        data=[_mask(UserLlmConfigResponse.model_validate(c)) for c in configs]
    )


@router.get(
    "/me/llm-config/{config_id}/full",
    response_model=ResponseModel[UserLlmConfigResponse],
    summary="获取单条配置（含完整 API Key，仅用于编辑回填）",
)
async def get_llm_config_full(
    config_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    config = await crud_user_llm_config.get_by_id(
        db, config_id=config_id, user_id=current_user.id
    )
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="配置不存在")
    return ResponseModel(data=UserLlmConfigResponse.model_validate(config))


@router.post(
    "/me/llm-config",
    response_model=ResponseModel[UserLlmConfigResponse],
    summary="新建一条大模型配置",
)
async def create_llm_config(
    body: UserLlmConfigCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if body.model_type not in VALID_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"model_type 只支持: {', '.join(VALID_TYPES)}",
        )
    config = await crud_user_llm_config.create(
        db,
        user_id=current_user.id,
        model_type=body.model_type,
        name=body.name,
        provider=body.provider,
        model=body.model,
        api_key=body.api_key,
        base_url=body.base_url,
        model_family=body.model_family,
        make_default=body.make_default,
    )
    return ResponseModel(
        data=_mask(UserLlmConfigResponse.model_validate(config)),
        message="配置已创建",
    )


@router.put(
    "/me/llm-config/{config_id}",
    response_model=ResponseModel[UserLlmConfigResponse],
    summary="修改一条大模型配置",
)
async def update_llm_config(
    config_id: int,
    body: UserLlmConfigUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    fields = body.model_fields_set
    config = await crud_user_llm_config.update(
        db,
        config_id=config_id,
        user_id=current_user.id,
        provider=body.provider,
        model=body.model,
        api_key=body.api_key,
        base_url=body.base_url,
        model_family=body.model_family,
        name=body.name,
        update_base_url="base_url" in fields,
        update_model_family="model_family" in fields,
        update_name="name" in fields,
    )
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="配置不存在")
    return ResponseModel(
        data=_mask(UserLlmConfigResponse.model_validate(config)),
        message="配置已更新",
    )


@router.post(
    "/me/llm-config/{config_id}/set-default",
    response_model=ResponseModel[UserLlmConfigResponse],
    summary="将某配置设为其类型的默认（运行时使用）",
)
async def set_default_llm_config(
    config_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    config = await crud_user_llm_config.set_default(
        db, config_id=config_id, user_id=current_user.id
    )
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="配置不存在")
    return ResponseModel(
        data=_mask(UserLlmConfigResponse.model_validate(config)),
        message="已设为默认",
    )


@router.delete(
    "/me/llm-config/{config_id}",
    response_model=ResponseModel[None],
    summary="删除一条大模型配置（删默认会自动顺位提升）",
)
async def delete_llm_config(
    config_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    deleted = await crud_user_llm_config.delete_by_id(
        db, config_id=config_id, user_id=current_user.id
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="配置不存在")
    return ResponseModel(data=None, message="大模型配置已删除")


@router.post(
    "/me/llm-config/test-connection",
    response_model=ResponseModel[dict],
    summary="验证大模型配置是否能正常连接",
)
async def test_llm_connection(
    body: TestConnectionRequest,
    current_user: User = Depends(get_current_active_user),
):
    start = time.time()
    try:
        if body.model_type == "embed":
            return await _test_embed_connection(body, start)
        return await _test_chat_connection(body, start)
    except httpx.ConnectError as e:
        return ResponseModel(
            data={"success": False, "message": f"连接失败：无法访问 {_clean_url(body.base_url) or '默认地址'}（{e}），请检查网络或 Base URL", "latency_ms": int((time.time() - start) * 1000)},
            message="连接失败",
        )
    except httpx.TimeoutException:
        return ResponseModel(
            data={"success": False, "message": f"连接超时，请检查网络或 Base URL {_clean_url(body.base_url) or ''} 是否正确", "latency_ms": int((time.time() - start) * 1000)},
            message="连接超时",
        )
    except httpx.HTTPStatusError as e:
        detail = ""
        if e.response.status_code == 401:
            detail = "认证失败，请检查 API Key 是否正确"
        elif e.response.status_code == 403:
            detail = "无权限访问，请检查 API Key 权限"
        elif e.response.status_code == 404:
            detail = f"模型 '{body.model}' 不存在或未开通，请检查模型名称"
        else:
            try:
                err_body = e.response.json()
                detail = err_body.get("error", {}).get("message", str(e))
            except Exception:
                detail = str(e)
        return ResponseModel(
            data={"success": False, "message": detail, "latency_ms": int((time.time() - start) * 1000)},
            message="验证失败",
        )
    except Exception as e:
        err_msg = str(e)
        if "connection" in err_msg.lower() or "connect" in err_msg.lower():
            err_msg = f"连接失败：{err_msg}"
        return ResponseModel(
            data={"success": False, "message": err_msg, "latency_ms": int((time.time() - start) * 1000)},
            message="验证失败",
        )


def _clean_url(url: str | None) -> str | None:
    if not url:
        return url
    url = url.strip()
    url = url.strip("`'\"")
    url = url.strip()
    return url


async def _test_chat_connection(body: TestConnectionRequest, start: float) -> ResponseModel:
    base_url = _clean_url(body.base_url)
    _timeout = httpx.Timeout(timeout=30.0, connect=10.0)

    if body.provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        llm = ChatAnthropic(
            model=body.model,
            api_key=body.api_key,
            base_url=base_url or None,
        )
    else:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=body.model,
            api_key=body.api_key,
            base_url=base_url or None,
        )

    response = await llm.ainvoke("Hi")

    latency = int((time.time() - start) * 1000)
    return ResponseModel(
        data={"success": True, "message": "连接成功，模型响应正常", "latency_ms": latency},
        message="连接成功",
    )


async def _test_embed_connection(body: TestConnectionRequest, start: float) -> ResponseModel:
    from langchain_openai import OpenAIEmbeddings

    base_url = _clean_url(body.base_url)
    kwargs: dict = {
        "model": body.model,
        "api_key": body.api_key,
        "http_client": httpx.Client(proxy=None),
        "http_async_client": httpx.AsyncClient(proxy=None),
    }
    if base_url:
        kwargs["base_url"] = base_url

    embed = OpenAIEmbeddings(**kwargs)
    await embed.aembed_query("test")

    latency = int((time.time() - start) * 1000)
    return ResponseModel(
        data={"success": True, "message": "连接成功，嵌入模型响应正常", "latency_ms": latency},
        message="连接成功",
    )
