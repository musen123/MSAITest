"""分批生成流水线纯逻辑回归（零 DB 零 LLM）。

守护企业可靠性设计的关键不变量：
  - normalize_points：脏输出净化、id 稳定去重、非法 group 兜底；
  - plan_batches：已覆盖点不进批、组间不混批、组内按上限切批、组序 正向→边界→异常；
  - resolve_code：编号撞车/缺失回退 None（DB 生成器兜底），防唯一约束炸整批事务；
  - coverage_stats：覆盖率 = 代码侧对账（历史覆盖 + 本次 covers 声明）。
"""

from app.ai_core.graphs.func_test.generate_case import (
    MAX_POINTS_PER_BATCH,
    coverage_stats,
    normalize_points,
    plan_batches,
    resolve_code,
)


def _pt(pid, group="正向", desc=None, covered=False):
    return {"id": pid, "group": group, "desc": desc or f"点{pid}", "covered": covered}


class TestNormalizePoints:
    def test_dict_with_points_key(self) -> None:
        out = normalize_points({"points": [{"id": 1, "group": "正向", "desc": "a"}]})
        assert out == [{"id": 1, "group": "正向", "desc": "a", "covered": False}]

    def test_junk_filtered(self) -> None:
        out = normalize_points([{"id": 1, "desc": ""}, "not-a-dict", None])
        assert out == []

    def test_invalid_group_defaults(self) -> None:
        out = normalize_points([{"id": 1, "group": "奇怪分组", "desc": "a"}])
        assert out[0]["group"] == "异常"

    def test_duplicate_and_missing_ids_reassigned(self) -> None:
        out = normalize_points(
            [
                {"id": 1, "group": "正向", "desc": "a"},
                {"id": 1, "group": "正向", "desc": "b"},   # 重复 id → 重排
                {"group": "边界", "desc": "c"},              # 缺 id → 补
            ]
        )
        ids = [p["id"] for p in out]
        assert len(ids) == len(set(ids)) == 3

    def test_non_list_returns_empty(self) -> None:
        assert normalize_points("garbage") == []
        assert normalize_points(None) == []


class TestPlanBatches:
    def test_covered_points_excluded(self) -> None:
        pts = [_pt(1), _pt(2, covered=True), _pt(3)]
        batches = plan_batches(pts)
        flat = [p["id"] for b in batches for p in b]
        assert flat == [1, 3]

    def test_groups_not_mixed_in_one_batch(self) -> None:
        pts = [_pt(1, "正向"), _pt(2, "边界"), _pt(3, "正向")]
        batches = plan_batches(pts)
        for b in batches:
            assert len({p["group"] for p in b}) == 1

    def test_group_order_and_chunking(self) -> None:
        pts = [_pt(i, "异常") for i in range(1, 8)] + [_pt(10, "正向")]
        batches = plan_batches(pts, max_per_batch=3)
        # 正向排最前
        assert batches[0][0]["group"] == "正向"
        # 异常 7 个 → 3+3+1
        sizes = [len(b) for b in batches[1:]]
        assert sizes == [3, 3, 1]

    def test_default_cap_respected(self) -> None:
        pts = [_pt(i) for i in range(1, MAX_POINTS_PER_BATCH + 3)]
        batches = plan_batches(pts)
        assert all(len(b) <= MAX_POINTS_PER_BATCH for b in batches)

    def test_all_covered_yields_no_batches(self) -> None:
        assert plan_batches([_pt(1, covered=True)]) == []


class TestResolveCode:
    def test_collision_returns_none(self) -> None:
        used = {"TC-DL-001"}
        assert resolve_code("TC-DL-001", used) is None

    def test_fresh_code_registered(self) -> None:
        used: set = set()
        assert resolve_code("TC-DL-001", used) == "TC-DL-001"
        # 同批第二次出现同编号 → 回退 None
        assert resolve_code("TC-DL-001", used) is None

    def test_empty_returns_none(self) -> None:
        assert resolve_code(None, set()) is None
        assert resolve_code("  ", set()) is None


class TestCoverageStats:
    def test_mixed_sources_of_coverage(self) -> None:
        pts = [_pt(1, covered=True), _pt(2), _pt(3)]
        done, total, uncovered = coverage_stats(pts, covered_ids={2})
        assert (done, total) == (2, 3)
        assert [p["id"] for p in uncovered] == [3]

    def test_all_covered(self) -> None:
        pts = [_pt(1), _pt(2)]
        done, total, uncovered = coverage_stats(pts, covered_ids={1, 2})
        assert (done, total, uncovered) == (2, 2, [])
