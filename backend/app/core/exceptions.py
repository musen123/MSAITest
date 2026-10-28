"""
自定义异常类

定义项目中使用的自定义异常
"""

from typing import Any, Optional


class BusinessException(Exception):
    """
    业务异常

    用于表示业务逻辑中的错误情况
    """

    def __init__(
        self,
        message: str,
        code: int = 400,
        data: Optional[Any] = None,
    ) -> None:
        """
        初始化业务异常

        Args:
            message: 错误消息
            code: 错误码（默认为 400）
            data: 额外的错误数据
        """
        self.message = message
        self.code = code
        self.data = data
        super().__init__(self.message)


class NotFoundException(BusinessException):
    """
    资源未找到异常
    """

    def __init__(self, message: str = "资源不存在", data: Optional[Any] = None) -> None:
        super().__init__(message, code=404, data=data)


class UnauthorizedException(BusinessException):
    """
    未授权异常
    """

    def __init__(self, message: str = "未授权访问", data: Optional[Any] = None) -> None:
        super().__init__(message, code=401, data=data)


class ForbiddenException(BusinessException):
    """
    禁止访问异常
    """

    def __init__(self, message: str = "禁止访问", data: Optional[Any] = None) -> None:
        super().__init__(message, code=403, data=data)


class ValidationException(BusinessException):
    """
    数据验证异常
    """

    def __init__(
        self, message: str = "数据验证失败", data: Optional[Any] = None
    ) -> None:
        super().__init__(message, code=422, data=data)


class ConflictException(BusinessException):
    """
    资源冲突异常
    """

    def __init__(self, message: str = "资源冲突", data: Optional[Any] = None) -> None:
        super().__init__(message, code=409, data=data)


class RateLimitException(BusinessException):
    """
    请求频率限制异常
    """

    def __init__(
        self, message: str = "请求过于频繁", data: Optional[Any] = None
    ) -> None:
        super().__init__(message, code=429, data=data)


class AIServiceException(BusinessException):
    """
    AI 服务异常
    """

    def __init__(
        self, message: str = "AI 服务调用失败", data: Optional[Any] = None
    ) -> None:
        super().__init__(message, code=500, data=data)


class TestExecutionException(BusinessException):
    """
    测试执行异常
    """

    def __init__(
        self, message: str = "测试执行失败", data: Optional[Any] = None
    ) -> None:
        super().__init__(message, code=500, data=data)
