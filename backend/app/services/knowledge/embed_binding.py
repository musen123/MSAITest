"""知识库 embedding 库级钉定（设计文档《知识库自研-总体设计方案》§3#5 / §8 R5）

解决的矛盾：平台 EMBED 配置是**用户级**（UserLlmConfig，per-user），而知识库是
**项目级**——同一个库的所有向量必须出自同一模型/维度，否则索引静默损坏
（生产 LightRAG entrypoint.sh 已有「换模型须清库重建」的教训注释）。

裁定：**pin-on-first-ingest**——首次入库时把提交者的默认 EMBED 配置快照进
kb 表五字段（provider/model/base_url/dim/bound_by），此后入库与检索一律用库
钉定配置；api_key **不快照**、调用时实时解析（轮换 key 免重建，换 model/维度
才需要重建）。

key 解析顺序（R5）：当前操作用户的同指纹配置 → 钉定来源用户的配置 → 任意
用户的同指纹 active 配置 → 全部失效则库置 embed_status=invalid 并抛业务异常
（检索侧捕获后降级纯全文单路，永不 502）。

维度纪律：首绑探针实测钉死 embed_dim；此后**每批每条**向量断言维度，不符
fail-fast 并置 invalid——防静默写坏索引。
"""

import asyncio
import base64
import hashlib
from datetime import datetime
from typing import Any, Optional, Sequence

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_core.llm_client import build_llm_from_config
from app.ai_core.runtime.event_bus import get_redis
from app.core.exceptions import BusinessException
from app.models.auth.user_llm_config import ModelType, UserLlmConfig
from app.models.knowledge.knowledge_base import KbEmbedStatus, ProjectKnowledgeBase

# —— 锁定常量（任务拆解文档冻结） ——
KB_EMBED_BATCH_SIZE = 64  # 批量向量化条数/批
KB_EMBED_QUERY_TIMEOUT_S = 10  # 检索侧 query 向量化超时（超时→全文单路降级）
KB_EMBED_PROBE_TIMEOUT_S = 30  # 首绑维度探针超时（入库侧，宽松些）
KB_QVEC_CACHE_TTL_S = 600  # query 向量 Redis 缓存 TTL
_PROBE_TEXT = "知识库维度探针"


# ────────────────────────── 向量编解码（BLOB ↔ numpy） ──────────────────────────

def pack_vector(vec: Sequence[float]) -> bytes:
    """float32 little-endian packed（kb_chunk.embedding 的存储格式）"""
    return np.asarray(vec, dtype="<f4").tobytes()


def unpack_vector(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype="<f4")


def _norm_base_url(url: Optional[str]) -> str:
    return (url or "").strip().rstrip("/")


# ────────────────────────── 钉定 / 解析 ──────────────────────────

async def _get_default_embed_config(
    db: AsyncSession, *, user_id: int
) -> UserLlmConfig:
    """取用户默认 EMBED 配置；未配置 → 平台既有 400 语义"""
    from app.crud.auth.user_llm_config import crud_user_llm_config

    config = await crud_user_llm_config.get_default(
        db, user_id=user_id, model_type=ModelType.EMBED
    )
    if config is None or not config.is_active:
        raise BusinessException("未配置 EMBED 向量模型，请先在「用户中心 → 大模型配置」添加", code=400)
    return config


async def pin_on_first_ingest(
    db: AsyncSession, *, kb: ProjectKnowledgeBase, user_id: int
) -> ProjectKnowledgeBase:
    """首次入库钉定：快照提交者默认 EMBED 配置 + 探针实测维度。幂等：已钉定直接返回。

    调用点：上传/插文本端点在建 kb_document 之前（提交任务前失败要趁早，
    不浪费任务队列）；kb_ingest 图 prepare 节点兜底复查。
    """
    if kb.embed_model:
        return kb

    config = await _get_default_embed_config(db, user_id=user_id)
    client = build_llm_from_config(config)
    try:
        vec = await asyncio.wait_for(
            client.aembed_query(_PROBE_TEXT), timeout=KB_EMBED_PROBE_TIMEOUT_S
        )
    except BusinessException:
        raise
    except Exception as exc:  # noqa: BLE001 —— 探针失败=配置不可用，给可读错误
        raise BusinessException(f"EMBED 模型探针调用失败（{config.model}）：{exc}", code=400) from exc

    dim = len(vec)
    if dim <= 0:
        raise BusinessException(f"EMBED 模型返回空向量（{config.model}），无法钉定维度", code=400)

    kb.embed_provider = config.provider
    kb.embed_model = config.model
    kb.embed_base_url = _norm_base_url(config.base_url) or None
    kb.embed_dim = dim
    kb.embed_bound_by = user_id
    kb.embed_bound_at = datetime.now()
    kb.embed_status = KbEmbedStatus.ACTIVE.value
    db.add(kb)
    await db.commit()
    await db.refresh(kb)
    return kb


