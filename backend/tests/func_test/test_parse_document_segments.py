"""长文档分段解析引擎单测（parse_document 截断修复）

切分：边界优先级/尾段合并/内容无损；标题栈；拼缝去重；
引擎：短文快路径用整篇 prompt / 多段携带上下文接续 / 截断二分重试 /
极限截断显式报错 / 空输出报错 / 进度回调。
"""

import re

import pytest

from app.services.func_test.document_parse_service import (
    _MIN_BISECT_CHARS,
    _SEG_TARGET_CHARS,
    _render_heading_stack,
    _stitch_parts,
    _update_heading_stack,
    rewrite_document_markdown,
    split_document_for_rewrite,
)

pytestmark = pytest.mark.unit


def _no_ws(s: str) -> str:
    return re.sub(r"\s+", "", s)


def _assert_lossless(original: str, segments: list[str]) -> None:
    """切分只允许在切点处丢弃空白，内容字符必须一个不少。"""
    assert _no_ws("".join(segments)) == _no_ws(original)


class TestSplitDocument:
    def test_short_doc_single_segment(self):
        text = "# 标题\n\n正文内容。"
        assert split_document_for_rewrite(text) == [text]

    def test_empty_doc(self):
        assert split_document_for_rewrite("   \n  ") == []

    def test_split_at_markdown_heading(self):
        # 每节 ~3000 字符，5 节共 ~15000，目标 8000 → 应在标题行前切开
        sections = [f"## 模块{i}\n" + "需求正文。" * 600 for i in range(5)]
        text = "\n".join(sections)
        segments = split_document_for_rewrite(text)
        assert len(segments) >= 2
        for seg in segments[:-1]:
            assert len(seg) <= _SEG_TARGET_CHARS
        # 非首段应从标题行开始（标题归属下一段）
        for seg in segments[1:]:
            assert seg.startswith("## 模块")
        _assert_lossless(text, segments)

    def test_split_at_blank_line_without_headings(self):
        paras = ["测试段落内容。" * 70 for _ in range(40)]  # 每段 ~490 字符
        text = "\n\n".join(paras)
        segments = split_document_for_rewrite(text)
        assert len(segments) >= 2
        for seg in segments[:-1]:
            assert len(seg) <= _SEG_TARGET_CHARS
        _assert_lossless(text, segments)

    def test_hard_cut_giant_single_line(self):
        text = "字" * 20000
        segments = split_document_for_rewrite(text)
        assert [len(s) for s in segments] == [8000, 8000, 4000]
        _assert_lossless(text, segments)

    def test_sentence_punct_cut(self):
        text = "本平台支持接口测试。" * 1600  # 16000 字符，无换行
        segments = split_document_for_rewrite(text)
        assert len(segments) >= 2
        assert segments[0].endswith("。")
        assert len(segments[0]) <= _SEG_TARGET_CHARS
        _assert_lossless(text, segments)

    def test_tiny_tail_merged(self):
        # 边界后只剩 800 字符（< 尾段下限 1500）→ 并入前段，总段数 1
        text = "a" * 7797 + "\n\n" + "b" * 800
        segments = split_document_for_rewrite(text)
        assert len(segments) == 1
        _assert_lossless(text, segments)


class TestHeadingStack:
    def test_stack_tracks_hierarchy(self):
        stack = _update_heading_stack([], "# 系统\n\n## 功能\n内容\n### 用户管理\n内容")
        assert stack == [(1, "系统"), (2, "功能"), (3, "用户管理")]
        stack = _update_heading_stack(stack, "## 非功能\n内容")
        assert stack == [(1, "系统"), (2, "非功能")]
        assert _render_heading_stack(stack) == "# 系统 > ## 非功能"

    def test_no_headings_keeps_stack(self):
        stack = [(1, "系统")]
        assert _update_heading_stack(stack, "纯正文，无标题") == [(1, "系统")]


class TestStitchParts:
    def test_plain_join(self):
        assert _stitch_parts(["A", "B"]) == "A\n\nB"

    def test_seam_duplicate_heading_dropped(self):
        parts = ["## 用户管理", "## 用户管理\n支持新增用户"]
        assert _stitch_parts(parts) == "## 用户管理\n\n支持新增用户"

    def test_empty_part_skipped(self):
        assert _stitch_parts(["A", "   ", "B"]) == "A\n\nB"

    def test_all_duplicate_part_dropped(self):
        assert _stitch_parts(["## 标题", "## 标题"]) == "## 标题"


