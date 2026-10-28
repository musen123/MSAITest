"""
API 路由汇总

注册所有 API 路由
"""

from fastapi import APIRouter
from app.api.v1.endpoints import projects
from app.api.v1.endpoints.logs import operation_logs
from app.api.v1.endpoints.auth import login
from app.api.v1.endpoints.bugs import actions as bug_actions
from app.api.v1.endpoints.bugs import ai_analysis as bug_ai_analysis
from app.api.v1.endpoints.bugs import crud as bug_crud
from app.api.v1.endpoints.bugs import histories as bug_histories
from app.api.v1.endpoints.chat import conversations as chat_conversations
from app.api.v1.endpoints.chat import ws as chat_ws
from app.api.v1.endpoints.func_test import case_executions as func_case_executions
from app.api.v1.endpoints.func_test import documents as func_documents
from app.api.v1.endpoints.func_test import requirements as func_requirements
from app.api.v1.endpoints.func_test import test_cases as func_test_cases
from app.api.v1.endpoints.knowledge import documents as kb_documents
from app.api.v1.endpoints.knowledge import knowledge_base as kb_base
from app.api.v1.endpoints.knowledge import search as kb_search
from app.api.v1.endpoints.knowledge import graph as kb_graph
from app.api.v1.endpoints.reports import router as reports_router
from app.api.v1.endpoints.roles import role
from app.api.v1.endpoints.test_environment import (
    databases_router,
    environments_router,
    functions_router,
    variables_router,
)
from app.api.v1.endpoints.users import user
from app.api.v1.endpoints.users import llm_config as user_llm_config
from app.api.v1.endpoints.ai import ai_tasks as unified_ai_tasks
from app.api.v1.endpoints.app_device import agents as app_agents
from app.api.v1.endpoints.app_device import automation as app_automation
from app.api.v1.endpoints.app_device import devices as app_devices
from app.api.v1.endpoints.app_test import executions as app_executions
from app.api.v1.endpoints.app_test import explore as app_explore
from app.api.v1.endpoints.app_test import report as app_report
from app.api.v1.endpoints.app_test import scripts as app_scripts
from app.api.v1.endpoints.app_test import suite_executions as app_suite_executions
from app.api.v1.endpoints.app_test import suites as app_suites
from app.api.v1.endpoints.test_data import datasets as test_data_datasets
from app.api.v1.endpoints.test_data import files as test_data_files
from app.api.v1.endpoints import celery_monitor as celery_monitor_ep

api_router = APIRouter()
api_router.include_router(login.router, prefix="/auth", tags=["认证授权"])
api_router.include_router(user.router, prefix="/users", tags=["用户管理"])
api_router.include_router(
    user_llm_config.router, prefix="/users", tags=["用户大模型配置"]
)
api_router.include_router(role.router, prefix="/roles", tags=["角色管理"])
api_router.include_router(projects.router)
from app.api.v1.endpoints.scheduler import scheduled_jobs

