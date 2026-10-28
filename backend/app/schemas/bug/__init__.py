"""
缺陷管理 Pydantic Schema
"""

from app.schemas.bug.bug import (
    BugCreate,
    BugListItem,
    BugListResponse,
    BugResponse,
    BugUpdate,
)
from app.schemas.bug.bug_actions import (
    BugArchive,
    BugAssign,
    BugAssignResponse,
    BugResolve,
    BugStatusChange,
    BugStatusResponse,
)
from app.schemas.bug.bug_ai_analysis import (
    AiAnalysisResponse,
    AiAnalysisStatusResponse,
    AiAnalysisTrigger,
)
from app.schemas.bug.bug_history import BugHistoryResponse
from app.schemas.bug.bug_statistics import BugStatistics, BugTrends

__all__ = [
    # Bug CRUD
    "BugCreate",
    "BugUpdate",
    "BugResponse",
    "BugListItem",
    "BugListResponse",
    # Bug Actions
    "BugStatusChange",
    "BugAssign",
    "BugResolve",
    "BugArchive",
    "BugStatusResponse",
    "BugAssignResponse",
    # Bug History
    "BugHistoryResponse",
    # AI Analysis
    "AiAnalysisTrigger",
    "AiAnalysisStatusResponse",
    "AiAnalysisResponse",
    # Statistics
    "BugStatistics",
    "BugTrends",
]
