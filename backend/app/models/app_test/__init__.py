"""
APP 自动化测试模块数据模型

导出用例（AppScript）、执行记录（AppExecution）、套件（AppSuite/AppSuiteCase）
与套件执行汇总（AppSuiteExecution）。设备/执行机域见 app_device。
"""

from app.models.app_test.execution import AppExecution, AppExecutionStatus
from app.models.app_test.script import AppScript, AppScriptStatus
from app.models.app_test.suite import AppSuite, AppSuiteCase
from app.models.app_test.suite_execution import (
    AppSuiteExecution,
    AppSuiteExecutionStatus,
)

__all__ = [
    "AppScript",
    "AppScriptStatus",
    "AppExecution",
    "AppExecutionStatus",
    "AppSuite",
    "AppSuiteCase",
    "AppSuiteExecution",
    "AppSuiteExecutionStatus",
]
