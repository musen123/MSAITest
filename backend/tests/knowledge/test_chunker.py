"""结构感知分块器单测（纯函数，WP3 probe 固化）

覆盖：标题树 heading_path / 父子块与小节 child-only / 中文句读切分 /
表格原子化+行组切重复表头 / 代码块原子 / seq 连续 / 嵌入文本拼接。
"""

import pytest

from app.services.knowledge.chunker import (
    CHILD_ONLY_THRESHOLD,
    TABLE_SLICE_MAX_CHARS,
    build_index_text,
    chunk_markdown,
)

pytestmark = pytest.mark.unit

LONG_CN = "用户发起退款后系统应在三个工作日内完成原路退回。" * 40  # ~1000 字无换行
TABLE_ROWS = "\n".join(
    f"| 字段{i} | string | 是 | 第{i}个参数的说明文字比较长一些 |" for i in range(60)
)
MD = f"""# 支付系统PRD

## 3 退款

### 3.2 退款时效

{LONG_CN}

### 3.3 接口定义

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
{TABLE_ROWS}

```python
def refund(order_id):
    return api.post("/refund", order_id)
```

## 4 附则

本节很短。
"""


@pytest.fixture(scope="module")
def drafts():
    return chunk_markdown(MD)


def _children(drafts):
    return [d for d in drafts if d.chunk_type != "parent"]


def _parents(drafts):
    return [d for d in drafts if d.chunk_type == "parent"]


class TestHeadingTree:
    def test_three_level_breadcrumb(self, drafts):
        paths = {d.heading_path for d in drafts}
        assert "支付系统PRD › 3 退款 › 3.2 退款时效" in paths
        assert "支付系统PRD › 3 退款 › 3.3 接口定义" in paths

    def test_index_text_prepends_heading(self, drafts):
        child = next(d for d in _children(drafts) if "退款时效" in d.heading_path)
        text = build_index_text(child.heading_path, child.content)
        assert text.startswith("支付系统PRD › 3 退款")


class TestChineseSplit:
    def test_no_mid_sentence_hard_cut(self, drafts):
        """长中文无换行段必须在句读处切开（评审实锤死代码分隔符缺句读的坑）"""
        children = [
            d for d in _children(drafts)
            if d.chunk_type == "text" and "退款时效" in d.heading_path
        ]
        assert children, "长段应产出多个 text child"
        for d in children:
            assert d.content.rstrip().endswith(("。", "！", "？", "；", "回")), d.content[-20:]

    def test_child_size_bounded(self, drafts):
        for d in _children(drafts):
            if d.chunk_type == "text":
                assert len(d.content) <= 470  # 400 目标 + keep_separator 缓冲


class TestAtomicBlocks:
    def test_table_sliced_with_header_repeated(self, drafts):
        tables = [d for d in _children(drafts) if d.chunk_type == "table"]
        assert len(tables) >= 2, "60 行表应按行组切成多片"
        for t in tables:
            lines = t.content.splitlines()
            assert lines[0].startswith("| 字段 |"), "每片必须重复表头行"
            assert "---" in lines[1]
            assert len(t.content) <= TABLE_SLICE_MAX_CHARS

    def test_code_block_atomic(self, drafts):
        codes = [d for d in _children(drafts) if d.chunk_type == "code"]
        assert len(codes) == 1
        assert codes[0].content.startswith("```")
        assert "def refund" in codes[0].content


class TestParentChild:
    def test_children_link_to_real_parents(self, drafts):
        parent_seqs = {p.seq for p in _parents(drafts)}
        linked = [d for d in _children(drafts) if d.parent_seq is not None]
        assert linked
        assert all(d.parent_seq in parent_seqs for d in linked)

    def test_small_section_child_only(self, drafts):
        small = [d for d in drafts if "4 附则" in d.heading_path]
        assert len(small) == 1
        assert small[0].chunk_type == "text"
        assert small[0].parent_seq is None
        assert len(small[0].content) <= CHILD_ONLY_THRESHOLD

    def test_seq_unique_and_sequential(self, drafts):
        seqs = [d.seq for d in drafts]
        assert seqs == list(range(len(drafts)))


class TestDocTypeProfiles:
    """P1a WP-A8:api_doc 接口节原子化 / test_case 每例一块"""

    API_MD = ("# 用户服务接口\n\n## 登录接口\n\nPOST /api/v1/auth/login,参数 username/password。"
              + "登录失败超过五次锁定账号三十分钟,返回统一错误码提示。" * 26
              + "\n\n## 登出接口\n\nPOST /api/v1/auth/logout,携带 token 即可。\n")

    def test_api_doc_section_atomic(self):
        hits = [d for d in chunk_markdown(self.API_MD, doc_type="api_doc")
                if "登录接口" in d.heading_path and d.chunk_type != "parent"]
        assert len(hits) == 1, "接口节 ≤1200 字应整节一块"
        assert 480 < hits[0].char_len <= 1200

    def test_generic_same_doc_splits(self):
        hits = [d for d in chunk_markdown(self.API_MD, doc_type="other")
                if "登录接口" in d.heading_path and d.chunk_type != "parent"]
        assert len(hits) > 1, "通用策略同文档应被细切(对照)"

    def test_test_case_child_typed_case(self):
        md = "# 用例\n\n## 用例1 锁定登录\n\n前置:已锁定。步骤:登录。预期:423。\n"
        drafts = chunk_markdown(md, doc_type="test_case")
        assert drafts and all(d.chunk_type == "case" for d in drafts if d.chunk_type != "parent")

    def test_oversized_section_falls_back(self):
        md = "# A\n\n## 超长接口\n\n" + "很长的描述内容需要正常切分。" * 120
        hits = [d for d in chunk_markdown(md, doc_type="api_doc")
                if d.chunk_type not in ("parent",)]
        assert len(hits) > 1, ">1200 字回落通用父子块策略"


class TestEdgeCases:
    def test_empty_input(self):
        assert chunk_markdown("") == []
        assert chunk_markdown("   \n  ") == []

    def test_no_heading_document(self):
        drafts = chunk_markdown("纯文本没有任何标题。" * 100)
        assert drafts
        assert all(d.heading_path == "" for d in drafts)

    def test_hash_and_tokens_computed(self, drafts):
        assert all(d.content_hash and d.token_len > 0 and d.char_len > 0 for d in drafts)
