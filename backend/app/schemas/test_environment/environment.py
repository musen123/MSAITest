"""
测试环境相关的 Pydantic Schema
"""

from typing import Optional
from pydantic import BaseModel, Field, field_validator


class ScriptConfig(BaseModel):
    """脚本配置 Schema"""

    language: str = Field(description="编程语言：python/javascript")
    code: str = Field(description="脚本代码", default="")
    is_active: bool = Field(description="是否启用", default=False)

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        """验证语言类型"""
        if v not in ("python", "javascript"):
            raise ValueError("语言必须是 python 或 javascript")
        return v


class EnvironmentBase(BaseModel):
    """测试环境基础 Schema"""

    name: str = Field(min_length=1, max_length=100, description="环境名称")
    base_url: str = Field(min_length=1, max_length=500, description="环境基础URL")
    description: Optional[str] = Field(
        default=None, max_length=500, description="环境描述"
    )
    env_type: int = Field(default=1, description="环境类型: 1=功能测试 2=App测试")
    is_default: bool = Field(default=False, description="是否默认环境")
    is_global: bool = Field(default=False, description="是否全局环境")
    proxy_url: Optional[str] = Field(
        default=None, max_length=500, description="代理URL"
    )
    timeout: int = Field(default=30, ge=1, le=300, description="请求超时时间（秒）")
    verify_ssl: bool = Field(default=True, description="是否校验 HTTPS 证书")
    allow_redirects: bool = Field(default=True, description="是否跟随重定向")
    keep_cookies: bool = Field(default=False, description="是否保持 Cookie 会话")
    retry_times: int = Field(default=1, ge=0, le=10, description="连接类异常重试次数")
    pre_script: Optional[ScriptConfig] = Field(default=None, description="前置脚本")
    post_script: Optional[ScriptConfig] = Field(default=None, description="后置脚本")

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """验证基础URL格式"""
        if not v.startswith(("http://", "https://")):
            raise ValueError("基础URL必须以 http:// 或 https:// 开头")
        return v


class EnvironmentCreate(EnvironmentBase):
    """创建环境请求 Schema"""

    pass


class EnvironmentUpdate(BaseModel):
    """更新环境请求 Schema"""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    base_url: Optional[str] = Field(default=None, min_length=1, max_length=500)
    description: Optional[str] = Field(default=None, max_length=500)
    env_type: Optional[int] = Field(
        default=None, description="环境类型: 1=功能测试 2=App测试"
    )
    is_default: Optional[bool] = Field(default=None)
    is_global: Optional[bool] = Field(default=None)
    proxy_url: Optional[str] = Field(default=None, max_length=500)
    timeout: Optional[int] = Field(default=None, ge=1, le=300)
    verify_ssl: Optional[bool] = Field(default=None)
    allow_redirects: Optional[bool] = Field(default=None)
    keep_cookies: Optional[bool] = Field(default=None)
    retry_times: Optional[int] = Field(default=None, ge=0, le=10)
    pre_script: Optional[ScriptConfig] = None
    post_script: Optional[ScriptConfig] = None


class SutPrometheusTestRequest(BaseModel):
    """测试 SUT Prometheus 连接请求(可传未保存的 url/auth 以便保存前先验证)"""

    url: Optional[str] = Field(
        default=None, max_length=500, description="覆盖已存地址(留空=用已存)"
    )
    auth: Optional[str] = Field(
        default=None, max_length=500, description="覆盖已存鉴权(留空=用已存)"
    )


class EnvironmentResponse(BaseModel):
    """环境响应 Schema"""

    id: int = Field(description="环境ID")
    project_id: int = Field(description="项目ID")
    name: str = Field(description="环境名称")
    base_url: str = Field(description="环境基础URL")
    description: Optional[str] = Field(default=None, description="环境描述")
    env_type: int = Field(default=1, description="环境类型: 1=功能测试 2=App测试")
    is_default: bool = Field(description="是否默认环境")
    is_global: bool = Field(description="是否全局环境")
    proxy_url: Optional[str] = Field(default=None, description="代理URL")
    timeout: int = Field(description="请求超时时间（秒）")
    verify_ssl: bool = Field(default=True, description="是否校验 HTTPS 证书")
    allow_redirects: bool = Field(default=True, description="是否跟随重定向")
    keep_cookies: bool = Field(default=False, description="是否保持 Cookie 会话")
    retry_times: int = Field(default=1, description="连接类异常重试次数")
    pre_script: Optional[ScriptConfig] = Field(default=None, description="前置脚本")
    post_script: Optional[ScriptConfig] = Field(default=None, description="后置脚本")
    variable_count: int = Field(default=0, description="变量数量")
    created_at: str = Field(description="创建时间")
    updated_at: str = Field(description="更新时间")
    model_config = {"from_attributes": True}


class EnvironmentListResponse(BaseModel):
    """环境列表查询 Schema"""

    is_global: Optional[bool] = Field(default=None, description="是否仅获取全局环境")
    env_type: Optional[int] = Field(
        default=None, description="环境类型筛选: 1=功能测试 2=App测试"
    )
    keyword: Optional[str] = Field(default=None, description="搜索关键词")


class EnvironmentCloneRequest(BaseModel):
    """克隆环境请求 Schema"""

    name: str = Field(min_length=1, max_length=100, description="新环境名称")


class EnvironmentCloneResponse(BaseModel):
    """克隆环境响应 Schema"""

    id: int = Field(description="新环境ID")
    name: str = Field(description="新环境名称")
    source_env_id: int = Field(description="源环境ID")