async def _find_key_config(
    db: AsyncSession, *, kb: ProjectKnowledgeBase, prefer_user_id: Optional[int] = None
) -> Optional[UserLlmConfig]:
    """按钉定指纹（provider+model+base_url）找一条可用配置供 api_key。

    排序：当前操作用户 → 钉定来源用户 → 任意（id 升序稳定）。
    """
    stmt = select(UserLlmConfig).where(
        UserLlmConfig.model_type == ModelType.EMBED,
        UserLlmConfig.is_active.is_(True),
        UserLlmConfig.provider == kb.embed_provider,
        UserLlmConfig.model == kb.embed_model,
    )
    rows = list((await db.execute(stmt)).scalars().all())
    pinned_url = _norm_base_url(kb.embed_base_url)
    rows = [c for c in rows if _norm_base_url(c.base_url) == pinned_url]
    if not rows:
        return None

    def rank(c: UserLlmConfig) -> tuple:
        return (
            0 if (prefer_user_id and c.user_id == prefer_user_id) else 1,
            0 if c.user_id == kb.embed_bound_by else 1,
            c.id,
        )

    return sorted(rows, key=rank)[0]


async def mark_invalid(
    db: AsyncSession, *, kb: ProjectKnowledgeBase, reason: str
) -> None:
    """库级 embed 失效态（可读原因落 error_message；检索侧据此降级纯全文）"""
    kb.embed_status = KbEmbedStatus.INVALID.value
    kb.error_message = reason
    db.add(kb)
    await db.commit()


async def resolve_embedder(
    db: AsyncSession, *, kb: ProjectKnowledgeBase, prefer_user_id: Optional[int] = None
) -> "KbEmbedder":
    """按库钉定配置构建向量化客户端（带维度断言的包装）。

    - 未钉定 → 400（先上传一份文档完成钉定）
    - 指纹配置全失效 → 置 invalid + 抛业务异常（含模型与来源用户，可读可操作）
    - 曾 invalid 但现在可解析 → 自愈回 active（用户重新启用了配置的场景）
    """
    if not kb.embed_model or not kb.embed_dim:
        raise BusinessException("知识库尚未钉定 EMBED 模型（首次上传文档时自动钉定）", code=400)

    config = await _find_key_config(db, kb=kb, prefer_user_id=prefer_user_id)
    if config is None:
        reason = (
            f"知识库已钉定模型 {kb.embed_model}（来源用户 {kb.embed_bound_by}），"
            "但平台内已无该指纹的可用 EMBED 配置——请重新启用原配置、"
            "由任意用户添加同 provider/model/base_url 的配置，或重绑后全量重建"
        )
        if kb.embed_status != KbEmbedStatus.INVALID.value:
            await mark_invalid(db, kb=kb, reason=reason)
        raise BusinessException(reason, code=400)

    if kb.embed_status == KbEmbedStatus.INVALID.value:
        kb.embed_status = KbEmbedStatus.ACTIVE.value
        db.add(kb)
        await db.commit()

    client = build_llm_from_config(config)
    return KbEmbedder(db=db, kb=kb, client=client)


async def rebind(
    db: AsyncSession, *, kb: ProjectKnowledgeBase, config_id: int, operator_id: int
) -> ProjectKnowledgeBase:
    """同指纹重绑（换 key 来源，不换模型）。换指纹必须走全量重建（P1a），此处 409。"""
    if not kb.embed_model:
        raise BusinessException("知识库尚未钉定 EMBED 模型，无需重绑", code=400)

    config = (
        await db.execute(select(UserLlmConfig).where(UserLlmConfig.id == config_id))
    ).scalar_one_or_none()
    if config is None or config.model_type != ModelType.EMBED or not config.is_active:
        raise BusinessException("目标配置不存在、非 EMBED 类型或未启用", code=400)

    same_fingerprint = (
        config.provider == kb.embed_provider
        and config.model == kb.embed_model
        and _norm_base_url(config.base_url) == _norm_base_url(kb.embed_base_url)
    )
    if not same_fingerprint:
        raise BusinessException(
            f"目标配置指纹不符（库钉定 {kb.embed_provider}/{kb.embed_model}）："
            "换模型必须走「全量重建」而非重绑，否则新旧向量不同空间、索引损坏",
            code=409,
        )

    kb.embed_bound_by = config.user_id
    kb.embed_bound_at = datetime.now()
    kb.embed_status = KbEmbedStatus.ACTIVE.value
    kb.error_message = None
    db.add(kb)
    await db.commit()
    await db.refresh(kb)
    return kb


