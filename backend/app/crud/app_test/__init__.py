"""APP 自动化测试模块 CRUD

用例（app_script）/ 执行记录（app_execution）/ 套件（app_suite 系）
数据访问层。设备域见 crud/app_device。
"""

from app.crud.app_test.execution import crud_app_execution
from app.crud.app_test.script import crud_app_script
from app.crud.app_test.suite import crud_app_suite, crud_app_suite_execution

__all__ = [
    "crud_app_script",
    "crud_app_execution",
    "crud_app_suite",
    "crud_app_suite_execution",
]
