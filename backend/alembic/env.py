"""
Alembic environment configuration

Support async database and auto migration generation
"""

import asyncio
from logging.config import fileConfig
from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config, AsyncEngine
from app.core.config import settings
from app.core.base import Base
from app.models.auth.permission import Permission
from app.models.auth.role import Role
from app.models.auth.role_permission import RolePermission
from app.models.auth.user import User
from app.models.auth.user_role import UserRole
from app.models.auth.user_token import UserToken
from app.models.project.config import ProjectConfig
from app.models.project.member import ProjectMember
from app.models.project.module import ProjectModule
from app.models.project.project import Project
from app.models.scheduler.scheduled_job import ScheduledJob, ScheduledJobRun
from app.models.test_environment.database import DatabaseConnection
from app.models.test_environment.environment import TestEnvironment
from app.models.test_environment.function import GlobalFunction
from app.models.test_environment.variable import EnvironmentVariable
from app.models.func_test.case_execution import FuncCaseExecution
from app.models.func_test.document import ProjectDocument
from app.models.func_test.requirement import TestRequirement
from app.models.func_test.test_case import FuncTestCase
from app.models.knowledge.chunk import KbChunk
from app.models.knowledge.retrieval_log import KbRetrievalLog
from app.models.knowledge.document import KbDocument
from app.models.knowledge.knowledge_base import ProjectKnowledgeBase
from app.models.chat.conversation import Conversation, Message
from app.models.test_data.dataset import TestDataset
from app.models.test_data.file_asset import TestFileAsset

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def get_engine() -> AsyncEngine:
    """
    Create async engine for Alembic migrations

    Returns:
        AsyncEngine: Async database engine
    """
    return async_engine_from_config(
        {"sqlalchemy.url": settings.DATABASE_URL},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """
    Execute actual migration operations

    Args:
        connection: Database connection
    """
    context.configure(
        connection=connection, target_metadata=target_metadata, render_as_batch=True
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations in async mode

    This scenario requires an Engine
    and associate a connection with the context.
    """
    connectable = get_engine()
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
