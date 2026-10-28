"""embedding 库级钉定单测（sqlite + 假客户端，WP2 probe 固化）

覆盖：pin 探针钉维与幂等 / 指纹 key 解析顺序 / 全失效置 invalid / 自愈 /
维度漂移断言 fail-fast / rebind 同指纹限定（换模型 409 拦截）。
Redis 相关（qvec 缓存）不在此测——缓存故障静默穿透由实现保证。
"""

import pytest

import app.services.knowledge.embed_binding as eb
from app.core.exceptions import BusinessException
from app.models.auth.user_llm_config import UserLlmConfig
from app.models.knowledge.knowledge_base import ProjectKnowledgeBase
from tests.knowledge.conftest import FakeEmbeddings

pytestmark = pytest.mark.unit

MODEL = "probe-embed-model"
URL = "https://probe.local/v1"


async def _mk_kb(db, project_id=101):
    kb = ProjectKnowledgeBase(project_id=project_id, status="empty")
    db.add(kb)
    await db.commit()
    await db.refresh(kb)
    return kb


async def _mk_cfg(db, *, user_id, active=True, model=MODEL, url=URL, name="c"):
    cfg = UserLlmConfig(
        user_id=user_id, model_type="embed", name=name, provider="openai",
        model=model, api_key="sk-x", base_url=url, is_active=active, is_default=False,
    )
    db.add(cfg)
    await db.commit()
    await db.refresh(cfg)
    return cfg


@pytest.fixture(autouse=True)
def fake_builder(monkeypatch):
    FakeEmbeddings.calls = 0
    monkeypatch.setattr(eb, "build_llm_from_config", lambda cfg: FakeEmbeddings(64))


class TestPin:
    async def test_pin_probes_dimension(self, db, monkeypatch):
        kb = await _mk_kb(db)
        cfg = await _mk_cfg(db, user_id=1)

        async def default_cfg(_db, *, user_id):
            return cfg

        monkeypatch.setattr(eb, "_get_default_embed_config", default_cfg)
        kb = await eb.pin_on_first_ingest(db, kb=kb, user_id=1)
        assert kb.embed_model == MODEL
        assert kb.embed_dim == 64  # 探针实测，非抄配置
        assert kb.embed_bound_by == 1
        assert kb.embed_status == "active"

    async def test_pin_idempotent(self, db, monkeypatch):
        kb = await _mk_kb(db)
        cfg = await _mk_cfg(db, user_id=1)

        async def default_cfg(_db, *, user_id):
            return cfg

        monkeypatch.setattr(eb, "_get_default_embed_config", default_cfg)
        await eb.pin_on_first_ingest(db, kb=kb, user_id=1)
        calls_after_pin = FakeEmbeddings.calls
        await eb.pin_on_first_ingest(db, kb=kb, user_id=2)  # 第二人不改钉定
        assert kb.embed_bound_by == 1
        assert FakeEmbeddings.calls == calls_after_pin  # 无第二次探针

    async def test_pin_without_config_raises_400(self, db):
        kb = await _mk_kb(db)
        with pytest.raises(BusinessException) as ei:
            await eb.pin_on_first_ingest(db, kb=kb, user_id=999)
        assert ei.value.code == 400
        assert "未配置" in ei.value.message


async def _pinned_kb(db, *, bound_by=1, dim=64):
    kb = await _mk_kb(db)
    kb.embed_provider = "openai"
    kb.embed_model = MODEL
    kb.embed_base_url = URL
    kb.embed_dim = dim
    kb.embed_bound_by = bound_by
    await db.commit()
    return kb


class TestResolve:
    async def test_second_user_uses_kb_fingerprint(self, db):
        kb = await _pinned_kb(db)
        await _mk_cfg(db, user_id=1)
        embedder = await eb.resolve_embedder(db, kb=kb, prefer_user_id=2)
        assert embedder.expected_dim == 64

    async def test_all_invalid_marks_and_raises(self, db):
        kb = await _pinned_kb(db)
        await _mk_cfg(db, user_id=1, active=False)
        with pytest.raises(BusinessException):
            await eb.resolve_embedder(db, kb=kb)
        await db.refresh(kb)
        assert kb.embed_status == "invalid"

    async def test_self_heal_with_any_user_same_fingerprint(self, db):
        kb = await _pinned_kb(db)
        kb.embed_status = "invalid"
        await db.commit()
        # 任何人补一条同指纹配置即可自愈（尾斜杠归一化）
        await _mk_cfg(db, user_id=7, url=URL + "/", name="other")
        await eb.resolve_embedder(db, kb=kb)
        await db.refresh(kb)
        assert kb.embed_status == "active"

    async def test_unpinned_kb_raises(self, db):
        kb = await _mk_kb(db)
        with pytest.raises(BusinessException):
            await eb.resolve_embedder(db, kb=kb)


class TestDimensionAssertion:
    async def test_dim_drift_fails_fast_and_invalidates(self, db, monkeypatch):
        kb = await _pinned_kb(db, dim=64)
        await _mk_cfg(db, user_id=1)
        monkeypatch.setattr(eb, "build_llm_from_config", lambda cfg: FakeEmbeddings(48))
        embedder = await eb.resolve_embedder(db, kb=kb)
        with pytest.raises(BusinessException) as ei:
            await embedder.embed_texts(["文本"])
        assert "48" in ei.value.message and "64" in ei.value.message
        await db.refresh(kb)
        assert kb.embed_status == "invalid"  # 停写保护索引


class TestRebind:
    async def test_rebind_different_model_409(self, db):
        kb = await _pinned_kb(db)
        other = await _mk_cfg(db, user_id=2, model="another-model", name="o")
        with pytest.raises(BusinessException) as ei:
            await eb.rebind(db, kb=kb, config_id=other.id, operator_id=1)
        assert ei.value.code == 409
        assert "全量重建" in ei.value.message

    async def test_rebind_same_fingerprint_ok(self, db):
        kb = await _pinned_kb(db, bound_by=1)
        kb.embed_status = "invalid"
        await db.commit()
        cfg2 = await _mk_cfg(db, user_id=2, name="key2")
        kb = await eb.rebind(db, kb=kb, config_id=cfg2.id, operator_id=1)
        assert kb.embed_bound_by == 2
        assert kb.embed_status == "active"


class TestVectorCodec:
    def test_pack_unpack_roundtrip(self):
        vec = [0.25, -1.5, 3.0]
        blob = eb.pack_vector(vec)
        assert len(blob) == 12  # float32 × 3
        out = eb.unpack_vector(blob)
        assert list(out) == vec
