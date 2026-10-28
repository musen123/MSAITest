"""知识库测试共用夹具

单元测试跑内存 sqlite（照 tests/auth/test_user_llm_config.py 先例）：
kb 模型全部用 mysql 方言类型，此处集中 shim 到 sqlite 可建表的等价类型
（仅影响 sqlite DDL 编译，不动真实 MySQL 行为）。FULLTEXT/图执行等
MySQL-only 行为放 test_isolation_mysql.py（integration 标记，直连 dev 库）。
"""

import pytest_asyncio
from sqlalchemy.dialects import mysql
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool

from app.models.auth.user_llm_config import UserLlmConfig
from app.models.knowledge.chunk import KbChunk
from app.models.knowledge.document import KbDocument
from app.models.knowledge.graph import (
    KbEntity,
    KbEntityMention,
    KbRelation,
    KbRelationMention,
)
from app.models.knowledge.knowledge_base import ProjectKnowledgeBase
from app.models.knowledge.retrieval_log import KbRetrievalLog

_SQLITE_RENDER = {
    mysql.BIGINT: "INTEGER",  # sqlite 仅 INTEGER 主键自增
    mysql.INTEGER: "INTEGER",
    mysql.TINYINT: "INTEGER",
    mysql.TEXT: "TEXT",
    mysql.LONGTEXT: "TEXT",
    mysql.MEDIUMTEXT: "TEXT",
    mysql.LONGBLOB: "BLOB",
    mysql.JSON: "TEXT",  # DDL 层面存 TEXT；SQLAlchemy JSON 绑定/解码不受影响
}

for _type, _render in _SQLITE_RENDER.items():

    @compiles(_type, "sqlite")
    def _render_mysql_type_on_sqlite(element, compiler, _r=_render, **kw):  # noqa: ANN001
        return _r


@compiles(mysql.VARCHAR, "sqlite")
def _varchar_on_sqlite(element, compiler, **kw):  # noqa: ANN001
    return f"VARCHAR({element.length})" if element.length else "VARCHAR"


@pytest_asyncio.fixture
async def db():
    """内存 sqlite 会话：建知识库检索三表 + 图谱四表 + 用户模型配置表（FK 校验
    默认关闭，跨表引用 tb_project/sys_user 无需真实存在）"""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        for table in (
            UserLlmConfig.__table__,
            ProjectKnowledgeBase.__table__,
            KbDocument.__table__,
            KbChunk.__table__,
            KbRetrievalLog.__table__,
            KbEntity.__table__,
            KbRelation.__table__,
            KbEntityMention.__table__,
            KbRelationMention.__table__,
        ):
            await conn.run_sync(lambda c, t=table: t.create(c))
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s
    await engine.dispose()


class FakeEmbeddings:
    """可配置维度的假向量客户端（计次，供缓存命中断言）"""

    calls = 0

    def __init__(self, dim: int = 64):
        self.dim = dim

    async def aembed_query(self, text: str):
        FakeEmbeddings.calls += 1
        return [0.1] * self.dim

    async def aembed_documents(self, texts):
        FakeEmbeddings.calls += 1
        return [[0.1] * self.dim for _ in texts]
