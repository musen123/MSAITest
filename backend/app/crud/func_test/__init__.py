"""功能测试模块 CRUD"""

from app.crud.func_test.case_execution import crud_case_execution
from app.crud.func_test.document import crud_document
from app.crud.func_test.requirement import crud_requirement
from app.crud.func_test.test_case import crud_test_case

__all__ = [
    "crud_document",
    "crud_requirement",
    "crud_test_case",
    "crud_case_execution",
]