api_router.include_router(
    scheduled_jobs.router,
    prefix="/projects/{project_id}/scheduled-jobs",
    tags=["定时任务"],
)
api_router.include_router(operation_logs.router, prefix="/logs", tags=["操作日志"])
api_router.include_router(
    environments_router,
    prefix="/projects/{project_id}/environments",
    tags=["测试环境管理"],
)
api_router.include_router(
    variables_router,
    prefix="/projects/{project_id}/environments/{env_id}/variables",
    tags=["环境变量管理"],
)
api_router.include_router(
    databases_router, prefix="/projects/{project_id}/databases", tags=["数据库连接管理"]
)
api_router.include_router(
    functions_router, prefix="/projects/{project_id}/functions", tags=["全局函数管理"]
)
api_router.include_router(celery_monitor_ep.router, prefix="/system", tags=["系统监控"])
api_router.include_router(
    bug_crud.router, prefix="/projects/{project_id}/bugs", tags=["缺陷管理 - Bug CRUD"]
)
api_router.include_router(
    bug_actions.router,
    prefix="/projects/{project_id}/bugs",
    tags=["缺陷管理 - 状态流转"],
)
api_router.include_router(
    bug_histories.router,
    prefix="/projects/{project_id}/bugs",
    tags=["缺陷管理 - 操作历史"],
)
api_router.include_router(
    bug_ai_analysis.router,
    prefix="/projects/{project_id}/bugs",
    tags=["缺陷管理 - AI 分析"],
)
api_router.include_router(
    reports_router, prefix="/projects/{project_id}/reports", tags=["测试报告"]
)
api_router.include_router(
    func_documents.router,
    prefix="/projects/{project_id}/func-documents",
    tags=["功能测试 - 文档管理"],
)
api_router.include_router(
    func_requirements.router,
    prefix="/projects/{project_id}/func-requirements",
    tags=["功能测试 - 需求管理"],
)
api_router.include_router(
    func_test_cases.router,
    prefix="/projects/{project_id}/func-test-cases",
    tags=["功能测试 - 用例管理"],
)
api_router.include_router(
    func_case_executions.router,
    prefix="/projects/{project_id}/func-test-cases",
    tags=["功能测试 - 执行记录"],
)
api_router.include_router(
    unified_ai_tasks.router,
    prefix="/projects/{project_id}/ai-tasks",
    tags=["AI 任务中心"],
)
api_router.include_router(
    test_data_datasets.router,
    prefix="/projects/{project_id}/test-datasets",
    tags=["测试数据中心 - 数据集"],
)
api_router.include_router(
    test_data_files.router,
    prefix="/projects/{project_id}/test-files",
    tags=["测试数据中心 - 文件资产"],
)
api_router.include_router(
    app_agents.router, prefix="/app/agents", tags=["APP自动化 - 执行机"]
)
api_router.include_router(
    app_devices.router, prefix="/app/devices", tags=["APP自动化 - 设备"]
)
api_router.include_router(
    app_automation.router, prefix="/app/devices", tags=["APP自动化 - 录制操作台"]
)
api_router.include_router(
    app_scripts.router,
    prefix="/projects/{project_id}/app/scripts",
    tags=["APP自动化 - 用例"],
)
api_router.include_router(
    app_executions.router,
    prefix="/projects/{project_id}/app/executions",
    tags=["APP自动化 - 执行记录"],
)
api_router.include_router(
    app_explore.router,
    prefix="/projects/{project_id}/app/automation",
    tags=["APP自动化 - 探索式生成"],
)
api_router.include_router(
    app_suites.router,
    prefix="/projects/{project_id}/app/suites",
    tags=["APP自动化 - 套件"],
)
api_router.include_router(
    app_suite_executions.router,
    prefix="/projects/{project_id}/app/suite-executions",
    tags=["APP自动化 - 套件执行"],
)
api_router.include_router(
    app_report.router,
    prefix="/projects/{project_id}/app/report",
    tags=["APP自动化 - 报表"],
)
api_router.include_router(
    kb_search.router,
    prefix="/projects/{project_id}/knowledge",
    tags=["项目知识库 - 检索（自研）"],
)
api_router.include_router(
    kb_graph.router,
    prefix="/projects/{project_id}/knowledge",
    tags=["项目知识库 - 图谱（自研）"],
)
api_router.include_router(
    kb_base.router,
    prefix="/projects/{project_id}/knowledge",
    tags=["项目知识库 - 元信息"],
)
api_router.include_router(
    kb_documents.router,
    prefix="/projects/{project_id}/knowledge/documents",
    tags=["项目知识库 - 文档"],
)
api_router.include_router(
    chat_conversations.router,
    prefix="/projects/{project_id}/chat",
    tags=["智能体对话 - 会话"],
)
api_router.include_router(
    chat_ws.router,
    prefix="/projects/{project_id}/chat",
    tags=["智能体对话 - WebSocket"],
)
