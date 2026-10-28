"""
统一响应模型

定义 API 的统一响应格式
"""

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ResponseModel(BaseModel, Generic[T]):
    """
    统一响应模型

    所有 API 响应都应使用此模型
    """

    code: int = Field(default=200, description="状态码")
    message: str = Field(default="success", description="响应消息")
    data: Optional[T] = Field(default=None, description="响应数据")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "code": 200,
                    "message": "success",
                    "data": {"id": 1, "name": "示例数据"},
                }
            ]
        }
    )


class PageModel(BaseModel, Generic[T]):
    """
    分页响应模型
    """

    items: list[T] = Field(description="数据列表")
    total: int = Field(description="总数量")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页大小")
    total_pages: int = Field(description="总页数")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "items": [{"id": 1, "name": "项目1"}],
                    "total": 100,
                    "page": 1,
                    "page_size": 20,
                    "total_pages": 5,
                }
            ]
        }
    )


class PageResponseModel(BaseModel, Generic[T]):
    """
    分页统一响应模型
    """

    code: int = Field(default=200, description="状态码")
    message: str = Field(default="success", description="响应消息")
    data: PageModel[T] = Field(description="分页数据")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "code": 200,
                    "message": "success",
                    "data": {
                        "items": [{"id": 1, "name": "项目1"}],
                        "total": 100,
                        "page": 1,
                        "page_size": 20,
                        "total_pages": 5,
                    },
                }
            ]
        }
    )


def success_response(
    data: Optional[Any] = None, message: str = "success"
) -> ResponseModel:
    """
    成功响应

    Args:
        data: 响应数据
        message: 响应消息

    Returns:
        ResponseModel: 响应模型
    """
    return ResponseModel(code=200, message=message, data=data)


def error_response(
    message: str, code: int = 400, data: Optional[Any] = None
) -> ResponseModel:
    """
    错误响应

    Args:
        message: 错误消息
        code: 错误码
        data: 额外数据

    Returns:
        ResponseModel: 响应模型
    """
    return ResponseModel(code=code, message=message, data=data)


def page_response(
    items: list[Any],
    total: int,
    page: int,
    page_size: int,
    message: str = "success",
) -> PageResponseModel:
    """
    分页响应

    Args:
        items: 数据列表
        total: 总数量
        page: 当前页码
        page_size: 每页大小
        message: 响应消息

    Returns:
        PageResponseModel: 分页响应模型
    """
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

    return PageResponseModel(
        code=200,
        message=message,
        data=PageModel(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        ),
    )
