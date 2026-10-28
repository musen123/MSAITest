"""AI 需求盘点纯逻辑回归（发现/三级合并/原型挂靠/证据包封顶，零 DB 零 LLM）。

守护设计 v2 的关键不变量：
  - K1 同编号跨文档聚合为一个候选（主段+补充块），不重复建需求；
  - 仅正文提及的编号不造候选（防功能清单表格刷薄需求），进报告统计；
  - K2 无编号 requirement 文档章节按标题归一并入同名候选；
  - K3 图谱实体桥只从**其它文档**拉补充块；
  - 原型图绝不独立成候选：实体桥/关键词挂靠，挂不上进未归位清单；
  - 证据包块数/字符封顶且优先级=主段>K1>原型>图谱桥。
"""

from app.ai_core.graphs.func_test.extract_requirements import (
    MAX_BLOCKS_PER_PACK,
    MAX_PACK_CHARS,
    assemble_evidence,
    attach_prototypes,
    bridge_graph_entities,
    discover_candidates,
    normalize_title,
)


def _chunk(cid, doc, heading, content, *, doc_name=None, doc_type="requirement", parent=True):
    return {
        "id": cid,
        "document_id": doc,
        "heading_path": heading,
        "content": content,
        "doc_name": doc_name or f"文档{doc}",
        "doc_type": doc_type,
        "is_parent": parent,
    }


class TestNormalizeTitle:
    def test_strips_code_and_punct(self) -> None:
        assert normalize_title("REQ-USER-001 用户注册") == "用户注册"
        assert normalize_title("3.1.4 用户 登录（★重点）") == "用户登录★重点"
        assert normalize_title("用户注册") == normalize_title(" 用户注册。")


class TestDiscover:
    def test_k1_cross_doc_merge(self) -> None:
        chunks = [
            _chunk(1, 10, "3.5 REQ-ORD-002 创建订单", "入参校验……", doc_name="SRS"),
            _chunk(2, 20, "2.3 订单接口", "创建订单接口 REQ-ORD-002 的响应……", doc_name="接口文档"),
        ]
        cands, stats = discover_candidates(chunks)
        assert len(cands) == 1
        cand = cands["REQ-ORD-002"]
        assert len(cand["primary"]) == 1 and cand["primary"][0]["doc"] == "SRS"
        assert len(cand["supplements"]) == 1
        assert cand["supplements"][0]["doc"] == "接口文档"

    def test_mention_only_codes_do_not_create_candidates(self) -> None:
        chunks = [
            _chunk(1, 10, "3.5.2 功能清单", "| REQ-ORD-003 | 订单列表 |……"),
        ]
        cands, stats = discover_candidates(chunks)
        assert cands == {}
        assert stats["mention_only_codes"] == ["REQ-ORD-003"]

    def test_k2_uncoded_doc_merges_by_title(self) -> None:
        chunks = [
            _chunk(1, 10, "3.1 REQ-USER-001 用户注册", "字段校验……", doc_name="SRS"),
            # 另一份无编号需求文档的同名章节 → 并入而非新建
            _chunk(2, 30, "二、用户注册", "补充说明：需支持手机号……", doc_name="补充需求"),
        ]
        cands, _ = discover_candidates(chunks)
        assert len(cands) == 1
        assert len(cands["REQ-USER-001"]["supplements"]) == 1

    def test_uncoded_requirement_doc_creates_candidate(self) -> None:
        chunks = [
            _chunk(1, 30, "三、积分兑换", "用户可用积分兑换优惠券……"),
        ]
        cands, _ = discover_candidates(chunks)
        assert len(cands) == 1
        cand = next(iter(cands.values()))
        assert cand["code"] is None and "积分兑换" in cand["title"]

    def test_uncoded_non_requirement_doc_ignored(self) -> None:
        chunks = [
            _chunk(1, 30, "会议纪要", "讨论了积分兑换……", doc_type="meeting"),
        ]
        cands, _ = discover_candidates(chunks)
        assert cands == {}

    def test_primary_prefers_parent_chunks_only(self) -> None:
        """父子块同 heading 锚定时只收父块——防主段膨胀挤出原型/图谱桥。"""
        chunks = [
            _chunk(1, 10, "3.1 REQ-USER-001 用户注册", "整节内容", parent=True),
            _chunk(2, 10, "3.1 REQ-USER-001 用户注册", "切片1", parent=False),
            _chunk(3, 10, "3.1 REQ-USER-001 用户注册", "切片2", parent=False),
        ]
        cands, _ = discover_candidates(chunks)
        primary = cands["REQ-USER-001"]["primary"]
        assert len(primary) == 1 and primary[0]["chunk_id"] == 1

    def test_child_fallback_when_no_parent_anchor(self) -> None:
        chunks = [
            _chunk(1, 10, "3.1 REQ-USER-001 用户注册", "只有子块", parent=False),
        ]
        cands, _ = discover_candidates(chunks)
        assert len(cands["REQ-USER-001"]["primary"]) == 1


