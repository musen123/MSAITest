"""APP 自动化测试 Schema"""

from app.schemas.app_test.script import (
    AppExecutionOut,
    AppScriptCreate,
    AppScriptOut,
    AppScriptUpdate,
    AutomationSessionRef,
    AutomationStepIn,
    AutomationStepOut,
    ExploreIn,
    RecoveredStepOut,
)
from app.schemas.app_test.suite import (
    AppSuiteCaseItem,
    AppSuiteCasesReplaceIn,
    AppSuiteCreate,
    AppSuiteDetailOut,
    AppSuiteExecutionOut,
    AppSuiteOut,
    AppSuiteRunIn,
    AppSuiteUpdate,
)

__all__ = [
    "AppScriptCreate",
    "AppScriptUpdate",
    "AppScriptOut",
    "AppExecutionOut",
    "AutomationSessionRef",
    "AutomationStepIn",
    "AutomationStepOut",
    "ExploreIn",
    "RecoveredStepOut",
    "AppSuiteCreate",
    "AppSuiteUpdate",
    "AppSuiteOut",
    "AppSuiteDetailOut",
    "AppSuiteCaseItem",
    "AppSuiteCasesReplaceIn",
    "AppSuiteRunIn",
    "AppSuiteExecutionOut",
]
