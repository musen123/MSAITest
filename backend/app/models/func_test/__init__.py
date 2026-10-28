"""功能测试模块数据模型

导出需求 / 用例 / 文档 / 用例执行记录的 ORM。
"""

from app.models.func_test.case_execution import (
    CaseExecuteResult,
    FuncCaseExecution,
)
from app.models.func_test.document import (
    DocumentStatus,
    DocumentType,
    ProjectDocument,
)
from app.models.func_test.requirement import (
    RequirementPriority,
    RequirementSource,
    RequirementStatus,
    TestRequirement,
)
from app.models.func_test.test_case import (
    CasePriority,
    CaseSource,
    CaseStatus,
    CaseType,
    FuncTestCase,
    ValidationLevel,
)

__all__ = [
    # 文档
    "ProjectDocument",
    "DocumentType",
    "DocumentStatus",
    # 需求
    "TestRequirement",
    "RequirementPriority",
    "RequirementStatus",
    "RequirementSource",
    # 用例
    "FuncTestCase",
    "CasePriority",
    "CaseType",
    "ValidationLevel",
    "CaseStatus",
    "CaseSource",
    # 执行记录
    "FuncCaseExecution",
    "CaseExecuteResult",
]
