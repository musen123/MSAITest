"""「排队中卡死取消不掉」修复的回归测试（纯逻辑 + monkeypatch，不碰真库）。

守护的不变量：
  - 取消端点对 pending 任务直接原子转终态（canceled）；worker 恰好抢走则不动；
  - running 任务心跳正常走协作取消（不就地终结）、心跳僵死就地标 failed；
  - finalize_biz_records 按 task_type 用各家族自己的终态词收尾预创建记录，
    且只动仍处于活跃状态的行；未登记类型 / 缺记录 id 一律 no-op；
  - 单个家族收尾抛异常被吞掉（不阻断任务状态流转）。
"""

from types import SimpleNamespace
import pytest
from app.services import ai_task_finalize as fin


def _task(task_type: str, **params):
    return SimpleNamespace(id=1, task_type=task_type, input_params=params)


class TestFinalizeBizRecords:

    async def test_app_script_canceled_word(self, monkeypatch) -> None:
        from app.crud.app_test.execution import crud_app_execution

        row = SimpleNamespace(id=9, status="pending")
        updates: list = []

        async def fake_get(db, execution_id):
            return row if execution_id == 9 else None

        async def fake_update(db, execution, changes):
            updates.append((execution.id, changes))

        monkeypatch.setattr(crud_app_execution, "get", fake_get)
        monkeypatch.setattr(crud_app_execution, "update", fake_update)
        done = await fin.finalize_biz_records(
            None, _task("run_app_script", execution_id=9), canceled=True
        )
        assert updates == [(9, {"status": "cancelled"})]
        assert done == ["app_execution#9"]

    async def test_app_script_zombie_failed_word(self, monkeypatch) -> None:
        from app.crud.app_test.execution import crud_app_execution

        row = SimpleNamespace(id=9, status="running")
        updates: list = []

        async def fake_get(db, execution_id):
            return row

        async def fake_update(db, execution, changes):
            updates.append(changes)

        monkeypatch.setattr(crud_app_execution, "get", fake_get)
        monkeypatch.setattr(crud_app_execution, "update", fake_update)
        await fin.finalize_biz_records(
            None, _task("run_app_script", execution_id=9), canceled=False
        )
        assert updates == [{"status": "failed"}]

    async def test_terminal_row_untouched(self, monkeypatch) -> None:
        from app.crud.app_test.execution import crud_app_execution

        row = SimpleNamespace(id=9, status="success")
        updates: list = []

        async def fake_get(db, execution_id):
            return row

        async def fake_update(db, execution, changes):
            updates.append(changes)

        monkeypatch.setattr(crud_app_execution, "get", fake_get)
        monkeypatch.setattr(crud_app_execution, "update", fake_update)
        done = await fin.finalize_biz_records(
            None, _task("run_app_script", execution_id=9), canceled=True
        )
        assert updates == [] and done == []

    async def test_app_suite_finalizes_children_too(self, monkeypatch) -> None:
        from app.crud.app_test.execution import crud_app_execution
        from app.crud.app_test.suite import crud_app_suite_execution

        suite_row = SimpleNamespace(id=5, status="pending")
        child_active = SimpleNamespace(id=51, status="running")
        child_done = SimpleNamespace(id=52, status="success")
        updates: list = []

        async def fake_suite_get(db, execution_id):
            return suite_row

        async def fake_suite_update(db, execution, changes):
            updates.append(("suite", execution.id, changes["status"]))

        async def fake_children(db, suite_execution_id):
            return [(child_active, "用例A"), (child_done, "用例B")]

        async def fake_child_update(db, execution, changes):
            updates.append(("child", execution.id, changes["status"]))

        monkeypatch.setattr(crud_app_suite_execution, "get", fake_suite_get)
        monkeypatch.setattr(crud_app_suite_execution, "update", fake_suite_update)
        monkeypatch.setattr(crud_app_execution, "get_by_suite_execution", fake_children)
        monkeypatch.setattr(crud_app_execution, "update", fake_child_update)
        done = await fin.finalize_biz_records(
            None, _task("run_app_suite", suite_execution_id=5), canceled=True
        )
        assert ("suite", 5, "cancelled") in updates
        assert ("child", 51, "cancelled") in updates
        assert not any((u[1] == 52 for u in updates))
        assert "app_suite_execution#5" in done

    async def test_unregistered_type_and_missing_id_noop(self) -> None:
        assert (
            await fin.finalize_biz_records(
                None, _task("generate_case", script_id=1), canceled=True
            )
            == []
        )
        assert (
            await fin.finalize_biz_records(None, _task("run_app_script"), canceled=True)
            == []
        )

    async def test_handler_exception_swallowed(self, monkeypatch) -> None:
        from app.crud.app_test.execution import crud_app_execution

        async def boom(db, execution_id):
            raise RuntimeError("db down")

        monkeypatch.setattr(crud_app_execution, "get", boom)
        done = await fin.finalize_biz_records(
            None, _task("run_app_script", execution_id=9), canceled=True
        )
        assert done == []


class TestForceFinalizeStuck:
    """取消端点的就地终结决策（_force_finalize_stuck）。"""

    @pytest.fixture()
    def endpoint(self):
        from app.api.v1.endpoints.ai import ai_tasks

        return ai_tasks

    async def test_pending_won_race(self, endpoint, monkeypatch) -> None:

        async def fake_cancel(db, *, task_id):
            return True

        monkeypatch.setattr(endpoint.crud_ai_task, "cancel_if_pending", fake_cancel)
        task = SimpleNamespace(id=1, status="pending")
        assert await endpoint._force_finalize_stuck(None, task) == "canceled"

    async def test_pending_lost_race_to_worker(self, endpoint, monkeypatch) -> None:

        async def fake_cancel(db, *, task_id):
            return False

        monkeypatch.setattr(endpoint.crud_ai_task, "cancel_if_pending", fake_cancel)
        task = SimpleNamespace(id=1, status="pending")
        assert await endpoint._force_finalize_stuck(None, task) is None

    async def test_running_alive_stays_cooperative(self, endpoint, monkeypatch) -> None:

        async def fake_zombie(db, *, task, timeout_s):
            return False

        monkeypatch.setattr(endpoint.crud_ai_task, "fail_if_zombie", fake_zombie)
        task = SimpleNamespace(id=1, status="running")
        assert await endpoint._force_finalize_stuck(None, task) is None

    async def test_running_dead_marked_failed(self, endpoint, monkeypatch) -> None:

        async def fake_zombie(db, *, task, timeout_s):
            return True

        monkeypatch.setattr(endpoint.crud_ai_task, "fail_if_zombie", fake_zombie)
        task = SimpleNamespace(id=1, status="running")
        assert await endpoint._force_finalize_stuck(None, task) == "failed"
