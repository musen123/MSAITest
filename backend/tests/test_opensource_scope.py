"""精简版的公开接口、任务边界和保留报表回归。"""

import ast
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.orm import configure_mappers

from app.ai_core.runtime import registry
from app.db.init_db import SUPPLEMENTAL_PERMISSIONS, SYSTEM_ROLE_DEFINITIONS
from app.models.base import Base
from app.services.project import dashboard_service, report_center_service
from app.services.report.report_service import ReportService
from app.tasks.ai_task import queue_for_task_type
from main import app


def test_removed_domains_have_no_public_routes_or_tables():
    configure_mappers()
    paths = app.openapi()["paths"]
    assert any("/func-test-cases" in path for path in paths)
    assert any("/app/scripts" in path for path in paths)
    assert any("/knowledge" in path for path in paths)
    for path in paths:
        assert not any(
            part in path
            for part in (
                "/api-imports",
                "/api-interfaces",
                "/api-test-",
                "/business-flows",
                "/flow-agent",
                "/web-",
                "/perf-",
                "/performance",
                "/agent-experiences",
                "/saved-sql",
            )
        )
    assert not any(
        name.startswith(("api_", "web_", "perf_"))
        or name in {"business_flow", "agent_experience", "saved_sql"}
        for name in Base.metadata.tables
    )


def test_only_retained_task_types_and_permissions_are_registered():
    types = set(registry.all_types())
    assert {"generate_case", "kb_ingest", "run_app_script", "run_app_suite"} <= types
    assert not any(
        "web" in name
        or "perf" in name
        or "interface" in name
        or "flow" in name
        or "api" in name
        for name in types
    )
    assert queue_for_task_type("run_app_script") == "app_tasks"
    assert queue_for_task_type("generate_case") == "ai_tasks"
    permissions = [p["code"] for p in SUPPLEMENTAL_PERMISSIONS]
    permissions.extend(
        code for role in SYSTEM_ROLE_DEFINITIONS for code in role["permission_codes"]
    )
    assert not any(
        code.startswith(
            (
                "api_test:",
                "web_test:",
                "web_element:",
                "perf_test:",
                "agent_experience:",
            )
        )
        for code in permissions
    )


def test_initial_migration_matches_retained_tables():
    source = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/01e74825fd25_baseline.py"
    )
    tree = ast.parse(source.read_text())
    tables = {
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "create_table"
    }
    assert tables == set(Base.metadata.tables)


@pytest.mark.asyncio
async def test_report_summary_counts_functional_and_app_execution():
    functional, device = MagicMock(), MagicMock()
    functional.one.return_value = (4, 2, 1)
    device.one.return_value = (3, 1, 1)
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[functional, device])
    report = await ReportService.get_summary(db, project_id=12)
    assert report.total_executions == 7
    assert report.functional_executions == 4 and report.app_executions == 3
    assert report.overall_pass_rate == 60.0
    for call in db.execute.call_args_list:
        sql = str(call.args[0])
        assert "api_" not in sql and "web_" not in sql and "perf_" not in sql


@pytest.mark.asyncio
async def test_empty_project_reports_load_without_removed_models():
    result = MagicMock()
    result.scalar.return_value = 0
    result.scalar_one.return_value = 0
    result.scalar_one_or_none.return_value = None
    result.one.return_value = (0, 0, 0, None)
    result.all.return_value = []
    result.scalars.return_value = result
    result.first.return_value = None
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    assets = await report_center_service.get_assets_report(db, project_id=12)
    assert assets["cards"]["case_total"]["by_type"] == {"functional": 0, "app": 0}
    execution = await report_center_service.get_execution_report(db, project_id=12)
    assert {item["key"] for item in execution["modules"]} == {"functional", "app"}
    dashboard = await dashboard_service.get_dashboard(db, project_id=12)
    assert dashboard["stat_cards"]["case_total"]["by_type"] == {
        "functional": 0,
        "app": 0,
    }
