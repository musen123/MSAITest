"""
测试环境业务服务层

处理测试环境相关的业务逻辑
"""

import json
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import BusinessException, NotFoundException
from app.crud.test_environment import environment, environment_variable
from app.models.test_environment.environment import TestEnvironment
from app.schemas.test_environment.environment import (
    EnvironmentCloneRequest,
    EnvironmentCloneResponse,
    EnvironmentCreate,
    EnvironmentUpdate,
)


class EnvironmentService:
    """
    测试环境业务服务类
    """

    @staticmethod
    async def create_environment(
        db: AsyncSession, *, obj_in: EnvironmentCreate, project_id: int
    ) -> TestEnvironment:
        """
        创建测试环境

        Args:
            db: 数据库会话
            obj_in: 创建数据
            project_id: 项目ID

        Returns:
            TestEnvironment: 创建的环境

        Raises:
            BusinessException: 环境名称已存在
        """
        if await environment.name_exists(db, project_id=project_id, name=obj_in.name):
            raise BusinessException("环境名称已存在")
        if obj_in.is_default:
            await environment.set_default_environment(
                db, project_id=project_id, env_id=0
            )
        return await environment.create(db, obj_in=obj_in, project_id=project_id)

    @staticmethod
    async def update_environment(
        db: AsyncSession, *, db_obj: TestEnvironment, obj_in: EnvironmentUpdate
    ) -> TestEnvironment:
        """
        更新测试环境

        Args:
            db: 数据库会话
            db_obj: 数据库中的环境
            obj_in: 更新数据

        Returns:
            TestEnvironment: 更新后的环境

        Raises:
            BusinessException: 环境名称已存在
        """
        if obj_in.name and obj_in.name != db_obj.name:
            if await environment.name_exists(
                db, project_id=db_obj.project_id, name=obj_in.name, exclude_id=db_obj.id
            ):
                raise BusinessException("环境名称已存在")
        if obj_in.is_default and (not db_obj.is_default):
            await environment.set_default_environment(
                db, project_id=db_obj.project_id, env_id=db_obj.id
            )
            update_data = obj_in.model_dump(exclude_unset=True)
            update_data.pop("is_default", None)
            return await environment.update(db, db_obj=db_obj, obj_in=update_data)
        return await environment.update(db, db_obj=db_obj, obj_in=obj_in)

    @staticmethod
    async def delete_environment(db: AsyncSession, *, env_id: int) -> bool:
        """
        删除测试环境

        Args:
            db: 数据库会话
            env_id: 环境ID

        Returns:
            bool: 是否删除成功

        Raises:
            NotFoundException: 环境不存在
        """
        from datetime import datetime

        env = await environment.get(db, id=env_id)
        if not env:
            raise NotFoundException("环境不存在")
        if env.is_default:
            raise BusinessException("不能删除默认环境")
        await environment_variable.delete_by_env(db, env_id=env_id)
        env.is_deleted = True
        env.deleted_at = datetime.utcnow()
        await db.commit()
        return True

    @staticmethod
    async def set_default_environment(
        db: AsyncSession, *, project_id: int, env_id: int
    ) -> TestEnvironment:
        """
        设置默认环境

        Args:
            db: 数据库会话
            project_id: 项目ID
            env_id: 环境ID

        Returns:
            TestEnvironment: 设置为默认的环境

        Raises:
            NotFoundException: 环境不存在
        """
        env = await environment.get(db, id=env_id)
        if not env:
            raise NotFoundException("环境不存在")
        if env.project_id != project_id:
            raise BusinessException("环境不属于该项目")
        return await environment.set_default_environment(
            db, project_id=project_id, env_id=env_id
        )

    @staticmethod
    async def clone_environment(
        db: AsyncSession,
        *,
        source_env: TestEnvironment,
        clone_data: EnvironmentCloneRequest,
    ) -> EnvironmentCloneResponse:
        """
        克隆测试环境

        Args:
            db: 数据库会话
            source_env: 源环境
            clone_data: 克隆数据

        Returns:
            EnvironmentCloneResponse: 克隆结果

        Raises:
            BusinessException: 环境名称已存在
        """
        from datetime import datetime
        from sqlalchemy import select as sql_select

        check_stmt = sql_select(TestEnvironment).where(
            TestEnvironment.project_id == source_env.project_id,
            TestEnvironment.name == clone_data.name,
        )
        result = await db.execute(check_stmt)
        existing_env = result.scalar_one_or_none()
        if existing_env:
            if existing_env.is_deleted:
                existing_env.is_deleted = False
                existing_env.deleted_at = None
                existing_env.name = clone_data.name
                existing_env.base_url = source_env.base_url
                existing_env.description = source_env.description
                existing_env.env_type = source_env.env_type
                existing_env.is_default = False
                existing_env.is_global = source_env.is_global
                existing_env.proxy_url = source_env.proxy_url
                existing_env.timeout = source_env.timeout
                existing_env.verify_ssl = source_env.verify_ssl
                existing_env.allow_redirects = source_env.allow_redirects
                existing_env.keep_cookies = source_env.keep_cookies
                existing_env.retry_times = source_env.retry_times
                if source_env.pre_script:
                    try:
                        existing_env.pre_script = json.dumps(
                            json.loads(source_env.pre_script), ensure_ascii=False
                        )
                    except Exception:
                        existing_env.pre_script = None
                if source_env.post_script:
                    try:
                        existing_env.post_script = json.dumps(
                            json.loads(source_env.post_script), ensure_ascii=False
                        )
                    except Exception:
                        existing_env.post_script = None
                existing_env.updated_at = datetime.utcnow()
                from app.models.test_environment.variable import EnvironmentVariable

                delete_stmt = sql_select(EnvironmentVariable).where(
                    EnvironmentVariable.env_id == existing_env.id
                )
                delete_result = await db.execute(delete_stmt)
                deleted_vars = delete_result.scalars().all()
                for var in deleted_vars:
                    await db.delete(var)
                variables, _ = await environment_variable.get_multi_by_env(
                    db, env_id=source_env.id
                )
                for var in variables:
                    new_var = EnvironmentVariable(
                        env_id=existing_env.id,
                        name=var.name,
                        value=var.value,
                        type=var.type,
                        description=var.description,
                        is_active=var.is_active,
                        sort_order=var.sort_order,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                    db.add(new_var)
                await db.commit()
                await db.refresh(existing_env)
                return EnvironmentCloneResponse(
                    id=existing_env.id,
                    name=existing_env.name,
                    source_env_id=source_env.id,
                )
            else:
                raise BusinessException("环境名称已存在")
        new_env = TestEnvironment(
            project_id=source_env.project_id,
            name=clone_data.name,
            base_url=source_env.base_url,
            description=source_env.description,
            env_type=source_env.env_type,
            is_default=False,
            is_global=source_env.is_global,
            proxy_url=source_env.proxy_url,
            timeout=source_env.timeout,
            verify_ssl=source_env.verify_ssl,
            allow_redirects=source_env.allow_redirects,
            keep_cookies=source_env.keep_cookies,
            retry_times=source_env.retry_times,
        )
        if source_env.pre_script:
            try:
                new_env.pre_script = json.dumps(
                    json.loads(source_env.pre_script), ensure_ascii=False
                )
            except Exception:
                new_env.pre_script = None
        if source_env.post_script:
            try:
                new_env.post_script = json.dumps(
                    json.loads(source_env.post_script), ensure_ascii=False
                )
            except Exception:
                new_env.post_script = None
        new_env.created_at = datetime.utcnow()
        new_env.updated_at = datetime.utcnow()
        db.add(new_env)
        await db.flush()
        variables, _ = await environment_variable.get_multi_by_env(
            db, env_id=source_env.id
        )
        for var in variables:
            from app.models.test_environment.variable import EnvironmentVariable

            new_var = EnvironmentVariable(
                env_id=new_env.id,
                name=var.name,
                value=var.value,
                type=var.type,
                description=var.description,
                is_active=var.is_active,
                sort_order=var.sort_order,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(new_var)
        await db.commit()
        await db.refresh(new_env)
        return EnvironmentCloneResponse(
            id=new_env.id, name=new_env.name, source_env_id=source_env.id
        )

    @staticmethod
    async def get_environment_detail(db: AsyncSession, *, env_id: int) -> dict:
        """
        获取环境详情（包含变量）

        Args:
            db: 数据库会话
            env_id: 环境ID

        Returns:
            dict: 环境详情

        Raises:
            NotFoundException: 环境不存在
        """
        env = await environment.get_with_variables(db, env_id=env_id)
        if not env:
            raise NotFoundException("环境不存在")
        env_dict = {
            "id": env.id,
            "project_id": env.project_id,
            "name": env.name,
            "base_url": env.base_url,
            "description": env.description,
            "env_type": env.env_type,
            "is_default": env.is_default,
            "is_global": env.is_global,
            "proxy_url": env.proxy_url,
            "timeout": env.timeout,
            "verify_ssl": bool(env.verify_ssl),
            "allow_redirects": bool(env.allow_redirects),
            "keep_cookies": bool(env.keep_cookies),
            "retry_times": env.retry_times,
            "variable_count": len(env.variables),
            "created_at": env.created_at.isoformat() if env.created_at else "",
            "updated_at": env.updated_at.isoformat() if env.updated_at else "",
        }
        if env.pre_script:
            try:
                env_dict["pre_script"] = json.loads(env.pre_script)
            except Exception:
                env_dict["pre_script"] = None
        else:
            env_dict["pre_script"] = None
        if env.post_script:
            try:
                env_dict["post_script"] = json.loads(env.post_script)
            except Exception:
                env_dict["post_script"] = None
        else:
            env_dict["post_script"] = None
        variables_data = []
        for var in env.variables:
            var_dict = {
                "id": var.id,
                "name": var.name,
                "value": "****" if var.type == "password" else var.value,
                "type": var.type,
                "description": var.description,
                "is_active": var.is_active,
                "sort_order": var.sort_order,
                "created_at": var.created_at.isoformat() if var.created_at else "",
                "updated_at": var.updated_at.isoformat() if var.updated_at else "",
            }
            variables_data.append(var_dict)
        env_dict["variables"] = variables_data
        return env_dict


environment_service = EnvironmentService()
