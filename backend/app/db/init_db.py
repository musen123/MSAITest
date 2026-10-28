"""
数据库初始化脚本

用于初始化数据库、表结构和种子数据
"""

import asyncio
from typing import AsyncGenerator
from pymysql import Error as PyMySQLError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.security import get_password_hash
from app.db.session import async_session_maker, engine
from app.models.auth.permission import Permission
from app.models.auth.role import Role
from app.models.auth.role_permission import RolePermission
from app.models.auth.user import User, UserStatus
from app.models.auth.user_role import UserRole
from app.models.base import Base

SUPPLEMENTAL_PERMISSIONS = [
    {
        "code": "permission:view",
        "name": "查看权限",
        "module": "权限管理",
        "sort_order": 24,
    },
    {
        "code": "permission:create",
        "name": "创建权限",
        "module": "权限管理",
        "sort_order": 25,
    },
    {
        "code": "permission:edit",
        "name": "编辑权限",
        "module": "权限管理",
        "sort_order": 26,
    },
    {
        "code": "permission:delete",
        "name": "删除权限",
        "module": "权限管理",
        "sort_order": 27,
    },
    {
        "code": "project:manage_member",
        "name": "管理项目成员",
        "module": "项目管理",
        "sort_order": 45,
    },
    {"code": "bug:assign", "name": "分配缺陷", "module": "缺陷管理", "sort_order": 75},
    {"code": "bug:resolve", "name": "解决缺陷", "module": "缺陷管理", "sort_order": 76},
    {"code": "bug:close", "name": "关闭缺陷", "module": "缺陷管理", "sort_order": 77},
    {
        "code": "report:delete",
        "name": "删除报告",
        "module": "测试报告",
        "sort_order": 83,
    },
    {
        "code": "scheduler:view",
        "name": "查看定时计划",
        "module": "定时调度",
        "sort_order": 100,
    },
    {
        "code": "scheduler:create",
        "name": "创建定时计划",
        "module": "定时调度",
        "sort_order": 101,
    },
    {
        "code": "scheduler:edit",
        "name": "编辑定时计划",
        "module": "定时调度",
        "sort_order": 102,
    },
    {
        "code": "scheduler:delete",
        "name": "删除定时计划",
        "module": "定时调度",
        "sort_order": 103,
    },
    {
        "code": "scheduler:execute",
        "name": "触发 / 启停定时计划",
        "module": "定时调度",
        "sort_order": 104,
    },
    {
        "code": "environment:view",
        "name": "查看测试环境",
        "module": "测试环境",
        "sort_order": 110,
    },
    {
        "code": "environment:create",
        "name": "创建测试环境",
        "module": "测试环境",
        "sort_order": 111,
    },
    {
        "code": "environment:edit",
        "name": "编辑测试环境",
        "module": "测试环境",
        "sort_order": 112,
    },
    {
        "code": "environment:delete",
        "name": "删除测试环境",
        "module": "测试环境",
        "sort_order": 113,
    },
    {
        "code": "knowledge:view",
        "name": "查看知识库",
        "module": "知识库",
        "sort_order": 120,
    },
    {
        "code": "knowledge:manage",
        "name": "管理知识库",
        "module": "知识库",
        "sort_order": 121,
    },
    {
        "code": "chat:use",
        "name": "使用 AI 助手",
        "module": "AI 助手",
        "sort_order": 130,
    },
    {
        "code": "ai_task:view",
        "name": "查看 AI 任务",
        "module": "AI 任务",
        "sort_order": 140,
    },
    {
        "code": "ai_task:manage",
        "name": "管理 AI 任务",
        "module": "AI 任务",
        "sort_order": 141,
    },
    {
        "code": "app_device:view",
        "name": "查看设备/执行机",
        "module": "APP自动化",
        "sort_order": 160,
    },
    {
        "code": "app_device:control",
        "name": "占用与控制设备",
        "module": "APP自动化",
        "sort_order": 161,
    },
    {
        "code": "app_device:manage",
        "name": "执行机注册/轮转/强制释放",
        "module": "APP自动化",
        "sort_order": 162,
    },
    {
        "code": "app_test:view",
        "name": "查看 App 用例/执行",
        "module": "APP自动化",
        "sort_order": 163,
    },
    {
        "code": "app_test:create",
        "name": "创建 App 用例（录制沉淀）",
        "module": "APP自动化",
        "sort_order": 164,
    },
    {
        "code": "app_test:edit",
        "name": "编辑 App 用例",
        "module": "APP自动化",
        "sort_order": 165,
    },
    {
        "code": "app_test:delete",
        "name": "删除 App 用例",
        "module": "APP自动化",
        "sort_order": 166,
    },
    {
        "code": "app_test:execute",
        "name": "回放 App 用例",
        "module": "APP自动化",
        "sort_order": 167,
    },
    {
        "code": "test_data:view",
        "name": "查看测试数据（数据集/文件资产）",
        "module": "测试数据",
        "sort_order": 170,
    },
    {
        "code": "test_data:create",
        "name": "创建测试数据（含 AI 造数）",
        "module": "测试数据",
        "sort_order": 171,
    },
    {
        "code": "test_data:edit",
        "name": "编辑测试数据",
        "module": "测试数据",
        "sort_order": 172,
    },
    {
        "code": "test_data:delete",
        "name": "删除测试数据",
        "module": "测试数据",
        "sort_order": 173,
    },
    {
        "code": "system:monitor",
        "name": "查看 Worker/队列监控",
        "module": "系统监控",
        "sort_order": 190,
    },
]
_BASE_AUTH = ["auth:login", "auth:logout"]
SYSTEM_ROLE_DEFINITIONS = [
    {
        "code": "admin",
        "name": "系统管理员",
        "description": "平台与人员管理 + 全部测试能力兜底；不含底层权限点增改删与系统配置（保留给超级管理员）",
        "sort_order": 2,
        "permission_codes": _BASE_AUTH
        + [
            "user:view",
            "user:create",
            "user:edit",
            "user:delete",
            "user:reset_pwd",
            "role:view",
            "role:create",
            "role:edit",
            "role:delete",
            "permission:view",
            "project:view",
            "project:create",
            "project:edit",
            "project:delete",
            "project:archive",
            "project:manage_member",
            "member:view",
            "member:add",
            "member:remove",
            "member:edit_role",
            "module:view",
            "module:add",
            "module:edit",
            "module:delete",
            "config:view",
            "config:edit",
            "test_case:view",
            "test_case:create",
            "test_case:edit",
            "test_case:delete",
            "test_case:execute",
            "bug:view",
            "bug:create",
            "bug:edit",
            "bug:delete",
            "bug:edit_own",
            "bug:assign",
            "bug:resolve",
            "bug:close",
            "report:view",
            "report:create",
            "report:export",
            "report:delete",
            "scheduler:view",
            "scheduler:create",
            "scheduler:edit",
            "scheduler:delete",
            "scheduler:execute",
            "environment:view",
            "environment:create",
            "environment:edit",
            "environment:delete",
            "knowledge:view",
            "knowledge:manage",
            "chat:use",
            "ai_task:view",
            "ai_task:manage",
            "system:log",
            "system:monitor",
            "app_device:view",
            "app_device:control",
            "app_device:manage",
            "app_test:view",
            "app_test:create",
            "app_test:edit",
            "app_test:delete",
            "app_test:execute",
            "test_data:view",
            "test_data:create",
            "test_data:edit",
            "test_data:delete",
        ],
    },
    {
        "code": "project_admin",
        "name": "项目管理员",
        "description": "运营测试项目（测试经理 / 项目负责人）：项目、成员、测试资产、缺陷、调度、环境、知识库全量；不含用户/角色/权限/系统管理",
        "sort_order": 3,
        "permission_codes": _BASE_AUTH
        + [
            "project:view",
            "project:create",
            "project:edit",
            "project:delete",
            "project:archive",
            "project:manage_member",
            "member:view",
            "member:add",
            "member:remove",
            "member:edit_role",
            "module:view",
            "module:add",
            "module:edit",
            "module:delete",
            "config:view",
            "config:edit",
            "test_case:view",
            "test_case:create",
            "test_case:edit",
            "test_case:delete",
            "test_case:execute",
            "bug:view",
            "bug:create",
            "bug:edit",
            "bug:delete",
            "bug:edit_own",
            "bug:assign",
            "bug:resolve",
            "bug:close",
            "report:view",
            "report:create",
            "report:export",
            "report:delete",
            "scheduler:view",
            "scheduler:create",
            "scheduler:edit",
            "scheduler:delete",
            "scheduler:execute",
            "environment:view",
            "environment:create",
            "environment:edit",
            "environment:delete",
            "knowledge:view",
            "knowledge:manage",
            "chat:use",
            "ai_task:view",
            "ai_task:manage",
            "app_device:view",
            "app_device:control",
            "app_device:manage",
            "app_test:view",
            "app_test:create",
            "app_test:edit",
            "app_test:delete",
            "app_test:execute",
            "test_data:view",
            "test_data:create",
            "test_data:edit",
            "test_data:delete",
        ],
    },
    {
        "code": "tester",
        "name": "测试工程师",
        "description": "一线测试：用例查看/新建/编辑/执行（不含删除）、报缺陷、报告导出、调度增改执、AI 用例生成；不含项目管理与删除类操作",
        "sort_order": 4,
        "permission_codes": _BASE_AUTH
        + [
            "project:view",
            "member:view",
            "module:view",
            "config:view",
            "test_case:view",
            "test_case:create",
            "test_case:edit",
            "test_case:execute",
            "bug:view",
            "bug:create",
            "bug:edit_own",
            "bug:assign",
            "report:view",
            "report:create",
            "report:export",
            "scheduler:view",
            "scheduler:create",
            "scheduler:edit",
            "scheduler:execute",
            "environment:view",
            "knowledge:view",
            "chat:use",
            "ai_task:view",
            "ai_task:manage",
            "app_device:view",
            "app_device:control",
            "app_test:view",
            "app_test:create",
            "app_test:edit",
            "app_test:execute",
            "test_data:view",
            "test_data:create",
            "test_data:edit",
        ],
    },
    {
        "code": "developer",
        "name": "开发工程师",
        "description": "研发侧：查看测试资产与缺陷、提交缺陷、处理(resolve)指派给自己的缺陷、查看报告、使用 AI 助手；不执行测试、不参与项目管理",
        "sort_order": 5,
        "permission_codes": _BASE_AUTH
        + [
            "project:view",
            "member:view",
            "module:view",
            "test_case:view",
            "bug:view",
            "bug:create",
            "bug:edit_own",
            "bug:resolve",
            "report:view",
            "knowledge:view",
            "chat:use",
            "ai_task:view",
            "app_device:view",
            "app_test:view",
        ],
    },
    {
        "code": "user",
        "name": "普通用户",
        "description": "自助注册默认角色 / 只读基线：全模块只读 + 提交缺陷 + 使用 AI 助手；无任何创建/编辑/执行权限（执行测试需测试工程师及以上）",
        "sort_order": 6,
        "permission_codes": _BASE_AUTH
        + [
            "project:view",
            "test_case:view",
            "bug:view",
            "bug:create",
            "report:view",
            "scheduler:view",
            "environment:view",
            "knowledge:view",
            "chat:use",
            "ai_task:view",
            "app_device:view",
            "app_test:view",
        ],
    },
]


