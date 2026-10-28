"""
数据库连接相关的 Pydantic Schema
"""

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# 数据库连接状态常量
class ConnectionStatus:
    """数据库连接状态常量"""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    UNKNOWN = "unknown"

    ALL = {CONNECTED, DISCONNECTED, UNKNOWN}


# 支持的数据库类型
class DatabaseType:
    """数据库类型常量"""

    MYSQL = "MySQL"
    POSTGRESQL = "PostgreSQL"
    ORACLE = "Oracle"
    SQLSERVER = "SQLServer"
    MONGODB = "MongoDB"
    REDIS = "Redis"

    ALL = {MYSQL, POSTGRESQL, ORACLE, SQLSERVER, MONGODB, REDIS}


class DatabaseBase(BaseModel):
    """数据库连接基础 Schema"""

    name: str = Field(min_length=1, max_length=100, description="连接名称")
    db_type: str = Field(description="数据库类型")
    host: str = Field(min_length=1, max_length=255, description="数据库地址")
    port: int = Field(ge=1, le=65535, description="端口号")
    database: str = Field(min_length=1, max_length=100, description="数据库名")
    username: str = Field(min_length=1, max_length=100, description="用户名")
    password: str = Field(min_length=1, max_length=255, description="密码")
    charset: Optional[str] = Field(
        default="utf8mb4", max_length=20, description="字符集"
    )
    connection_params: Optional[dict[str, Any]] = Field(
        default=None, description="额外连接参数"
    )
    allow_write: bool = Field(
        default=False,
        description="是否允许写操作（造数/清理等破坏性 SQL），默认关闭",
    )

    @field_validator("db_type")
    @classmethod
    def validate_db_type(cls, v: str) -> str:
        """验证数据库类型"""
        if v not in DatabaseType.ALL:
            raise ValueError(f"数据库类型必须是 {', '.join(DatabaseType.ALL)} 之一")
        return v


class DatabaseCreate(DatabaseBase):
    """创建数据库连接请求 Schema"""

    pass


class DatabaseUpdate(BaseModel):
    """更新数据库连接请求 Schema"""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    db_type: Optional[str] = None
    host: Optional[str] = Field(default=None, min_length=1, max_length=255)
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    database: Optional[str] = Field(default=None, min_length=1, max_length=100)
    username: Optional[str] = Field(default=None, min_length=1, max_length=100)
    password: Optional[str] = Field(default=None, min_length=1, max_length=255)
    charset: Optional[str] = Field(default=None, max_length=20)
    connection_params: Optional[dict[str, Any]] = None
    allow_write: Optional[bool] = Field(
        default=None, description="是否允许写操作"
    )


class DatabaseResponse(BaseModel):
    """数据库连接响应 Schema"""

    id: int = Field(description="连接ID")
    project_id: int = Field(description="项目ID")
    name: str = Field(description="连接名称")
    db_type: str = Field(description="数据库类型")
    host: str = Field(description="数据库地址")
    port: int = Field(description="端口号")
    database: str = Field(description="数据库名")
    username: str = Field(description="用户名")
    password: str = Field(description="密码")
    charset: Optional[str] = Field(default=None, description="字符集")
    connection_params: Optional[dict[str, Any]] = Field(
        default=None, description="连接参数"
    )
    allow_write: bool = Field(default=False, description="是否允许写操作")
    connection_status: str = Field(description="连接状态")
    last_test_time: Optional[str] = Field(default=None, description="最后测试时间")
    last_test_result: Optional[str] = Field(default=None, description="最后测试结果")
    created_at: str = Field(description="创建时间")
    updated_at: str = Field(description="更新时间")

    model_config = {"from_attributes": True}


class DatabaseTestRequest(BaseModel):
    """测试数据库连接请求 Schema"""

    model_config = {"extra": "ignore"}


class DatabaseTestResponse(BaseModel):
    """测试数据库连接响应 Schema"""

    status: str = Field(description="连接状态")
    response_time: Optional[int] = Field(default=None, description="响应时间（毫秒）")
    message: str = Field(description="测试消息")
    error: Optional[str] = Field(default=None, description="错误信息")
    tested_at: str = Field(description="测试时间")
