"""
测试环境管理 API 端点模块

包含测试环境、环境变量、数据库连接、全局函数等管理接口
"""

from app.api.v1.endpoints.test_environment.databases import router as databases_router
from app.api.v1.endpoints.test_environment.environments import (
    router as environments_router,
)
from app.api.v1.endpoints.test_environment.functions import router as functions_router
from app.api.v1.endpoints.test_environment.variables import router as variables_router

__all__ = [
    "databases_router",
    "environments_router",
    "functions_router",
    "variables_router",
]
