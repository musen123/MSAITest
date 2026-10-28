"""小测 AI 助手工具集（平台 Copilot）

分组：
  - 查询（只读）：query_tools
  - 执行（产生真实测试执行）：exec_tools
  - 管理/创建（写库）：manage_tools
  - 导航：navigate_tools
"""

from app.ai_core.chat_agent.tools.app_tools import (
    explore_app,
    query_app_assets,
    query_app_devices,
    run_app_case,
    run_app_suite,
)
from app.ai_core.chat_agent.tools.config_tools import (
    create_environment,
    create_scheduled_job,
    kb_ingest_text,
    query_members,
    update_environment,
    update_scheduled_job,
)
from app.ai_core.chat_agent.tools.exec_tools import (
    run_scheduled_job,
    toggle_scheduled_job,
)
from app.ai_core.chat_agent.tools.manage_tools import (
    create_bug,
    extract_requirements,
    generate_func_cases,
    review_func_cases,
)
from app.ai_core.chat_agent.tools.memory_tools import forget, recall, remember
from app.ai_core.chat_agent.tools.navigate_tools import open_page
from app.ai_core.chat_agent.tools.query_tools import (
    analyze_change_impact,
    get_execution_report,
    get_project_overview,
    get_requirement_detail,
    kb_search,
    query_ai_tasks,
    query_kb_graph,
    query_bugs,
    query_environments,
    query_func_cases,
    query_requirements,
    query_scheduled_jobs,
)
from app.ai_core.chat_agent.tools.permissions import guard_tool

_RAW_TOOLS = [
    get_project_overview,
    query_requirements,
    get_requirement_detail,
    query_func_cases,
    query_app_assets,
    query_app_devices,
    query_bugs,
    query_environments,
    query_scheduled_jobs,
    query_ai_tasks,
    query_members,
    get_execution_report,
    kb_search,
    query_kb_graph,
    analyze_change_impact,
    run_app_case,
    run_app_suite,
    explore_app,
    run_scheduled_job,
    toggle_scheduled_job,
    create_bug,
    review_func_cases,
    generate_func_cases,
    extract_requirements,
    create_scheduled_job,
    update_scheduled_job,
    create_environment,
    update_environment,
    kb_ingest_text,
    remember,
    recall,
    forget,
    open_page,
]
ALL_TOOLS = [guard_tool(_t) for _t in _RAW_TOOLS]
