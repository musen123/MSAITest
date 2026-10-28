"""
项目 Schema 模块

导出所有项目相关的 Pydantic Schema
"""

from app.schemas.project.config import (
    ConfigBase,
    ConfigCreate,
    ConfigResponse,
    ConfigUpdate,
)
from app.schemas.project.member import (
    MemberCreate,
    MemberListQuery,
    MemberPermissionsResponse,
    MemberResponse,
    MemberRoleUpdate,
    ProjectTransferRequest,
    ProjectTransferResponse,
    UserInProject,
)
from app.schemas.project.module import (
    ModuleCreate,
    ModuleMove,
    ModuleResponse,
    ModuleTreeNode,
    ModuleUpdate,
)
from app.schemas.project.project import (
    BugStatistics,
    CaseStatistics,
    ExecutionTrendItem,
    MemberStatisticsItem,
    ProjectCreate,
    ProjectDetailResponse,
    ProjectListQuery,
    ProjectResponse,
    ProjectStatisticsResponse,
    ProjectStatusUpdate,
    ProjectUpdate,
    UserSimple,
)

__all__ = [
    # Project
    "UserSimple",
    "ProjectCreate",
    "ProjectUpdate",
    "ProjectResponse",
    "ProjectDetailResponse",
    "ProjectListQuery",
    "ProjectStatusUpdate",
    "ProjectStatisticsResponse",
    "CaseStatistics",
    "BugStatistics",
    "ExecutionTrendItem",
    "MemberStatisticsItem",
    # Module
    "ModuleCreate",
    "ModuleUpdate",
    "ModuleMove",
    "ModuleResponse",
    "ModuleTreeNode",
    # Member
    "UserInProject",
    "MemberCreate",
    "MemberResponse",
    "MemberRoleUpdate",
    "MemberListQuery",
    "MemberPermissionsResponse",
    "ProjectTransferRequest",
    "ProjectTransferResponse",
    # Config
    "ConfigBase",
    "ConfigCreate",
    "ConfigUpdate",
    "ConfigResponse",
]
