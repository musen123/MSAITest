"""
项目 CRUD 模块

导出所有项目相关的 CRUD 操作类
"""

from app.crud.project.config import CRUDProjectConfig, project_config
from app.crud.project.member import CRUDProjectMember, project_member
from app.crud.project.module import CRUDProjectModule, project_module
from app.crud.project.project import CRUDProject, project

__all__ = [
    "CRUDProject",
    "project",
    "CRUDProjectModule",
    "project_module",
    "CRUDProjectMember",
    "project_member",
    "CRUDProjectConfig",
    "project_config",
]
