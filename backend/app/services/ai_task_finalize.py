"""AI 任务在「执行壳之外」被终结时，联动收尾预创建的业务执行记录。

提交路径是「先立账」：专用 run 端点 / 小测工具先预创建业务执行记录
（app_execution / app_suite_execution / web_task_execution / web_suite_execution /
api_task_execution / perf_run），再建 ai_task、后派发，执行图跑起来后由图收尾。
但任务若从未被 worker 领取（broker 消息丢失 / 队列无 worker → 排队中取消），
或 worker 崩溃后被僵尸回收，图的收尾代码永远不会执行——这些预创建记录会
永远停在 pending/running，各执行记录列表页出现永久「排队中/执行中」残骸。

本模块按 task_type 从 input_params 定位预创建记录 id，把仍处于活跃状态的行
写成该家族自己的终态词（各表状态词汇不同，见 _HANDLERS 内注释）。
尽力而为：单个家族收尾失败只记日志，绝不阻断 ai_task 自身的状态流转。

调用方：
  - 取消端点（pending 直接终态 / running 心跳超时就地回收）
  - reap_zombies 僵尸巡检（同一种孤儿，同一种收尾）
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)
_ACTIVE = {"pending", "running", "queued"}


def _record_id(params: dict, *keys: str) -> Optional[int]:
    """从 input_params 里按候选键取记录 id（端点与小测工具的键名一致，
    候选列表只为防御历史数据）。"""
    for key in keys:
        value = (params or {}).get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


async def _finalize_app_script(db, params: dict, canceled: bool, done: list) -> None:
    from app.crud.app_test.execution import crud_app_execution

    exec_id = _record_id(params, "execution_id")
    if exec_id is None:
        return
    execution = await crud_app_execution.get(db, exec_id)
    if execution is not None and execution.status in _ACTIVE:
        await crud_app_execution.update(
            db, execution, {"status": "cancelled" if canceled else "failed"}
        )
        done.append(f"app_execution#{exec_id}")


async def _finalize_app_suite(db, params: dict, canceled: bool, done: list) -> None:
    from app.crud.app_test.execution import crud_app_execution
    from app.crud.app_test.suite import crud_app_suite_execution

    exec_id = _record_id(params, "suite_execution_id")
    if exec_id is None:
        return
    word = "cancelled" if canceled else "failed"
    execution = await crud_app_suite_execution.get(db, exec_id)
    if execution is not None and execution.status in _ACTIVE:
        await crud_app_suite_execution.update(db, execution, {"status": word})
        done.append(f"app_suite_execution#{exec_id}")
    for child, _name in await crud_app_execution.get_by_suite_execution(db, exec_id):
        if child.status in _ACTIVE:
            await crud_app_execution.update(db, child, {"status": word})
            done.append(f"app_execution#{child.id}")


_HANDLERS = {
    "run_app_script": _finalize_app_script,
    "run_app_suite": _finalize_app_suite,
}


async def finalize_biz_records(db, task, *, canceled: bool) -> list[str]:
    """把 task 预创建的业务执行记录写成终态。

    canceled=True 用各家族的「取消」词（用户主动取消排队任务）；
    False 用 failed（僵尸回收）。返回已收尾记录的描述列表（日志/提示用）。
    """
    handler = _HANDLERS.get(task.task_type)
    done: list[str] = []
    if handler is None:
        return done
    try:
        await handler(db, task.input_params or {}, canceled, done)
    except Exception:
        logger.warning(
            "任务 %s(%s) 业务执行记录收尾失败（不阻断任务状态流转）",
            task.id,
            task.task_type,
            exc_info=True,
        )
    return done
