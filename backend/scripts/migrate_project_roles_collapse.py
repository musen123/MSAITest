"""项目角色收口迁移：把 5 个项目角色收成「负责人 + 成员」两种。

单层 RBAC 下项目角色仅作组织标签,test_lead/developer/tester/viewer 功能等价,
现统一收成 project_member。本脚本对**已上线库**幂等执行:

  1. 确保 project_member(项目成员)角色存在(缺则补建);
  2. 把现有成员中 project_role 属于 test_lead/developer/tester/viewer 的,
     改挂到 project_member;
  3. 删除这 4 个废弃项目角色及其权限分配(project_owner 保留)。

顺序保证不触发外键约束:先改成员引用 → 再删角色权限 → 最后删角色。

用法(backend 目录下):
    uv run python scripts/migrate_project_roles_collapse.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete, select, update  # noqa: E402

from app.db.session import async_session_maker, engine  # noqa: E402
from app.models.auth.role import Role  # noqa: E402
from app.models.auth.role_permission import RolePermission  # noqa: E402
from app.models.project.member import ProjectMember  # noqa: E402

OBSOLETE = [
    "project_test_lead",
    "project_developer",
    "project_tester",
    "project_viewer",
]
MEMBER_CODE = "project_member"


async def migrate() -> None:
    async with async_session_maker() as s:
        print("=" * 60)
        print("🔧 项目角色收口：5 角色 → 负责人 + 成员")
        print("=" * 60)

        # 1) 确保 project_member 存在
        member = (
            await s.execute(select(Role).where(Role.code == MEMBER_CODE))
        ).scalar_one_or_none()
        if member is None:
            member = Role(
                code=MEMBER_CODE,
                name="项目成员",
                description="项目成员（组织标签，不单独控权；实际操作权限由系统角色决定）",
                is_system=True,
                sort_order=11,
            )
            s.add(member)
            await s.flush()
            print(f"  ＋ 补建角色 {MEMBER_CODE}")
        else:
            print(f"  ✓ 角色 {MEMBER_CODE} 已存在")

        # 2) 找废弃角色
        obsolete_roles = (
            await s.execute(select(Role).where(Role.code.in_(OBSOLETE)))
        ).scalars().all()
        obsolete_ids = [r.id for r in obsolete_roles]
        if not obsolete_ids:
            print("  ✓ 无废弃项目角色，已是收口状态")
            await s.commit()
            await engine.dispose()
            return

        # 3) 改挂成员引用 → project_member
        res = await s.execute(
            update(ProjectMember)
            .where(ProjectMember.project_role_id.in_(obsolete_ids))
            .values(project_role_id=member.id)
        )
        print(f"  ↻ 迁移成员 {res.rowcount} 名 → {MEMBER_CODE}")

        # 4) 删废弃角色的权限分配
        await s.execute(
            delete(RolePermission).where(RolePermission.role_id.in_(obsolete_ids))
        )
        # 5) 删废弃角色
        await s.execute(delete(Role).where(Role.id.in_(obsolete_ids)))
        print(f"  ✗ 删除废弃角色：{', '.join(r.code for r in obsolete_roles)}")

        await s.commit()
        print("\n✅ 收口完成（project_owner 保留，其余并入 project_member）")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())
