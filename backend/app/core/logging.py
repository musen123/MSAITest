"""
日志集中初始化

项目唯一的 logging 入口。读取 settings 中的 LOG_LEVEL/LOG_DIR/LOG_FILE_SIZE/LOG_BACKUP_COUNT，
通过 logging.config.dictConfig 统一配置：
  - 控制台 StreamHandler（stdout）
  - 滚动文件 RotatingFileHandler
  - 接管 uvicorn / fastapi / sqlalchemy 命名空间，让它们的输出也走我们的 handlers

启动顺序：main.py 的 lifespan 中应**先**调用本模块的 setup_logging()，再做其他初始化。
"""

import logging
import logging.config
import sys
from pathlib import Path

from app.core.config import settings

# 统一日志格式
_LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 需要接管的第三方 logger 命名空间（让它们走我们的 handlers）
# 注：sqlalchemy.* 提到 WARNING，避免每条 SQL 都打到日志（即使 SQL_ECHO 偶发开启也兜底）
_EXTERNAL_LOGGERS = (
    "uvicorn",
    "uvicorn.error",
    "uvicorn.access",
    "fastapi",
)
# SQLAlchemy 单独配 WARNING 级别
_SQLALCHEMY_LOGGERS = (
    "sqlalchemy",
    "sqlalchemy.engine",
    "sqlalchemy.engine.Engine",
    "sqlalchemy.pool",
    "sqlalchemy.dialects",
)


def setup_logging() -> None:
    """
    初始化全局日志配置

    - 创建日志目录（不存在则自动创建）
    - 配置 root logger：控制台 + 滚动文件双 handler
    - 接管 uvicorn / fastapi / sqlalchemy 命名空间
    - 保留已有 logger 的 handler（即 case_result.py 中手动加的 StreamHandler），
      避免与全局配置冲突
    """
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    # 文件大小从 MB 换算成字节
    max_bytes = settings.LOG_FILE_SIZE * 1024 * 1024

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": _LOG_FORMAT,
                "datefmt": _DATE_FORMAT,
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": sys.stdout,
                "level": settings.LOG_LEVEL,
                "formatter": "default",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(log_file),
                "maxBytes": max_bytes,
                "backupCount": settings.LOG_BACKUP_COUNT,
                "encoding": "utf-8",
                "level": settings.LOG_LEVEL,
                "formatter": "default",
            },
        },
        "loggers": {
            # root logger —— 不显式设 level，使用下面 default 行为（WARNING），
            # 但所有具体业务 logger 走各自显式 level
            "": {
                "handlers": ["console", "file"],
                "level": "WARNING",
                "propagate": False,
            },
            # 接管 uvicorn / fastapi —— 显式设 INFO 级别
            **{name: {"level": "INFO", "handlers": ["console", "file"], "propagate": False} for name in _EXTERNAL_LOGGERS},
            # 接管 sqlalchemy —— 显式设 WARNING 级别（屏蔽每条 SQL 的 INFO 输出）
            **{name: {"level": "WARNING", "handlers": ["console", "file"], "propagate": False} for name in _SQLALCHEMY_LOGGERS},
            # 项目业务 logger —— 显式设 INFO 级别，让我们的访问日志能正常输出
            "app.core.middleware": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "propagate": False,
            },
        },
    }

    logging.config.dictConfig(config)