# ────────────────────────── 维度断言包装（T2.2） ──────────────────────────

class KbEmbedder:
    """库钉定向量化客户端：每批每条向量断言维度，不符 fail-fast + 库置 invalid。

    不做重试——指数退避重试是 kb_ingest embed 节点的职责（批间还要 ctx.progress），
    本层只保证「出去的向量维度一定正确」。
    """

    def __init__(
        self, *, db: AsyncSession, kb: ProjectKnowledgeBase, client: Any
    ) -> None:
        self._db = db
        self._kb = kb
        self._client = client
        self.expected_dim: int = int(kb.embed_dim or 0)

    async def _assert_dims(self, vectors: Sequence[Sequence[float]]) -> None:
        for i, vec in enumerate(vectors):
            if len(vec) != self.expected_dim:
                reason = (
                    f"EMBED 返回维度 {len(vec)} ≠ 库钉定 {self.expected_dim}"
                    f"（模型 {self._kb.embed_model}，批内第 {i} 条）——"
                    "疑似同名模型被供应商改版，已停写保护索引，请全量重建"
                )
                await mark_invalid(self._db, kb=self._kb, reason=reason)
                raise BusinessException(reason, code=400)

    async def embed_texts(self, texts: Sequence[str]) -> list[bytes]:
        """单批向量化（调用方控制批大小 ≤ KB_EMBED_BATCH_SIZE），返回 packed BLOB 列表"""
        vectors = await self._client.aembed_documents(list(texts))
        await self._assert_dims(vectors)
        return [pack_vector(v) for v in vectors]

    async def embed_query(self, query: str, *, timeout_s: float = KB_EMBED_QUERY_TIMEOUT_S) -> np.ndarray:
        """query 向量化（检索侧，带超时；超时/失败由调用方降级全文单路）"""
        vec = await asyncio.wait_for(self._client.aembed_query(query), timeout=timeout_s)
        await self._assert_dims([vec])
        return np.asarray(vec, dtype="<f4")


# ────────────────────────── query 向量 Redis 缓存（T2.3） ──────────────────────────

def _qvec_cache_key(kb: ProjectKnowledgeBase, query: str) -> str:
    digest = hashlib.sha256(query.strip().encode("utf-8")).hexdigest()
    # 键含模型指纹：同库换模型重建后旧缓存天然失配不复用
    return f"kb:qvec:{kb.id}:{kb.embed_model}:{digest}"


async def embed_query_cached(
    db: AsyncSession,
    *,
    kb: ProjectKnowledgeBase,
    query: str,
    prefer_user_id: Optional[int] = None,
    timeout_s: float = KB_EMBED_QUERY_TIMEOUT_S,
) -> np.ndarray:
    """带 Redis 缓存的 query 向量化（TTL 600s，防高频重复查询重复计费）。

    平台 Redis 客户端 decode_responses=True，原始 bytes 无法回环——base64 文本存
    （2560 维 10KB → 13.6KB，TTL 内可忽略）。缓存层任何异常都静默穿透到直调。
    """
    key = _qvec_cache_key(kb, query)
    redis = get_redis()
    try:
        cached = await redis.get(key)
        if cached:
            vec = unpack_vector(base64.b64decode(cached))
            if len(vec) == int(kb.embed_dim or 0):
                return vec
    except Exception:  # noqa: BLE001 —— 缓存故障不阻断检索
        pass

    embedder = await resolve_embedder(db, kb=kb, prefer_user_id=prefer_user_id)
    vec = await embedder.embed_query(query, timeout_s=timeout_s)
    try:
        await redis.set(key, base64.b64encode(vec.tobytes()).decode("ascii"), ex=KB_QVEC_CACHE_TTL_S)
    except Exception:  # noqa: BLE001
        pass
    return vec
