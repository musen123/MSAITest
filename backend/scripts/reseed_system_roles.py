"""授权重设：把「系统角色 → 权限」重置为 init_db.SYSTEM_ROLE_DEFINITIONS 的新设计

适用于**已上线 / 已初始化**的库（init_db 的 create_roles 在表里有数据时整段跳过，
改了矩阵不会自动生效）。本脚本对系统角色做**权威重置**（幂等，可重复运行）：

  1. super_admin —— 确保存在，并补齐「库内全部权限点」（始终全权限）；
  2. admin / project_admin / tester / user —— 确保存在，并把其权限集合**替换**为
     SYSTEM_ROLE_DEFINITIONS 中声明的矩阵（删除旧 role_permission，按矩阵重建）。

边界（安全）：
  - 只动上述 5 个系统角色；**不碰**用户、项目角色(project_*)、或任何自建角色；
  - 不删用户与角色本身，只重写这 5 个角色的权限分配；
  - 缺失的角色会按矩阵补建(is_system=True)。

用法（在 backend 目录下）：
    uv run python scripts/reseed_system_roles.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete, select  # noqa: E402

from app.db.init_db import SYSTEM_ROLE_DEFINITIONS  # noqa: E402
from app.db.session import async_session_maker, engine  # noqa: E402
from app.models.auth.permission import Permission  # noqa: E402
from app.models.auth.role import Role  # noqa: E402
from app.models.auth.role_permission import RolePermission  # noqa: E402

SUPER_ADMIN = {
    "code": "super_admin",
    "name": "超级管理员",
    "description": "拥有系统所有权限",
    "sort_order": 1,
}


async def _get_or_create_role(session, *, code, name, description, sort_order) -> Role:
    role = (
        await session.execute(select(Role).where(Role.code == code))
    ).scalar_one_or_none()
    if role is None:
        role = Role(
            code=code,
            name=name,
            description=description,
            is_system=True,
            sort_order=sort_order,
        )
        session.add(role)
        await session.flush()
        print(f"  ＋ 角色 {code} 不存在，已补建")
    return role


async def _set_role_permissions(session, role: Role, perm_ids: list[int]) -> int:
    """权威重置：清空该角色现有权限分配，再按 perm_ids 重建。返回最终权限数。"""
    await session.execute(
        delete(RolePermission).where(RolePermission.role_id == role.id)
    )
    for pid in perm_ids:
        session.add(RolePermission(role_id=role.id, permission_id=pid))
    return len(perm_ids)


async def reseed_system_roles() -> None:
    async with async_session_maker() as session:
        all_perms = (await session.execute(select(Permission))).scalars().all()
        perm_by_code = {p.code: p for p in all_perms}
        all_perm_ids = [p.id for p in all_perms]

        print("=" * 60)
        print("🔐 重置系统角色权限（权威，按 SYSTEM_ROLE_DEFINITIONS）")
        print("=" * 60)

        # 1) super_admin —— 全部权限
        sa = await _get_or_create_role(session, **SUPER_ADMIN)
        n = await _set_role_permissions(session, sa, all_perm_ids)
        print(f"  ✓ super_admin：{n} 项权限（全量）")

        # 2) 其余职能角色 —— 按矩阵
        missing_codes: set[str] = set()
        for role_def in SYSTEM_ROLE_DEFINITIONS:
            role = await _get_or_create_role(
                session,
                code=role_def["code"],
                name=role_def["name"],
                description=role_def["description"],
                sort_order=role_def["sort_order"],
            )
            ids = []
            for code in role_def["permission_codes"]:
                perm = perm_by_code.get(code)
                if perm:
                    ids.append(perm.id)
                else:
                    missing_codes.add(code)
            n = await _set_role_permissions(session, role, ids)
            print(f"  ✓ {role_def['code']}：{n} 项权限")

        await session.commit()

        if missing_codes:
            print(
                "\n⚠ 以下权限码在库中不存在(矩阵引用了但未建)，已跳过：\n   "
                + ", ".join(sorted(missing_codes))
                + "\n   如需补建，请先运行 scripts/sync_permissions.py"
            )

        print("\n✅ 系统角色权限已重置完成（项目角色 project_* 与用户分配未受影响）")

    # 释放连接池，避免脚本退出时 aiomysql 在已关闭事件循环上清理连接报错
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(reseed_system_roles())