class TestGraphBridge:
    def test_bridge_pulls_other_doc_blocks_only(self) -> None:
        chunks = [
            _chunk(1, 10, "3.1 REQ-USER-001 用户注册", "……", doc_name="SRS"),
            _chunk(2, 20, "接口A", "注册接口详情……", doc_name="接口文档"),
            _chunk(3, 10, "同文档另一节", "……", doc_name="SRS"),
        ]
        cands, _ = discover_candidates(chunks)
        chunk_map = {c["id"]: c for c in chunks}
        entities = [{"id": 7, "name": "用户注册"}]
        mentions = [
            {"entity_id": 7, "chunk_id": 2, "document_id": 20},  # 其它文档 → 拉
            {"entity_id": 7, "chunk_id": 3, "document_id": 10},  # 同文档 → 不拉
        ]
        added = bridge_graph_entities(cands, entities, mentions, chunk_map)
        assert added == 1
        sup = cands["REQ-USER-001"]["supplements"]
        assert len(sup) == 1 and sup[0]["kind"] == "graph" and sup[0]["doc"] == "接口文档"


class TestPrototypes:
    def _cands(self):
        chunks = [_chunk(1, 10, "3.1 REQ-USER-001 用户注册", "……", doc_name="SRS")]
        cands, _ = discover_candidates(chunks)
        return cands

    def test_attach_by_entity_bridge(self) -> None:
        cands = self._cands()
        entities = [{"id": 7, "name": "用户注册"}]
        mentions = [{"entity_id": 7, "chunk_id": 0, "document_id": 99}]
        imgs = [{"id": 99, "file_name": "proto.png", "content_md": "登录界面……"}]
        attached, unplaced = attach_prototypes(cands, imgs, entities, mentions)
        assert attached == 1 and unplaced == []
        assert cands["REQ-USER-001"]["prototypes"][0]["kind"] == "prototype"

    def test_attach_by_filename_keyword(self) -> None:
        cands = self._cands()
        imgs = [{"id": 99, "file_name": "用户注册-原型.png", "content_md": "表单……"}]
        attached, unplaced = attach_prototypes(cands, imgs, [], [])
        assert attached == 1 and unplaced == []

    def test_attach_by_description_code(self) -> None:
        cands = self._cands()
        imgs = [{"id": 99, "file_name": "IMG_0001.png", "content_md": "对应 REQ-USER-001 的注册页"}]
        attached, unplaced = attach_prototypes(cands, imgs, [], [])
        assert attached == 1

    def test_unplaced_goes_to_report(self) -> None:
        cands = self._cands()
        imgs = [{"id": 99, "file_name": "IMG_0001.png", "content_md": "一张风景照"}]
        attached, unplaced = attach_prototypes(cands, imgs, [], [])
        assert attached == 0
        assert unplaced == [{"document_id": 99, "file_name": "IMG_0001.png"}]


class TestEvidencePack:
    def test_priority_and_block_cap(self) -> None:
        cand = {
            "key": "k",
            "code": "REQ-X-1",
            "title": "t",
            "primary": [
                {"chunk_id": 1, "document_id": 1, "doc": "SRS", "heading": "h1", "content": "主段", "kind": "primary"}
            ],
            "supplements": (
                [{"chunk_id": 10 + i, "document_id": 2, "doc": "D", "heading": f"m{i}", "content": "提及", "kind": "mention"} for i in range(3)]
                + [{"chunk_id": 30 + i, "document_id": 3, "doc": "G", "heading": f"g{i}", "content": "桥", "kind": "graph"} for i in range(3)]
            ),
            "prototypes": [
                {"chunk_id": -9, "document_id": 9, "doc": "p.png", "heading": "原型图", "content": "原型", "kind": "prototype"}
            ],
        }
        text, sources, truncated = assemble_evidence(cand)
        assert truncated  # 1+3+1+3=8 > 6
        # 优先级:主段最先,原型保底一席排在提及前(挂靠了就必须进包),图谱桥垫底被挤
        assert text.index("主段") < text.index("原型") < text.index("提及")
        assert text.count("### 来源") == MAX_BLOCKS_PER_PACK
        assert sources[0].startswith("《SRS》")
        assert any("p.png" in s for s in sources)  # 原型必进来源清单

    def test_char_cap(self) -> None:
        cand = {
            "key": "k", "code": None, "title": "t",
            "primary": [
                {"chunk_id": 1, "document_id": 1, "doc": "D", "heading": "h", "content": "x" * (MAX_PACK_CHARS + 500), "kind": "primary"}
            ],
            "supplements": [], "prototypes": [],
        }
        text, _, truncated = assemble_evidence(cand)
        assert truncated and len(text) <= MAX_PACK_CHARS + 200
