"""RERANK 模型客户端（P2 WP-C3）

OpenAI/Cohere 兼容形制（SiliconFlow bge-reranker 同款）：
    POST {base_url}/rerank
    {"model": ..., "query": ..., "documents": [...], "top_n": N}
    → {"results": [{"index": 原下标, "relevance_score": ...}, ...]}

契约：成功返回**完整的原下标重排列表**（缺失下标按原序补尾——部分返回不丢候选）；
任何失败（网络/超时/非 2xx/结构不合法）返回 None，调用方回退 listwise LLM。
trust_env=False：本机代理会劫持 localhost（平台已知陷阱）,统一直连。
"""

import logging
from typing import Optional, Sequence

import httpx

logger = logging.getLogger(__name__)

RERANK_TIMEOUT_S = 5.0


async def api_rerank(
    config, *, query: str, documents: Sequence[str]
) -> Optional[list[int]]:
    """返回 documents 的重排下标序（完整置换）；失败返回 None。"""
    if not documents:
        return None
    base = (config.base_url or "").rstrip("/")
    if not base:
        return None
    url = f"{base}/rerank"
    payload = {
        "model": config.model,
        "query": query,
        "documents": list(documents),
        "top_n": len(documents),
    }
    headers = {"Authorization": f"Bearer {config.api_key}"}
    try:
        async with httpx.AsyncClient(
            timeout=RERANK_TIMEOUT_S, trust_env=False
        ) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001 —— 增强路失败静默回退
        logger.info("rerank API 调用失败(回退 listwise): %s", exc)
        return None

    results = data.get("results")
    if not isinstance(results, list):
        return None
    order: list[int] = []
    seen: set[int] = set()
    for item in results:
        idx = item.get("index") if isinstance(item, dict) else None
        if isinstance(idx, int) and 0 <= idx < len(documents) and idx not in seen:
            order.append(idx)
            seen.add(idx)
    if not order:
        return None
    # 缺失下标按原序补尾（部分返回不丢候选）
    for i in range(len(documents)):
        if i not in seen:
            order.append(i)
    return order
