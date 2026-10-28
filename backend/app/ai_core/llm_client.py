"""
LLM 客户端统一入口
所有模块需要调用 LLM 时，通过此模块获取客户端实例
"""
import re
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_openai import ChatOpenAI

_THINK_RE = re.compile(r"<think[^>]*>.*?</think\s*>", re.DOTALL)


def strip_think_tags(text: str) -> str:
    return _THINK_RE.sub("", text).strip()


class ThinkSafeChatOpenAI(ChatOpenAI):
    def _generate(
        self,
        messages: list,
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        result = super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
        for gen in result.generations:
            if isinstance(gen, ChatGeneration) and hasattr(gen.message, "content"):
                content = gen.message.content
                if isinstance(content, str) and "<think" in content:
                    gen.message.content = strip_think_tags(content)
        return result

    def _stream(
        self,
        messages: list,
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        for chunk in super()._stream(messages, stop=stop, run_manager=run_manager, **kwargs):
            content = chunk.message.content
            if isinstance(content, str) and "<think" in content:
                chunk.message.content = strip_think_tags(content)
            yield chunk

    async def _astream(
        self,
        messages: list,
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        async for chunk in super()._astream(
            messages, stop=stop, run_manager=run_manager, **kwargs
        ):
            content = chunk.message.content
            if isinstance(content, str) and "<think" in content:
                chunk.message.content = strip_think_tags(content)
            yield chunk

    def with_structured_output(self, schema=None, **kwargs: Any):
        kwargs.setdefault("method", "function_calling")
        return super().with_structured_output(schema, **kwargs)


def build_llm_from_config(config: Any) -> Any:
    """
    根据 UserLlmConfig 对象构建 LangChain LLM 实例。
    config 需有 provider、model、api_key、base_url 属性。
    """
    model_type = getattr(config, "model_type", "text")
    if model_type == "embed":
        return _build_embed(config)

    _timeout = httpx.Timeout(timeout=None, connect=15.0)
    provider = (config.provider or "").lower()
    base_url = config.base_url or None
    api_key = config.api_key

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=config.model,
            api_key=api_key,
            base_url=base_url,
            max_tokens=32768,
            timeout=_timeout,
        )
    else:
        return ThinkSafeChatOpenAI(
            model=config.model,
            api_key=api_key,
            base_url=base_url,
            max_tokens=32768,
        )


def _build_embed(config: Any) -> Any:
    from langchain_openai import OpenAIEmbeddings

    kwargs: dict = {
        "model": config.model,
        "api_key": config.api_key,
    }
    if config.base_url:
        kwargs["base_url"] = config.base_url
    return OpenAIEmbeddings(**kwargs)
