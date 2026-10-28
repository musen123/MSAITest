"""
项目管理 API 路由

聚合所有项目管理相关的路由
"""

from fastapi import APIRouter

from app.api.v1.endpoints.projects import (
    crud,
    dashboard,
    members,
    modules,
    overview,
    report_center,
)

router = APIRouter(tags=["项目管理"])

# 项目概览仪表盘（/{project_id}/dashboard 为静态后缀路径，
# 需注册在 crud.router 的 GET /projects/{project_id} 之前不冲突，
# 但保险起见先于 crud 注册）
router.include_router(
    dashboard.router, prefix="/projects", tags=["项目概览"]
)

# 数据报表中心（资产/质量/AI 提效三维度聚合）
router.include_router(
    report_center.router, prefix="/projects", tags=["数据报表中心"]
)

# 项目管理路由（核心 CRUD）
# 路由: /api/v1/projects
router.include_router(crud.router, prefix="/projects", tags=["项目CRUD"])

# 项目成员管理路由
# 路由: /api/v1/project-members (使用平行路由避免与 projects 冲突)
router.include_router(members.router, prefix="/project-members", tags=["项目成员"])

# 项目模块管理路由
# 路由: /api/v1/project-modules (使用平行路由避免与 projects 冲突)
router.include_router(modules.router, prefix="/project-modules", tags=["项目模块"])

# 工作台总览路由
# 路由: /api/v1/projects-overview
# ⚠️ 独立前缀 /projects-overview（而非 /projects/overview），
#    避免与 crud.router 中 GET /projects/{project_id} 路径冲突
#    （FastAPI 会把 "overview" 解析为 project_id 触发 422）
router.include_router(
    overview.router, prefix="/projects-overview", tags=["工作台总览"]
)

__all__ = ["router"]
