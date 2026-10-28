"""文件资产 CRUD：${{file:资产名}} 渲染期解析 + 原始文件名兜底匹配。

根因回归（exec#73 NoSuchKey）：脚本用 ${{file:product_main.png}}（原始文件名）引用，
但资产的引用键是 name 字段（商品主图，人工/AI 起的显示名）——get_by_name 未命中，
占位符原样保留 → 当成 storage_key 直传 COS → 404。get_by_file_name 按原始文件名
兜底找回同一份资产（项目内该文件名唯一时）。
"""

import pytest_asyncio
from sqlalchemy.dialects.mysql import BIGINT as MySQLBIGINT
from sqlalchemy.dialects.mysql import INTEGER as MySQLINTEGER
from sqlalchemy.dialects.mysql import JSON as MySQLJSON
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool

from app.crud.test_data.file_asset import crud_test_file_asset
from app.models.test_data.file_asset import TestFileAsset


@compiles(MySQLBIGINT, "sqlite")
def _bigint_sqlite(element, compiler, **kw):  # noqa: ANN001
    return "INTEGER"


@compiles(MySQLINTEGER, "sqlite")
def _int_sqlite(element, compiler, **kw):  # noqa: ANN001
    return "INTEGER"


@compiles(MySQLJSON, "sqlite")
def _json_sqlite(element, compiler, **kw):  # noqa: ANN001
    return "JSON"


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: TestFileAsset.__table__.create(c))
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s
    await engine.dispose()


async def _seed(db, **overrides):
    defaults = dict(
        project_id=2, name="商品主图", file_name="product_main.png",
        storage_key="test_data/2/real-key.png", mime="image/png", source="manual",
    )
    defaults.update(overrides)
    obj = TestFileAsset(**defaults)
    db.add(obj)
    await db.commit()
    return obj


class TestGetByName:
    async def test_exact_name_match(self, db):
        await _seed(db)
        got = await crud_test_file_asset.get_by_name(db, project_id=2, name="商品主图")
        assert got is not None and got.storage_key == "test_data/2/real-key.png"

    async def test_no_match(self, db):
        await _seed(db)
        assert await crud_test_file_asset.get_by_name(db, project_id=2, name="不存在") is None


class TestGetByFileNameFallback:
    async def test_unique_file_name_resolves(self, db):
        # 脚本用了原始文件名而非资产名（本次线上根因）——按文件名唯一命中同一份资产
        await _seed(db)
        got = await crud_test_file_asset.get_by_file_name(
            db, project_id=2, file_name="product_main.png"
        )
        assert got is not None and got.name == "商品主图"
        assert got.storage_key == "test_data/2/real-key.png"

    async def test_ambiguous_file_name_returns_none(self, db):
        # 两份资产原始文件名相同（分两次各自上传的同名图）→ 不猜，交回调用方按未命中处理
        await _seed(db, name="资产A", storage_key="k/a.png")
        await _seed(db, name="资产B", storage_key="k/b.png")
        got = await crud_test_file_asset.get_by_file_name(
            db, project_id=2, file_name="product_main.png"
        )
        assert got is None

    async def test_project_isolated(self, db):
        await _seed(db, project_id=1)
        got = await crud_test_file_asset.get_by_file_name(
            db, project_id=2, file_name="product_main.png"
        )
        assert got is None

    async def test_soft_deleted_excluded(self, db):
        from datetime import datetime

        await _seed(db, deleted_at=datetime.utcnow())
        got = await crud_test_file_asset.get_by_file_name(
            db, project_id=2, file_name="product_main.png"
        )
        assert got is None

    async def test_no_match_returns_none(self, db):
        await _seed(db)
        got = await crud_test_file_asset.get_by_file_name(
            db, project_id=2, file_name="nope.png"
        )
        assert got is None
