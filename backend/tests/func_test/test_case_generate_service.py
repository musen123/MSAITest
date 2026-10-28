"""用例生成落库标准化回归（纯逻辑，零 DB 零 LLM）。

守护"可执行性改造"后 prompt 输出 → ORM 字段的标准化不变量：
  - 结构化步骤 [{step_no, action, expected}] 原样透传（下游桥接靠 action/expected）；
  - 旧的字符串步骤仍兼容（补 step_no/expected=空）；
  - ui_automatable=false 落成"非UI自动化"标签，缺省/true 不打标；
  - 前置条件列表按行拼接（含【入口路径】/【数据前置】标签原样保留）。
"""

from app.ai_core.prompts.func_test_prompts import GENERATE_CASE_SYSTEM_PROMPT
from app.services.func_test.case_generate_service import (
    NON_UI_AUTOMATABLE_TAG,
    _coerce_preconditions,
    _coerce_steps,
    _coerce_tags,
)


class TestPromptPlaceholderSyntax:
    def test_prompt_uses_double_brace_placeholder(self) -> None:
        """占位符必须是 ${{键名}}（平台统一语法：接口/性能/UI 一致），
        不能是单花括号 ${键名} 或裸 {键名}——否则跨工具复用时渲染语法不一致。"""
        assert "${{username}}" in GENERATE_CASE_SYSTEM_PROMPT
        assert "${{键名}}" in GENERATE_CASE_SYSTEM_PROMPT
        # 不得残留单花括号占位符（${username} 会被 ${{username}} 判否）
        assert "${username}" not in GENERATE_CASE_SYSTEM_PROMPT
        assert "英文标识符" in GENERATE_CASE_SYSTEM_PROMPT


class TestCoerceSteps:
    def test_structured_steps_pass_through(self) -> None:
        """新 prompt 的结构化步骤（带每步 expected）必须原样保留。"""
        steps = [
            {"step_no": 1, "action": "在『用户名』输入框输入 ${{username}}", "expected": "输入框显示该值"},
            {"step_no": 2, "action": "点击『登录』按钮", "expected": "跳转到工作台首页"},
        ]
        assert _coerce_steps(steps) == steps

    def test_legacy_string_steps_still_coerced(self) -> None:
        """旧字符串步骤兼容：补 step_no，expected 置空。"""
        out = _coerce_steps(["步骤1", "步骤2"])
        assert out == [
            {"step_no": 1, "action": "步骤1", "expected": ""},
            {"step_no": 2, "action": "步骤2", "expected": ""},
        ]

    def test_empty_returns_none(self) -> None:
        assert _coerce_steps(None) is None
        assert _coerce_steps([]) is None


class TestCoerceTags:
    def test_non_automatable_gets_tag(self) -> None:
        assert _coerce_tags(None, False) == [NON_UI_AUTOMATABLE_TAG]

    def test_automatable_true_no_tag(self) -> None:
        assert _coerce_tags(None, True) is None

    def test_automatable_missing_no_tag(self) -> None:
        """ui_automatable 缺省（LLM 未给）视为可自动化，不打标。"""
        assert _coerce_tags(None, None) is None

    def test_merges_existing_tags(self) -> None:
        assert _coerce_tags(["冒烟"], False) == ["冒烟", NON_UI_AUTOMATABLE_TAG]

    def test_no_duplicate_marker(self) -> None:
        assert _coerce_tags([NON_UI_AUTOMATABLE_TAG], False) == [NON_UI_AUTOMATABLE_TAG]

    def test_string_tags_normalized(self) -> None:
        assert _coerce_tags("回归", None) == ["回归"]

    def test_blank_entries_dropped(self) -> None:
        assert _coerce_tags(["", "  ", "有效"], True) == ["有效"]


class TestCoercePreconditions:
    def test_labeled_list_joined_by_newline(self) -> None:
        """入口路径/数据前置标签必须原样保留（桥接会整段透传给 Web 生成）。"""
        pre = [
            "【入口路径】登录系统 → 进入『订单管理』菜单",
            "【数据前置】存在一笔待支付订单",
        ]
        out = _coerce_preconditions(pre)
        assert out == "【入口路径】登录系统 → 进入『订单管理』菜单\n【数据前置】存在一笔待支付订单"

    def test_empty_returns_none(self) -> None:
        assert _coerce_preconditions(None) is None
        assert _coerce_preconditions([]) is None