class _Chunk:
    def __init__(self, content: str, finish: str | None = None):
        self.content = content
        self.response_metadata = {"finish_reason": finish} if finish else {}


class FakeLLM:
    """script(call_index, messages) -> (输出文本, finish_reason)"""

    def __init__(self, script):
        self.script = script
        self.calls: list[list] = []

    async def astream(self, messages):
        idx = len(self.calls)
        self.calls.append(messages)
        text, finish = self.script(idx, messages)
        # 模拟流式：拆两片输出 + 一个只带 finish_reason 的收尾 chunk
        mid = max(1, len(text) // 2)
        yield _Chunk(text[:mid])
        yield _Chunk(text[mid:])
        yield _Chunk("", finish)


def _human_text(messages) -> str:
    return messages[-1].content


class TestRewriteEngine:
    async def test_short_doc_uses_full_prompt_and_cleans(self):
        llm = FakeLLM(lambda i, m: ("```markdown\n# 出参\n内容\n```", None))
        result = await rewrite_document_markdown(llm, "短文档原文。", doc_type="other")
        assert result == "# 出参\n内容"
        assert len(llm.calls) == 1
        human = _human_text(llm.calls[0])
        assert "## 文档原文" in human
        assert "本段原文" not in human

    async def test_long_doc_segments_carry_context(self):
        sections = [f"## 模块{i}\n" + f"模块{i}正文。" * 600 for i in range(3)]
        text = "\n".join(sections)  # ~10500 字符 → 2 段以上

        def script(i, m):
            return (f"## 段{i}\n段{i}整理后的内容", None)

        llm = FakeLLM(script)
        ratios: list[float] = []
        logs: list[tuple[str, str]] = []
        result = await rewrite_document_markdown(
            llm,
            text,
            doc_type="requirement",
            doc_name="需求书",
            log=lambda msg, level: logs.append((msg, level)),
            progress=ratios.append,
        )
        assert len(llm.calls) >= 2
        # 第二段 prompt 必须带：分段标识、标题栈（含第一段输出的标题）、前段结尾
        human2 = _human_text(llm.calls[1])
        assert "第 2/" in human2
        assert "当前标题层级" in human2 and "## 段0" in human2
        assert "前一段解析结果的结尾" in human2
        assert "## 本段原文" in human2
        # 结果按序拼接
        assert result.index("## 段0") < result.index("## 段1")
        # 进度单调递增且收于 1.0
        assert ratios == sorted(ratios)
        assert ratios[-1] == pytest.approx(1.0)
        # 有切段日志
        assert any("切分为" in msg for msg, _ in logs)

    async def test_truncated_segment_bisected_and_retried(self):
        text = "字" * 2400  # 单段（<8000），截断后二分为 2×1200

        def script(i, m):
            if i == 0:
                return ("残缺输出", "length")
            return (f"## 部分{i}\n内容{i}", None)

        llm = FakeLLM(script)
        logs: list[tuple[str, str]] = []
        result = await rewrite_document_markdown(
            llm, text, log=lambda msg, level: logs.append((msg, level))
        )
        assert len(llm.calls) == 3  # 1 次截断 + 2 个半段
        assert "## 部分1" in result and "## 部分2" in result
        assert "残缺输出" not in result  # 截断的产物必须整段丢弃
        # 重试段走分段 prompt
        assert "## 本段原文" in _human_text(llm.calls[1])
        assert any("截断" in msg and level == "warning" for msg, level in logs)

    async def test_truncation_below_min_size_raises(self):
        text = "字" * 800  # < _MIN_BISECT_CHARS，截断后不可再分
        assert len(text) <= _MIN_BISECT_CHARS
        llm = FakeLLM(lambda i, m: ("半截", "length"))
        with pytest.raises(ValueError, match="截断"):
            await rewrite_document_markdown(llm, text)

    async def test_persistent_truncation_exhausts_depth_raises(self):
        text = "行内容。\n" * 4000  # 多段长文
        llm = FakeLLM(lambda i, m: ("半截", "length"))
        with pytest.raises(ValueError, match="截断"):
            await rewrite_document_markdown(llm, text)

    async def test_empty_output_on_substantial_segment_raises(self):
        llm = FakeLLM(lambda i, m: ("   ", None))
        with pytest.raises(ValueError, match="为空"):
            await rewrite_document_markdown(llm, "有效内容。" * 200)

    async def test_empty_input_raises(self):
        llm = FakeLLM(lambda i, m: ("x", None))
        with pytest.raises(ValueError, match="为空"):
            await rewrite_document_markdown(llm, "   ")
