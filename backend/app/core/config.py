"""
应用配置管理

使用 Pydantic Settings 管理应用配置，支持从环境变量读取
"""

from functools import lru_cache
from typing import Annotated, List
from pydantic import AnyHttpUrl, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """
    应用配置类

    从环境变量和 .env 文件读取配置
    """

    PROJECT_NAME: str = "AI 智能测试平台"
    VERSION: str = "0.1.0"
    ENV: str = "development"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    PASSWORD_HASH_SCHEMES: List[str] = ["argon2"]
    PASSWORD_HASH_DEPRECATED: List[str] = ["auto"]
    db_host: str = Field(default="localhost", description="数据库主机")
    db_port: int = Field(default=3306, description="数据库端口")
    db_user: str = Field(default="root", description="数据库用户名")
    db_password: str = Field(default="", description="数据库密码")
    database: str = Field(default="ai_test_platform", description="数据库名称")

    @property
    def DATABASE_URL(self) -> str:
        """构建数据库连接 URL"""
        return f"mysql+aiomysql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.database}"

    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600
    admin_username: str = Field(default="admin", description="管理员用户名")
    admin_password: str = Field(default="admin123456", description="管理员密码")
    admin_email: str = Field(default="admin@example.com", description="管理员邮箱")
    BACKEND_CORS_ORIGINS: Annotated[List[AnyHttpUrl], NoDecode] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | List[str]) -> List[str]:
        """解析 CORS 配置：空 / 空白 → []；逗号分隔串 → 列表；已是列表则原样。"""
        if v is None or (isinstance(v, str) and (not v.strip())):
            return []
        if isinstance(v, str):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PASSWORD: str = ""
    login_throttle_window_seconds: int = 600
    login_throttle_ip_max_attempts: int = 30
    login_throttle_pair_max_failures: int = 5
    login_lock_distinct_ip_threshold: int = 3
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    AI_TASK_EVENT_FLUSH_MS: int = 300
    AI_TASK_TIME_LIMIT: int = 3600
    AI_TASK_SOFT_TIME_LIMIT: int = 3540
    AI_TASK_VISIBILITY_TIMEOUT: int = 21600
    AI_TASK_RUN_LOCK_TTL: int = 3600
    AI_TASK_ZOMBIE_TIMEOUT_S: int = 600
    AI_TASK_HEARTBEAT_S: int = 5
    AI_TASK_REAP_INTERVAL_S: int = 60
    SCHEDULED_JOB_DISPATCH_INTERVAL_S: int = 30
    AI_TASK_PENDING_ZOMBIE_S: int = 1800
    AI_TASK_EVENT_RETENTION_DAYS: int = 30
    AI_TASK_ARCHIVE_DIR: str = "archives/ai_task_events"
    AI_TASK_ARCHIVE_BATCH: int = 200
    AI_PROVIDER: str = "openai"
    AI_MODEL: str = "gpt-4o"
    AI_API_KEY: str = ""
    AI_BASE_URL: str = ""
    AI_MAX_TOKENS: int = 4096
    AI_TEMPERATURE: float = 0.7
    VECTOR_DB_URL: str = ""
    VECTOR_DIMENSION: int = 1536
    KNOWLEDGE_BASE_PATH: str = "./data/knowledge"
    KB_VECTOR_DIR: str = "./data/kb_vec"
    KB_VECTOR_CACHE_PROJECTS: int = 4
    MAX_UPLOAD_SIZE: int = 100
    UPLOAD_DIR: str = "./data/uploads"
    ALLOWED_FILE_EXTENSIONS: List[str] = [
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".pdf",
        ".doc",
        ".docx",
        ".txt",
        ".json",
        ".yaml",
        ".yml",
    ]
    AVATAR_MAX_SIZE: int = 2
    AVATAR_ALLOWED_EXTENSIONS: List[str] = [".jpg", ".jpeg", ".png", ".webp"]
    AVATAR_UPLOAD_DIR: str = "./data/uploads/avatars"
    TEST_TIMEOUT: int = 300
    MAX_CONCURRENT_TESTS: int = 10
    TEST_LOG_DIR: str = "./data/logs/tests"
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "./data/logs"
    LOG_FILE_SIZE: int = 100
    LOG_BACKUP_COUNT: int = 10
    COS_SECRET_ID: str = Field(default="", description="腾讯云 SecretId")
    COS_SECRET_KEY: str = Field(default="", description="腾讯云 SecretKey")
    COS_BUCKET: str = Field(default="", description="COS 存储桶名称")
    COS_REGION: str = Field(default="ap-guangzhou", description="COS 地域")
    COS_UPLOAD_DIR: str = Field(default="uploads/", description="COS 上传目录前缀")

    @property
    def COS_ENABLED(self) -> bool:
        """是否启用 COS 存储"""
        return bool(self.COS_SECRET_ID and self.COS_SECRET_KEY and self.COS_BUCKET)

    JIRA_URL: str = ""
    JIRA_USERNAME: str = ""
    JIRA_API_KEY: str = ""
    ZENTAO_URL: str = ""
    ZENTAO_USERNAME: str = ""
    ZENTAO_PASSWORD: str = ""
    GATEWAY_INTERNAL_KEY: str = "dev-gateway-internal-key"
    GATEWAY_INTERNAL_URL: str = "http://127.0.0.1:8889"
    APP_REPORT_DIR: str = "./data/app_reports"
    APP_REPORT_PUBLIC_BASE: str = "http://127.0.0.1:8889"
    TIMEZONE: str = "Asia/Shanghai"
    DEBUG: bool = True
    SQL_ECHO: bool = False
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    """
    获取配置单例

    使用 lru_cache 确保配置只加载一次

    Returns:
        Settings: 配置实例
    """
    return Settings()


settings = get_settings()
