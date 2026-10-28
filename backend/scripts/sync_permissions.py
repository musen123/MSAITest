"""幂等增量同步权限数据（用于已上线的库）

init_db.py 的 create_permissions / create_roles 是「表里有数据就整段跳过」，
对已部署库重跑无效。本脚本可对已上线库**重复执行**，安全（只增不删，不覆盖
用户已有的角色配置）：

  1. 把 SUPPLEMENTAL_PERMISSIONS 中数据库尚缺的权限点补建；
  2. 给 super_admin 补齐「数据库里所有权限点」的分配（确保超管始终全权限）；
  3. 按映射给 admin / 项目负责人 / 测试负责人 补本次新增的权限码（幂等）。

用法（在 backend 目录下）：
    uv run python scripts/sync_permissions.py
"""

import asyncio
import os
import sys

# 让脚本能直接 `python scripts/sync_permissions.py` 运行（把 backend 加入 path）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402

from app.db.init_db import SUPPLEMENTAL_PERMISSIONS  # noqa: E402
from app.db.session import async_session_maker  # noqa: E402
from app.models.auth.permission import Permission  # noqa: E402
from app.models.auth.role import Role  # noqa: E402
from app.models.auth.role_permission import RolePermission  # noqa: E402

# 本次新增权限码 → 各系统角色的补充分配（super_admin 单独全量补，不在此表）
ROLE_GRANTS = {
    "admin": [
        "agent_experience:view", "agent_experience:manage", "system:monitor",
        "permission:view", "project:manage_member", "web_element:manage",
        "bug:assign", "bug:resolve", "bug:close",
        "scheduler:view", "scheduler:create", "scheduler:edit", "scheduler:execute",
        "environment:view", "environment:create", "environment:edit",
        "knowledge:view", "knowledge:manage",
        "chat:use", "ai_task:view", "ai_task:manage",
        "app_device:view", "app_device:control", "app_device:manage",
        "app_test:view", "app_test:create", "app_test:edit", "app_test:delete", "app_test:execute",
    ],
    "project_admin": [
        "agent_experience:view", "agent_experience:manage", "system:monitor",
        "app_device:view", "app_device:control", "app_device:manage",
        "app_test:view", "app_test:create", "app_test:edit", "app_test:delete", "app_test:execute",
    ],
    "tester": [
        "agent_experience:view", "agent_experience:manage", "system:monitor",
        "app_device:view", "app_device:control",
        "app_test:view", "app_test:create", "app_test:edit", "app_test:execute",
    ],
    "developer": [
        "agent_experience:view",
        "app_device:view",
        "app_test:view",
    ],
    "project_owner": [
        "agent_experience:view", "agent_experience:manage", "system:monitor",
        "project:manage_member", "web_element:manage",
        "bug:assign", "bug:resolve", "bug:close",
        "scheduler:view", "scheduler:create", "scheduler:edit", "scheduler:delete", "scheduler:execute",
        "environment:view", "environment:create", "environment:edit", "environment:delete",
        "knowledge:view", "knowledge:manage",
        "chat:use", "ai_task:view", "ai_task:manage",
    ],
    "project_test_lead": [
        "agent_experience:view", "agent_experience:manage", "system:monitor",
        "web_element:manage", "bug:assign", "bug:resolve", "bug:close",
        "scheduler:view", "scheduler:create", "scheduler:edit", "scheduler:execute",
        "environment:view", "environment:create", "environment:edit",
        "knowledge:view", "knowledge:manage",
        "chat:use", "ai_task:view", "ai_task:manage",
    ],
    # 普通用户：只读基线，补定时计划只读 + APP 设备/用例只读
    "user": [
        "agent_experience:view",
        "scheduler:view",
        "app_device:view",
        "app_test:view",
    ],
}


async def sync_permissions() -> None:
    async with async_session_maker() as session:
        # 1. 补建缺失的权限点
        existing_codes = {
            p.code
            for p in (await session.execute(select(Permission))).scalars().all()
        }
        new_codes = []
        for pd in SUPPLEMENTAL_PERMISSIONS:
            if pd["code"] not in existing_codes:
                session.add(Permission(**pd))
                new_codes.append(pd["code"])
        await session.flush()

        all_perms = {
            p.code: p
            for p in (await session.execute(select(Permission))).scalars().all()
        }

        async def grant(role_code: str, codes) -> int:
            role = (
                await session.execute(select(Role).where(Role.code == role_code))
            ).scalar_one_or_none()
            if not role:
                return 0
            owned = {
                rp.permission_id
                for rp in (
                    await session.execute(
                        select(RolePermission).where(
                            RolePermission.role_id == role.id
                        )
                    )
                ).scalars().all()
            }
            cnt = 0
            for code in codes:
                perm = all_perms.get(code)
                if perm and perm.id not in owned:
                    session.add(
                        RolePermission(role_id=role.id, permission_id=perm.id)
                    )
                    owned.add(perm.id)
                    cnt += 1
            return cnt

        # 2. super_admin 补齐全部权限
        sa_added = await grant("super_admin", list(all_perms.keys()))

        # 3. 其它系统角色按映射补本次新增码
        role_added = {}
        for role_code, codes in ROLE_GRANTS.items():
            role_added[role_code] = await grant(role_code, codes)

        await session.commit()

        print("=" * 52)
        print("✅ 权限同步完成（幂等，可重复执行）")
        print(f"  新增权限点 {len(new_codes)}: {new_codes or '无（已是最新）'}")
        print(f"  super_admin 补分配: {sa_added} 条")
        for rc, n in role_added.items():
            print(f"  {rc} 补分配: {n} 条")
        print("=" * 52)


if __name__ == "__main__":
    asyncio.run(sync_permissions())
