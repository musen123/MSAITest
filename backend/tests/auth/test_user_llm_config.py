"""用户大模型配置 CRUD 不变量测试（每类型多配置 + 默认模式）

核心保证：同一 (user_id, model_type) 恰好一个 is_default；首条自动默认；
set_default 切换唯一；删默认自动顺位；get_by_id 带 user_id 防越权(IDOR)。

用内存 sqlite 自建该表跑（with_for_update 在 sqlite 上被忽略，不影响逻辑）。
"""

import pytest_asyncio
from sqlalchemy.dialects.mysql import BIGINT as MySQLBIGINT
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool

from app.crud.auth.user_llm_config import crud_user_llm_config as crud
from app.models.auth.user_llm_config import ModelType, UserLlmConfig


# SQLite 只对声明为 INTEGER 的主键自增；把 mysql BIGINT 在 sqlite 下渲染成 INTEGER，
# 让自增主键正常工作（仅影响 sqlite 方言编译，不动真实 MySQL 行为）。
@compiles(MySQLBIGINT, "sqlite")
def _bigint_as_integer_on_sqlite(element, compiler, **kw):  # noqa: ANN001
    return "INTEGER"


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: UserLlmConfig.__table__.create(c))
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s
    await engine.dispose()


async def _mk(db, *, user_id=1, mt=ModelType.TEXT, name="c", make_default=False):
    return await crud.create(
        db, user_id=user_id, model_type=mt, provider="openai",
        model="m", api_key="k", name=name, make_default=make_default,
    )


async def _defaults(db, *, user_id=1, mt=ModelType.TEXT):
    rows = await crud.list_by_user_and_type(db, user_id=user_id, model_type=mt)
    return [r for r in rows if r.is_default]


class TestDefaultInvariant:
    async def test_first_config_auto_default(self, db):
        a = await _mk(db, name="A")
        assert a.is_default is True
        got = await crud.get_default(db, user_id=1, model_type=ModelType.TEXT)
        assert got.id == a.id

    async def test_second_config_not_default(self, db):
        a = await _mk(db, name="A")
        b = await _mk(db, name="B")
        assert a.is_default is True and b.is_default is False
        assert len(await _defaults(db)) == 1

    async def test_make_default_on_create_steals(self, db):
        a = await _mk(db, name="A")
        b = await _mk(db, name="B", make_default=True)
        # 重新读 A
        a2 = await crud.get_by_id(db, config_id=a.id, user_id=1)
        assert b.is_default is True and a2.is_default is False
        assert len(await _defaults(db)) == 1


class TestSetDefault:
    async def test_set_default_switches_uniquely(self, db):
        a = await _mk(db, name="A")
        b = await _mk(db, name="B")
        c = await _mk(db, name="C")
        await crud.set_default(db, config_id=c.id, user_id=1)
        defs = await _defaults(db)
        assert len(defs) == 1 and defs[0].id == c.id

    async def test_set_default_reactivates(self, db):
        a = await _mk(db, name="A")
        b = await _mk(db, name="B")
        # 停用 B 再设默认，应被重新激活，避免"默认却停用"死状态
        b.is_active = False
        await db.commit()
        await crud.set_default(db, config_id=b.id, user_id=1)
        b2 = await crud.get_by_id(db, config_id=b.id, user_id=1)
        assert b2.is_default is True and b2.is_active is True


class TestDelete:
    async def test_delete_default_auto_promotes_earliest(self, db):
        a = await _mk(db, name="A")  # 默认
        b = await _mk(db, name="B")
        c = await _mk(db, name="C")
        await crud.delete_by_id(db, config_id=a.id, user_id=1)
        defs = await _defaults(db)
        assert len(defs) == 1 and defs[0].id == b.id  # 顺位提升最早一条

    async def test_delete_nondefault_keeps_default(self, db):
        a = await _mk(db, name="A")  # 默认
        b = await _mk(db, name="B")
        await crud.delete_by_id(db, config_id=b.id, user_id=1)
        defs = await _defaults(db)
        assert len(defs) == 1 and defs[0].id == a.id

    async def test_delete_last_leaves_none(self, db):
        a = await _mk(db, name="A")
        await crud.delete_by_id(db, config_id=a.id, user_id=1)
        assert await crud.get_default(db, user_id=1, model_type=ModelType.TEXT) is None


class TestIsolationAndIdor:
    async def test_get_by_id_rejects_other_user(self, db):
        a = await _mk(db, user_id=1, name="A")
        assert await crud.get_by_id(db, config_id=a.id, user_id=2) is None
        assert (await crud.get_by_id(db, config_id=a.id, user_id=1)).id == a.id

    async def test_default_isolated_by_type(self, db):
        t = await _mk(db, mt=ModelType.TEXT, name="T")
        e = await _mk(db, mt=ModelType.EMBED, name="E")
        # 两个类型各自的首条都是默认，互不干扰
        assert t.is_default and e.is_default
        assert (await crud.get_default(db, user_id=1, model_type=ModelType.TEXT)).id == t.id
        assert (await crud.get_default(db, user_id=1, model_type=ModelType.EMBED)).id == e.id

    async def test_delete_rejects_other_user(self, db):
        a = await _mk(db, user_id=1, name="A")
        assert await crud.delete_by_id(db, config_id=a.id, user_id=2) is False
        # 仍在
        assert await crud.get_by_id(db, config_id=a.id, user_id=1) is not None
