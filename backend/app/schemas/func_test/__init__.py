"""功能测试模块 Pydantic Schemas"""

from app.schemas.func_test.case_execution import (
    CaseExecutionCreate,
    CaseExecutionListResponse,
    CaseExecutionResponse,
)
from app.schemas.func_test.document import (
    DocumentListResponse,
    DocumentResponse,
    DocumentUpdate,
)
from app.schemas.func_test.requirement import (
    RequirementCreate,
    RequirementListResponse,
    RequirementResponse,
    RequirementReview,
    RequirementUpdate,
)
from app.schemas.func_test.test_case import (
    CaseStepSchema,
    TestCaseCreate,
    TestCaseListResponse,
    TestCaseResponse,
    TestCaseUpdate,
)

__all__ = [
    # Document
    "DocumentResponse",
    "DocumentListResponse",
    "DocumentUpdate",
    # Requirement
    "RequirementCreate",
    "RequirementUpdate",
    "RequirementResponse",
    "RequirementListResponse",
    "RequirementReview",
    # Test Case
    "CaseStepSchema",
    "TestCaseCreate",
    "TestCaseUpdate",
    "TestCaseResponse",
    "TestCaseListResponse",
    # Case Execution
    "CaseExecutionCreate",
    "CaseExecutionResponse",
    "CaseExecutionListResponse",
]
