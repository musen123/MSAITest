"""TestAgent_2604 同步数据库引擎（不暴露 Base，避免循环 import）。

TestAgent_2604 用的同步 SQLAlchemy + pymysql + 自己的 Base。
当前项目是异步 SQLAlchemy + aiomysql。

为了让搬过来的模型能跑：
  - engine / SessionLocal / get_db 用项目配置（替换 +aiomysql → +pymysql）
  - Base 让模型直接继承 app.models.base.Base（两者都基于 DeclarativeBase）
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings

_sync_url = settings.DATABASE_URL.replace("+aiomysql", "+pymysql")
engine = create_engine(
    _sync_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """TestAgent 风格的依赖注入函数。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
