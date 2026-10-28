"""用户大模型配置 CRUD

每个用户每种类型(text/embed/vision)可配置多个，运行时取 ``is_default=True`` 的那条。
"同一 (user_id, model_type) 恰好一个默认"由本层在事务内用 ``SELECT ... FOR UPDATE``
锁住该组全部行后批量改写保证（MySQL/InnoDB 不支持 partial unique index）。沿用
``crud/web_test/script.py:get_for_update`` 的行锁风格——必须在未提交事务内调用，锁持有到
commit/rollback。
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth.user_llm_config import ModelType, UserLlmConfig


class CRUDUserLlmConfig:

    # ---------------------------------------------------------------- 读

    async def get_default(
        self, db: AsyncSession, *, user_id: int, model_type: str = ModelType.TEXT
    ) -> Optional[UserLlmConfig]:
        """运行时入口：取该用户该类型的默认配置。

        正常情况下每组恰好一个 is_default=True。为兜底历史/异常数据（全无默认时），
        回退到该组最早一条，避免明明配了却报"未配置"。
        """
        result = await db.execute(
            select(UserLlmConfig)
            .where(
                UserLlmConfig.user_id == user_id,
                UserLlmConfig.model_type == model_type,
            )
            .order_by(UserLlmConfig.is_default.desc(), UserLlmConfig.id.asc())
        )
        return result.scalars().first()

    async def list_by_user_and_type(
        self, db: AsyncSession, *, user_id: int, model_type: str
    ) -> List[UserLlmConfig]:
        result = await db.execute(
            select(UserLlmConfig)
            .where(
                UserLlmConfig.user_id == user_id,
                UserLlmConfig.model_type == model_type,
            )
            .order_by(UserLlmConfig.is_default.desc(), UserLlmConfig.id.asc())
        )
        return list(result.scalars().all())

    async def get_all_by_user(
        self, db: AsyncSession, *, user_id: int
    ) -> List[UserLlmConfig]:
        result = await db.execute(
            select(UserLlmConfig)
            .where(UserLlmConfig.user_id == user_id)
            .order_by(
                UserLlmConfig.model_type.asc(),
                UserLlmConfig.is_default.desc(),
                UserLlmConfig.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def get_by_id(
        self, db: AsyncSession, *, config_id: int, user_id: int
    ) -> Optional[UserLlmConfig]:
        """按 id 取配置，user_id 进 WHERE —— 越权(IDOR)防护的根，查不到即非本人所有。"""
        result = await db.execute(
            select(UserLlmConfig).where(
                UserLlmConfig.id == config_id,
                UserLlmConfig.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    # ----------------------------------------------------------- 内部工具

    async def _lock_group(
        self, db: AsyncSession, *, user_id: int, model_type: str
    ) -> List[UserLlmConfig]:
        """锁住该 (user_id, model_type) 的全部行（FOR UPDATE），用于串行化默认切换。"""
        result = await db.execute(
            select(UserLlmConfig)
            .where(
                UserLlmConfig.user_id == user_id,
                UserLlmConfig.model_type == model_type,
            )
            .with_for_update()
        )
        return list(result.scalars().all())

    # ---------------------------------------------------------------- 写

    async def create(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        model_type: str = ModelType.TEXT,
        provider: str,
        model: str,
        api_key: str,
        base_url: Optional[str] = None,
        model_family: Optional[str] = None,
        name: Optional[str] = None,
        make_default: bool = False,
    ) -> UserLlmConfig:
        """新建一条配置。该类型首条自动成为默认；make_default=True 则抢占默认。"""
        now = datetime.utcnow()
        # 同事务内锁旧行：决定是否首条、并在需要时把旧默认置 False
        existing = await self._lock_group(db, user_id=user_id, model_type=model_type)
        as_default = make_default or len(existing) == 0
        if as_default:
            for r in existing:
                r.is_default = False

        obj = UserLlmConfig(
            user_id=user_id,
            model_type=model_type,
            name=name,
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            model_family=model_family,
            is_active=True,
            is_default=as_default,
            created_at=now,
            updated_at=now,
        )
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj

    async def update(
        self,
        db: AsyncSession,
        *,
        config_id: int,
        user_id: int,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_family: Optional[str] = None,
        name: Optional[str] = None,
        update_base_url: bool = False,
        update_model_family: bool = False,
        update_name: bool = False,
    ) -> Optional[UserLlmConfig]:
        """改一条配置（不在此切默认、不允许改 model_type）。

        base_url / model_family / name 可被显式置空，故用 update_* 开关区分
        "未传"与"传了 None"。
        """
        obj = await self.get_by_id(db, config_id=config_id, user_id=user_id)
        if not obj:
            return None
        if provider is not None:
            obj.provider = provider
        if model is not None:
            obj.model = model
        if api_key is not None:
            obj.api_key = api_key
        if update_base_url:
            obj.base_url = base_url
        if update_model_family:
            obj.model_family = model_family
        if update_name:
            obj.name = name
        obj.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(obj)
        return obj

    async def set_default(
        self, db: AsyncSession, *, config_id: int, user_id: int
    ) -> Optional[UserLlmConfig]:
        """把某配置设为其类型的默认（事务锁该组全部行，串行化并发切换）。

        同时把目标置 is_active=True，避免"默认却被停用"的死状态。
        """
        target = await self.get_by_id(db, config_id=config_id, user_id=user_id)
        if not target:
            return None
        rows = await self._lock_group(
            db, user_id=user_id, model_type=target.model_type
        )
        for r in rows:
            if r.id == config_id:
                r.is_default = True
                r.is_active = True
            else:
                r.is_default = False
        await db.commit()
        await db.refresh(target)
        return target

    async def delete_by_id(
        self, db: AsyncSession, *, config_id: int, user_id: int
    ) -> bool:
        """删一条配置；若删的是默认且尚有其它，自动把最早一条顺位提升为默认。"""
        target = await self.get_by_id(db, config_id=config_id, user_id=user_id)
        if not target:
            return False
        was_default = target.is_default
        model_type = target.model_type
        await db.delete(target)
        await db.flush()  # 先落删除，再选顺位继任者

        if was_default:
            result = await db.execute(
                select(UserLlmConfig)
                .where(
                    UserLlmConfig.user_id == user_id,
                    UserLlmConfig.model_type == model_type,
                )
                .order_by(UserLlmConfig.id.asc())
                .with_for_update()
                .limit(1)
            )
            survivor = result.scalar_one_or_none()
            if survivor:
                survivor.is_default = True
        await db.commit()
        return True


crud_user_llm_config = CRUDUserLlmConfig()