async def create_database_if_not_exists() -> None:
    """
    创建数据库（如果不存在）

    使用 MySQL root 连接创建数据库
    """
    base_url = f"mysql+aiomysql://{settings.db_user}:{settings.db_password}@{settings.db_host}:{settings.db_port}"
    from sqlalchemy.ext.asyncio import create_async_engine

    base_engine = create_async_engine(base_url, echo=False)
    try:
        async with base_engine.connect() as conn:
            result = await conn.execute(
                text(
                    f"SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = '{settings.database}'"
                )
            )
            exists = result.first() is not None
            if not exists:
                await conn.execute(
                    text(
                        f"CREATE DATABASE `{settings.database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                    )
                )
                await conn.commit()
                print(f"✅ 数据库 '{settings.database}' 创建成功")
            else:
                print(f"ℹ️  数据库 '{settings.database}' 已存在")
    except PyMySQLError as e:
        print(f"❌ 创建数据库失败: {e}")
        raise
    finally:
        await base_engine.dispose()


async def init_tables() -> None:
    """
    初始化数据库表

    创建所有表结构
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ 数据库表创建完成")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话

    Yields:
        AsyncSession: 数据库会话
    """
    async with async_session_maker() as session:
        yield session


async def create_permissions() -> None:
    """
    创建系统权限数据

    初始化所有模块的权限定义
    """
    async with async_session_maker() as session:
        result = await session.execute(select(Permission).limit(1))
        if result.scalar_one_or_none():
            print("ℹ️  权限数据已存在，跳过创建")
            return
        permissions_data = [
            {
                "code": "auth:login",
                "name": "登录",
                "module": "认证授权",
                "sort_order": 1,
            },
            {
                "code": "auth:register",
                "name": "注册",
                "module": "认证授权",
                "sort_order": 2,
            },
            {
                "code": "auth:logout",
                "name": "登出",
                "module": "认证授权",
                "sort_order": 3,
            },
            {
                "code": "user:view",
                "name": "查看用户",
                "module": "用户管理",
                "sort_order": 10,
            },
            {
                "code": "user:create",
                "name": "创建用户",
                "module": "用户管理",
                "sort_order": 11,
            },
            {
                "code": "user:edit",
                "name": "编辑用户",
                "module": "用户管理",
                "sort_order": 12,
            },
            {
                "code": "user:delete",
                "name": "删除用户",
                "module": "用户管理",
                "sort_order": 13,
            },
            {
                "code": "user:reset_pwd",
                "name": "重置密码",
                "module": "用户管理",
                "sort_order": 14,
            },
            {
                "code": "role:view",
                "name": "查看角色",
                "module": "角色管理",
                "sort_order": 20,
            },
            {
                "code": "role:create",
                "name": "创建角色",
                "module": "角色管理",
                "sort_order": 21,
            },
            {
                "code": "role:edit",
                "name": "编辑角色",
                "module": "角色管理",
                "sort_order": 22,
            },
            {
                "code": "role:delete",
                "name": "删除角色",
                "module": "角色管理",
                "sort_order": 23,
            },
            {
                "code": "project:view",
                "name": "查看项目",
                "module": "项目管理",
                "sort_order": 30,
            },
            {
                "code": "project:create",
                "name": "创建项目",
                "module": "项目管理",
                "sort_order": 31,
            },
            {
                "code": "project:edit",
                "name": "编辑项目",
                "module": "项目管理",
                "sort_order": 32,
            },
            {
                "code": "project:delete",
                "name": "删除项目",
                "module": "项目管理",
                "sort_order": 33,
            },
            {
                "code": "test_case:view",
                "name": "查看测试用例",
                "module": "功能测试",
                "sort_order": 40,
            },
            {
                "code": "test_case:create",
                "name": "创建测试用例",
                "module": "功能测试",
                "sort_order": 41,
            },
            {
                "code": "test_case:edit",
                "name": "编辑测试用例",
                "module": "功能测试",
                "sort_order": 42,
            },
            {
                "code": "test_case:delete",
                "name": "删除测试用例",
                "module": "功能测试",
                "sort_order": 43,
            },
            {
                "code": "test_case:execute",
                "name": "执行测试用例",
                "module": "功能测试",
                "sort_order": 44,
            },
            {
                "code": "bug:view",
                "name": "查看缺陷",
                "module": "缺陷管理",
                "sort_order": 70,
            },
            {
                "code": "bug:create",
                "name": "创建缺陷",
                "module": "缺陷管理",
                "sort_order": 71,
            },
            {
                "code": "bug:edit",
                "name": "编辑缺陷",
                "module": "缺陷管理",
                "sort_order": 72,
            },
            {
                "code": "bug:delete",
                "name": "删除缺陷",
                "module": "缺陷管理",
                "sort_order": 73,
            },
            {
                "code": "report:view",
                "name": "查看报告",
                "module": "测试报告",
                "sort_order": 80,
            },
            {
                "code": "report:create",
                "name": "创建报告",
                "module": "测试报告",
                "sort_order": 81,
            },
            {
                "code": "report:export",
                "name": "导出报告",
                "module": "测试报告",
                "sort_order": 82,
            },
            {
                "code": "project:archive",
                "name": "归档项目",
                "module": "项目管理",
                "sort_order": 34,
            },
            {
                "code": "member:view",
                "name": "查看成员",
                "module": "项目管理",
                "sort_order": 35,
            },
            {
                "code": "member:add",
                "name": "添加成员",
                "module": "项目管理",
                "sort_order": 36,
            },
            {
                "code": "member:remove",
                "name": "移除成员",
                "module": "项目管理",
                "sort_order": 37,
            },
            {
                "code": "member:edit_role",
                "name": "修改成员角色",
                "module": "项目管理",
                "sort_order": 38,
            },
            {
                "code": "module:view",
                "name": "查看模块",
                "module": "项目管理",
                "sort_order": 39,
            },
            {
                "code": "module:add",
                "name": "添加模块",
                "module": "项目管理",
                "sort_order": 40,
            },
            {
                "code": "module:edit",
                "name": "编辑模块",
                "module": "项目管理",
                "sort_order": 41,
            },
            {
                "code": "module:delete",
                "name": "删除模块",
                "module": "项目管理",
                "sort_order": 42,
            },
            {
                "code": "config:view",
                "name": "查看项目配置",
                "module": "项目管理",
                "sort_order": 43,
            },
            {
                "code": "config:edit",
                "name": "编辑项目配置",
                "module": "项目管理",
                "sort_order": 44,
            },
            {
                "code": "bug:edit_own",
                "name": "编辑自己提交的缺陷",
                "module": "缺陷管理",
                "sort_order": 74,
            },
            {
                "code": "system:config",
                "name": "系统配置",
                "module": "系统管理",
                "sort_order": 90,
            },
            {
                "code": "system:log",
                "name": "查看日志",
                "module": "系统管理",
                "sort_order": 91,
            },
        ] + SUPPLEMENTAL_PERMISSIONS
        for perm_data in permissions_data:
            permission = Permission(**perm_data)
            session.add(permission)
        await session.commit()
        print(f"✅ 创建了 {len(permissions_data)} 条权限数据")


async def create_roles() -> None:
    """
    创建系统角色数据（单层全局 RBAC）

    角色集合(单一事实来源见 SYSTEM_ROLE_DEFINITIONS)：
      super_admin 超级管理员 / admin 系统管理员 / project_admin 项目管理员
      / tester 测试工程师 / user 普通用户(自助注册默认)
    """
    async with async_session_maker() as session:
        result = await session.execute(select(Role).limit(1))
        if result.scalar_one_or_none():
            print("ℹ️  角色数据已存在，跳过创建")
            return
        permissions_result = await session.execute(select(Permission))
        all_permissions = permissions_result.scalars().all()
        perm_by_code = {p.code: p for p in all_permissions}
        super_admin_role = Role(
            code="super_admin",
            name="超级管理员",
            description="拥有系统所有权限",
            is_system=True,
            sort_order=1,
        )
        session.add(super_admin_role)
        await session.flush()
        for permission in all_permissions:
            session.add(
                RolePermission(role_id=super_admin_role.id, permission_id=permission.id)
            )
        for role_def in SYSTEM_ROLE_DEFINITIONS:
            role = Role(
                code=role_def["code"],
                name=role_def["name"],
                description=role_def["description"],
                is_system=True,
                sort_order=role_def["sort_order"],
            )
            session.add(role)
            await session.flush()
            for code in role_def["permission_codes"]:
                perm = perm_by_code.get(code)
                if perm:
                    session.add(RolePermission(role_id=role.id, permission_id=perm.id))
        await session.commit()
        role_names = "超级管理员、" + "、".join(
            (r["name"] for r in SYSTEM_ROLE_DEFINITIONS)
        )
        print(
            f"✅ 创建了 {len(SYSTEM_ROLE_DEFINITIONS) + 1} 个系统角色（{role_names}）"
        )


async def create_project_roles() -> None:
    """
    创建项目角色数据（负责人、测试负责人、开发、测试、查看者）

    ⚠ 单层全局 RBAC 下，这些项目角色**仅作项目成员标签**：require_permission 只校验
    系统角色权限，不读取项目角色权限分配。项目层只有两点真正生效——「是否成员」
    （二元访问门禁）与「是否 OWNER=project_owner」（可管成员/配置/删项目）。
    下方 permission_codes 不参与任何鉴权判定，保留仅为兼容与展示；真正的能力边界由
    用户的**系统角色**(SYSTEM_ROLE_DEFINITIONS)决定。
    """
    async with async_session_maker() as session:
        result = await session.execute(
            select(Role).where(Role.code == "project_owner").limit(1)
        )
        if result.scalar_one_or_none():
            print("ℹ️  项目角色数据已存在，跳过创建")
            return
        perms_result = await session.execute(select(Permission))
        all_permissions = {p.code: p for p in perms_result.scalars().all()}
        project_roles_data = [
            {
                "code": "project_owner",
                "name": "项目负责人",
                "description": "项目负责人，拥有项目的所有管理权限",
                "is_system": True,
                "sort_order": 10,
                "permission_codes": [
                    "auth:login",
                    "auth:logout",
                    "project:view",
                    "project:create",
                    "project:edit",
                    "project:delete",
                    "project:archive",
                    "member:view",
                    "member:add",
                    "member:remove",
                    "member:edit_role",
                    "module:view",
                    "module:add",
                    "module:edit",
                    "module:delete",
                    "config:view",
                    "config:edit",
                    "project:manage_member",
                    "test_case:view",
                    "test_case:create",
                    "test_case:edit",
                    "test_case:delete",
                    "test_case:execute",
                    "bug:view",
                    "bug:create",
                    "bug:edit",
                    "bug:delete",
                    "bug:edit_own",
                    "bug:assign",
                    "bug:resolve",
                    "bug:close",
                    "report:view",
                    "report:create",
                    "report:export",
                    "scheduler:view",
                    "scheduler:create",
                    "scheduler:edit",
                    "scheduler:delete",
                    "scheduler:execute",
                    "environment:view",
                    "environment:create",
                    "environment:edit",
                    "environment:delete",
                    "knowledge:view",
                    "knowledge:manage",
                    "chat:use",
                    "ai_task:view",
                    "ai_task:manage",
                ],
            },
            {
                "code": "project_member",
                "name": "项目成员",
                "description": "项目成员（组织标签，不单独控权；成员的实际操作权限由其系统角色决定）",
                "is_system": True,
                "sort_order": 11,
                "permission_codes": [
                    "auth:login",
                    "auth:logout",
                    "project:view",
                    "member:view",
                    "module:view",
                ],
            },
        ]
        for role_data in project_roles_data:
            permission_codes = role_data.pop("permission_codes")
            role = Role(**role_data)
            session.add(role)
            await session.flush()
            for code in permission_codes:
                perm = all_permissions.get(code)
                if perm:
                    session.add(RolePermission(role_id=role.id, permission_id=perm.id))
        await session.commit()
        print(f"✅ 创建了 {len(project_roles_data)} 个项目角色（含权限分配）")


async def create_admin_user() -> None:
    """
    创建管理员账号

    从配置文件读取管理员信息并创建
    """
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.username == settings.admin_username)
        )
        if result.scalar_one_or_none():
            print(f"ℹ️  管理员账号 '{settings.admin_username}' 已存在，跳过创建")
            return
        super_admin_role = await session.execute(
            select(Role).where(Role.code == "super_admin")
        )
        super_admin = super_admin_role.scalar_one()
        admin_user = User(
            username=settings.admin_username,
            password_hash=get_password_hash(settings.admin_password),
            email=settings.admin_email,
            real_name="系统管理员",
            status=UserStatus.ACTIVE,
        )
        session.add(admin_user)
        await session.flush()
        user_role = UserRole(user_id=admin_user.id, role_id=super_admin.id)
        session.add(user_role)
        await session.commit()
        print(f"✅ 创建管理员账号: {settings.admin_username}")


async def main() -> None:
    """
    主函数

    执行完整的数据库初始化流程
    """
    print("=" * 60)
    print("🚀 开始初始化数据库...")
    print("=" * 60)
    try:
        print("\n📝 步骤 1/5: 创建数据库")
        await create_database_if_not_exists()
        print("\n📝 步骤 2/5: 创建表结构")
        await init_tables()
        print("\n📝 步骤 3/5: 初始化权限数据")
        await create_permissions()
        print("\n📝 步骤 4/6: 初始化角色数据")
        await create_roles()
        print("\n📝 步骤 5/6: 初始化项目角色数据")
        await create_project_roles()
        print("\n📝 步骤 6/6: 创建管理员账号")
        await create_admin_user()
        print("\n" + "=" * 60)
        print("✅ 数据库初始化完成！")
        print("=" * 60)
        print("\n📌 管理员账号信息:")
        print(f"   用户名: {settings.admin_username}")
        print(f"   密码: {settings.admin_password}")
        print(f"   邮箱: {settings.admin_email}")
        print("\n⚠️  请在生产环境中修改默认密码！")
    except Exception as e:
        print(f"\n❌ 数据库初始化失败: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
