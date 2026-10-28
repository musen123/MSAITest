"""AI 用例生成 — 字段标准化辅助

旧的 generate_cases_for_requirement 主流程已迁移至统一 AI 任务框架
（task_type=generate_case，见 app/ai_core/graphs/func_test/generate_case.py），
本模块仅保留 prompt 输出 → ORM 字段的标准化函数，供图复用。
"""

from typing import Optional


# ─────────────────────────────────────────────────────────────
# 辅助：标准化用例字段（适配 prompt 输出 → ORM 字段）
# ─────────────────────────────────────────────────────────────


def _normalize_priority(p) -> str:
    """把 P0/P1/P2 映射成 high/medium/low"""
    if not p:
        return "medium"
    p = str(p).strip().upper()
    return {
        "P0": "high",
        "P1": "medium",
        "P2": "low",
        "URGENT": "urgent",
        "HIGH": "high",
        "MEDIUM": "medium",
        "LOW": "low",
    }.get(p, "medium")


def _coerce_steps(value) -> Optional[list]:
    """将步骤字段标准化为 [{step_no, action, expected}]"""
    if not value:
        return None
    # 已经是结构化的列表
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return value
    # 字符串列表 → 转成 step_no/action/expected=空
    if isinstance(value, list):
        return [
            {"step_no": i + 1, "action": str(s), "expected": ""}
            for i, s in enumerate(value)
        ]
    return None


def _coerce_expected(value) -> Optional[list]:
    if not value:
        return None
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def _coerce_preconditions(value) -> Optional[str]:
    if not value:
        return None
    if isinstance(value, list):
        return "\n".join(str(v) for v in value)
    return str(value)


# 非 UI 自动化用例的标签标记（供下游"批量转 Web 脚本"按此过滤，避免把纯后端/接口
# 用例喂给 UI 自动化必然失败）。ui_automatable 缺省(None)视为可自动化，不打标。
NON_UI_AUTOMATABLE_TAG = "非UI自动化"


def _coerce_tags(raw_tags, ui_automatable) -> Optional[list]:
    """合并 LLM 返回的 tags 与 ui_automatable 派生标记，标准化为字符串列表。"""
    tags: list[str] = []
    if isinstance(raw_tags, list):
        tags = [str(t).strip() for t in raw_tags if str(t).strip()]
    elif isinstance(raw_tags, str) and raw_tags.strip():
        tags = [raw_tags.strip()]
    if ui_automatable is False and NON_UI_AUTOMATABLE_TAG not in tags:
        tags.append(NON_UI_AUTOMATABLE_TAG)
    return tags or None


