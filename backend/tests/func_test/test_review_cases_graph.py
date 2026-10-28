"""AI 用例评审图纯逻辑回归（零 DB 零 LLM）。

守护:评审输出按 case_id 对齐写回;漏评用例进未评清单(绝不猜结论);
review_decs 截断;code 缺失用 db_{id} 兜底键。
"""

from types import SimpleNamespace

from app.ai_core.graphs.func_test.review_cases import (
    map_review_results,
    serialize_for_review,
)


def _case(cid, code=None, title="用例"):
    return SimpleNamespace(
        id=cid,
        code=code,
        title=title,
        priority="medium",
        preconditions=None,
        test_data=None,
        steps=[{"step_no": 1, "action": "a", "expected": ""}],
        expected_result=["e"],
    )


class TestSerialize:
    def test_code_fallback_key(self) -> None:
        out = serialize_for_review([_case(7, code=None)])
        assert out[0]["case_id"] == "db_7"

    def test_fields_aligned_with_generation_shape(self) -> None:
        out = serialize_for_review([_case(1, code="TC-A-001", title="登录")])
        assert out[0]["case_name"] == "登录"
        assert out[0]["execute_step"] == [{"step_no": 1, "action": "a", "expected": ""}]


class TestMapResults:
    def test_aligned_by_case_id(self) -> None:
        cases = [_case(1, code="TC-A-001"), _case(2, code=None)]
        results = [
            {"case_id": "TC-A-001", "review_result": "通过", "review_decs": "ok",
             "ui_automatable": True},
            {"case_id": "db_2", "review_result": "不通过", "review_decs": "步骤不原子",
             "ui_automatable": False},
        ]
        mapped, missed = map_review_results(cases, results)
        assert mapped[1]["review_info"]["review_result"] == "通过"
        assert mapped[1]["ui_automatable"] is True
        assert mapped[2]["review_info"]["review_result"] == "不通过"
        assert mapped[2]["ui_automatable"] is False
        assert missed == []

    def test_ui_automatable_defaults_none_when_absent_or_bad(self) -> None:
        # 评审没给 ui_automatable、或给非布尔值 → 归 None（下游 update 会跳过、不误清列）
        cases = [_case(1, code="A"), _case(2, code="B")]
        results = [
            {"case_id": "A", "review_result": "通过"},
            {"case_id": "B", "review_result": "通过", "ui_automatable": "yes"},
        ]
        mapped, _ = map_review_results(cases, results)
        assert mapped[1]["ui_automatable"] is None
        assert mapped[2]["ui_automatable"] is None

    def test_missed_cases_not_guessed(self) -> None:
        cases = [_case(1, code="TC-A-001"), _case(2, code="TC-A-002")]
        results = [{"case_id": "TC-A-001", "review_result": "通过"}]
        mapped, missed = map_review_results(cases, results)
        assert 2 not in mapped
        assert [c.id for c in missed] == [2]

    def test_decs_truncated(self) -> None:
        cases = [_case(1, code="X")]
        results = [{"case_id": "X", "review_result": "不通过", "review_decs": "长" * 500}]
        mapped, _ = map_review_results(cases, results)
        assert len(mapped[1]["review_info"]["review_decs"]) == 200

    def test_garbage_results_tolerated(self) -> None:
        cases = [_case(1, code="X")]
        mapped, missed = map_review_results(cases, "not-a-list")
        assert mapped == {} and [c.id for c in missed] == [1]
