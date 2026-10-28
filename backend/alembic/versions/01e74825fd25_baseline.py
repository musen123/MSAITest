"""baseline

Revision ID: 01e74825fd25
Revises:
Create Date: 2026-07-21 21:03:08.669757

"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = "01e74825fd25"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("SET FOREIGN_KEY_CHECKS=0")
    op.create_table(
        "app_agent",
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "name", mysql.VARCHAR(length=64), nullable=False, comment="执行机名称"
        ),
        sa.Column(
            "host_label",
            mysql.VARCHAR(length=128),
            nullable=True,
            comment="宿主机标签（机房/工位等备注）",
        ),
        sa.Column(
            "token_hash",
            mysql.VARCHAR(length=64),
            nullable=False,
            comment="接入 token 的 sha256（hex），明文不落库",
        ),
        sa.Column(
            "token_version",
            mysql.INTEGER(),
            server_default=sa.text("1"),
            nullable=False,
            comment="token 版本号，轮转 +1",
        ),
        sa.Column(
            "host_fingerprint",
            mysql.VARCHAR(length=128),
            nullable=True,
            comment="宿主机硬件指纹（首连绑定，后续不符拒连）",
        ),
        sa.Column(
            "agent_version",
            mysql.VARCHAR(length=32),
            nullable=True,
            comment="Agent 程序版本（register 帧上报）",
        ),
        sa.Column(
            "capabilities",
            mysql.JSON(),
            nullable=True,
            comment="Agent 能力列表，如 ['scrcpy']",
        ),
        sa.Column(
            "protocol_version",
            mysql.INTEGER(),
            server_default=sa.text("1"),
            nullable=False,
            comment="隧道控制帧协议版本",
        ),
        sa.Column(
            "last_heartbeat_at",
            sa.DateTime(),
            nullable=True,
            comment="最近心跳时间（在线判定依据：≤30s=online、≤60s=stale、否则 offline）",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("app_agent", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_app_agent_token_hash"), ["token_hash"], unique=True
        )
    op.create_table(
        "app_control_session",
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "session_id",
            mysql.VARCHAR(length=64),
            nullable=False,
            comment="控制会话ID（s-uuid，与 Redis 锁/ticket 中的 session_id 一致）",
        ),
        sa.Column(
            "udid", mysql.VARCHAR(length=160), nullable=False, comment="被控设备 udid"
        ),
        sa.Column(
            "agent_id",
            mysql.BIGINT(),
            nullable=False,
            comment="设备所属执行机ID（审计快照，无外键）",
        ),
        sa.Column(
            "owner_user_id",
            mysql.BIGINT(),
            nullable=False,
            comment="占用者用户ID（审计快照，无外键）",
        ),
        sa.Column(
            "kind",
            mysql.VARCHAR(length=16),
            server_default=sa.text("'control'"),
            nullable=False,
            comment="占用类型：control/record/replay",
        ),
        sa.Column(
            "started_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="会话开始时间",
        ),
        sa.Column("ended_at", sa.DateTime(), nullable=True, comment="会话结束时间"),
        sa.Column(
            "end_reason",
            mysql.VARCHAR(length=32),
            nullable=True,
            comment="结束原因：released/takeover/ws_closed/ttl_expired 等",
        ),
        sa.Column(
            "actions_summary",
            mysql.JSON(),
            nullable=True,
            comment="动作计数摘要（不含明文内容）",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("app_control_session", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_app_control_session_owner_user_id"),
            ["owner_user_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_app_control_session_session_id"), ["session_id"], unique=True
        )
        batch_op.create_index(
            batch_op.f("ix_app_control_session_udid"), ["udid"], unique=False
        )
    op.create_table(
        "kb_retrieval_log",
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "project_id", mysql.BIGINT(), nullable=False, comment="项目ID（硬隔离列）"
        ),
        sa.Column("user_id", mysql.BIGINT(), nullable=True, comment="查询用户ID"),
        sa.Column(
            "consumer",
            mysql.VARCHAR(length=20),
            server_default=sa.text("'search'"),
            nullable=False,
            comment="消费方：search/answer/chat/requirement/case_gen",
        ),
        sa.Column(
            "query",
            mysql.VARCHAR(length=500),
            nullable=False,
            comment="查询文本（截断 500）",
        ),
        sa.Column(
            "top_k", mysql.INTEGER(), server_default=sa.text("10"), nullable=False
        ),
        sa.Column("doc_types", mysql.JSON(), nullable=True, comment="类型过滤"),
        sa.Column(
            "deep",
            mysql.TINYINT(display_width=1),
            server_default=sa.text("0"),
            nullable=False,
            comment="是否深度模式（改写+重排）",
        ),
        sa.Column(
            "hits",
            mysql.JSON(),
            nullable=True,
            comment="命中 [{chunk_id, document_id, score}]",
        ),
        sa.Column(
            "degraded",
            mysql.JSON(),
            nullable=True,
            comment="降级标志 {vector, fulltext}",
        ),
        sa.Column(
            "latency_ms",
            mysql.INTEGER(),
            server_default=sa.text("0"),
            nullable=False,
            comment="检索耗时（毫秒,不含合成）",
        ),
        sa.Column(
            "adopted_chunk_ids",
            mysql.JSON(),
            nullable=True,
            comment="被采纳的 chunk（需求页点选/引用展开回写）",
        ),
        sa.Column(
            "feedback",
            mysql.TINYINT(),
            nullable=True,
            comment="用户反馈：1 赞 / -1 踩 / NULL 未反馈",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("kb_retrieval_log", schema=None) as batch_op:
        batch_op.create_index(
            "idx_kb_rlog_project_time", ["project_id", "created_at"], unique=False
        )
    op.create_table(
        "sys_permission",
        sa.Column(
            "code", mysql.VARCHAR(length=100), nullable=False, comment="权限编码"
        ),
        sa.Column("name", mysql.VARCHAR(length=50), nullable=False, comment="权限名称"),
        sa.Column(
            "module", mysql.VARCHAR(length=50), nullable=False, comment="所属模块"
        ),
        sa.Column(
            "description", mysql.VARCHAR(length=200), nullable=True, comment="权限描述"
        ),
        sa.Column("sort_order", mysql.INTEGER(), nullable=False, comment="排序顺序"),
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("sys_permission", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_sys_permission_code"), ["code"], unique=True
        )
        batch_op.create_index(
            batch_op.f("ix_sys_permission_module"), ["module"], unique=False
        )
    op.create_table(
        "sys_role",
        sa.Column("code", mysql.VARCHAR(length=50), nullable=False, comment="角色编码"),
        sa.Column("name", mysql.VARCHAR(length=50), nullable=False, comment="角色名称"),
        sa.Column(
            "description", mysql.VARCHAR(length=200), nullable=True, comment="角色描述"
        ),
        sa.Column(
            "is_system", sa.Boolean(), nullable=False, comment="是否系统预定义角色"
        ),
        sa.Column("sort_order", mysql.INTEGER(), nullable=False, comment="排序顺序"),
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.Column("is_deleted", mysql.TINYINT(), nullable=False, comment="是否删除"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="删除时间"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("sys_role", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_sys_role_code"), ["code"], unique=True)
    op.create_table(
        "sys_user",
        sa.Column(
            "username", mysql.VARCHAR(length=50), nullable=False, comment="用户名"
        ),
        sa.Column(
            "password_hash",
            mysql.VARCHAR(length=255),
            nullable=False,
            comment="加密后的密码（bcrypt）",
        ),
        sa.Column("email", mysql.VARCHAR(length=100), nullable=False, comment="邮箱"),
        sa.Column("phone", mysql.VARCHAR(length=20), nullable=True, comment="手机号"),
        sa.Column(
            "real_name", mysql.VARCHAR(length=50), nullable=True, comment="真实姓名"
        ),
        sa.Column(
            "avatar", mysql.VARCHAR(length=255), nullable=True, comment="头像URL"
        ),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "DISABLED", "LOCKED", name="userstatus"),
            nullable=False,
            comment="状态：active/disabled/locked",
        ),
        sa.Column("bio", mysql.VARCHAR(length=500), nullable=True, comment="个人简介"),
        sa.Column(
            "login_fail_count", mysql.INTEGER(), nullable=False, comment="登录失败次数"
        ),
        sa.Column(
            "locked_until", mysql.BIGINT(), nullable=True, comment="锁定到期时间"
        ),
        sa.Column(
            "last_login_at", mysql.BIGINT(), nullable=True, comment="最后登录时间"
        ),
        sa.Column(
            "last_login_ip",
            mysql.VARCHAR(length=50),
            nullable=True,
            comment="最后登录IP",
        ),
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.Column("is_deleted", mysql.TINYINT(), nullable=False, comment="是否删除"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="删除时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone"),
    )
    with op.batch_alter_table("sys_user", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_sys_user_email"), ["email"], unique=True)
        batch_op.create_index(
            batch_op.f("ix_sys_user_status"), ["status"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_sys_user_username"), ["username"], unique=True
        )
    op.create_table(
        "kb_entity",
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "project_id",
            mysql.BIGINT(),
            nullable=False,
            comment="项目ID（硬隔离列，一切查询第一过滤条件）",
        ),
        sa.Column(
            "name",
            mysql.VARCHAR(length=255),
            nullable=False,
            comment="展示名（GraphView 节点 id）",
        ),
        sa.Column(
            "name_norm",
            mysql.VARCHAR(length=255),
            nullable=False,
            comment="归一化合并键（NFKC+lower+strip）",
        ),
        sa.Column(
            "entity_type",
            mysql.VARCHAR(length=50),
            server_default=sa.text("'term'"),
            nullable=False,
            comment="实体类型（受控 10 类词表，service 层准入）",
        ),
        sa.Column(
            "description",
            mysql.TEXT(),
            nullable=True,
            comment="描述（多来源合并，≤2000 字）",
        ),
        sa.Column(
            "ref_count",
            mysql.INTEGER(),
            server_default=sa.text("0"),
            nullable=False,
            comment="引用计数（唯一事实源=mention 台账，可重算）",
        ),
        sa.Column(
            "doc_count",
            mysql.INTEGER(),
            server_default=sa.text("0"),
            nullable=False,
            comment="出现文档数（台账 DISTINCT document_id 重算）",
        ),
        sa.Column(
            "human_edited",
            sa.Boolean(),
            server_default=sa.text("0"),
            nullable=False,
            comment="手工编辑保护位：置位后自动抽取只增 mention/计数，不覆写 name/type/description",
        ),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            server_default=sa.text("0"),
            nullable=False,
            comment="软删墓碑：手工删除留行，自动抽取遇同 name_norm 墓碑跳过（防复活）",
        ),
        sa.Column(
            "merged_into_id",
            mysql.BIGINT(),
            nullable=True,
            comment="合并重定向：被合并者留墓碑指向胜者（无 FK，应用层维护，禁环）",
        ),
        sa.Column(
            "created_by",
            mysql.BIGINT(),
            nullable=True,
            comment="非空=手工创建（ref_count=0 也永不 GC）",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["sys_user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "name_norm", name="uq_kb_entity_project_name"
        ),
    )
    with op.batch_alter_table("kb_entity", schema=None) as batch_op:
        batch_op.create_index(
            "idx_kb_entity_project_hot",
            ["project_id", "is_deleted", "ref_count"],
            unique=False,
        )
        batch_op.create_index(
            "idx_kb_entity_project_type", ["project_id", "entity_type"], unique=False
        )
    op.create_table(
        "sys_operation_log",
        sa.Column("user_id", mysql.BIGINT(), nullable=True, comment="操作用户ID"),
        sa.Column(
            "username",
            mysql.VARCHAR(length=50),
            nullable=True,
            comment="操作用户名（冗余）",
        ),
        sa.Column(
            "module", mysql.VARCHAR(length=50), nullable=False, comment="操作模块"
        ),
        sa.Column(
            "action",
            sa.String(length=50),
            nullable=False,
            comment="操作类型：login/logout/create/update/delete",
        ),
        sa.Column(
            "description", mysql.VARCHAR(length=500), nullable=True, comment="操作描述"
        ),
        sa.Column(
            "request_method",
            sa.String(length=10),
            nullable=True,
            comment="请求方法：GET/POST/PUT/DELETE",
        ),
        sa.Column(
            "request_url", mysql.VARCHAR(length=500), nullable=True, comment="请求URL"
        ),
        sa.Column(
            "request_params", sa.Text(), nullable=True, comment="请求参数（JSON）"
        ),
        sa.Column(
            "response_status", mysql.INTEGER(), nullable=True, comment="响应状态码"
        ),
        sa.Column(
            "ip_address", mysql.VARCHAR(length=50), nullable=True, comment="操作IP地址"
        ),
        sa.Column(
            "user_agent", mysql.VARCHAR(length=500), nullable=True, comment="用户代理"
        ),
        sa.Column(
            "execution_time", mysql.INTEGER(), nullable=True, comment="执行耗时（毫秒）"
        ),
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["sys_user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("sys_operation_log", schema=None) as batch_op:
        batch_op.create_index("idx_action", ["action"], unique=False)
        batch_op.create_index("idx_created_at", ["created_at"], unique=False)
        batch_op.create_index("idx_module", ["module"], unique=False)
        batch_op.create_index("idx_user_id", ["user_id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_sys_operation_log_action"), ["action"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_sys_operation_log_module"), ["module"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_sys_operation_log_user_id"), ["user_id"], unique=False
        )
    op.create_table(
        "sys_role_permission",
        sa.Column("role_id", mysql.BIGINT(), nullable=False, comment="角色ID"),
        sa.Column("permission_id", mysql.BIGINT(), nullable=False, comment="权限ID"),
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.ForeignKeyConstraint(
            ["permission_id"], ["sys_permission.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["role_id"], ["sys_role.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role_id", "permission_id", name="uk_role_permission"),
    )
    with op.batch_alter_table("sys_role_permission", schema=None) as batch_op:
        batch_op.create_index("idx_permission_id", ["permission_id"], unique=False)
        batch_op.create_index("idx_role_id", ["role_id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_sys_role_permission_permission_id"),
            ["permission_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_sys_role_permission_role_id"), ["role_id"], unique=False
        )
    op.create_table(
        "sys_user_llm_config",
        sa.Column("id", mysql.BIGINT(), autoincrement=True, nullable=False),
        sa.Column("user_id", mysql.BIGINT(), nullable=False),
        sa.Column(
            "model_type",
            sa.String(length=20),
            nullable=False,
            comment="模型类型: text/embed/vision",
        ),
        sa.Column(
            "provider",
            sa.String(length=50),
            nullable=False,
            comment="模型提供商: openai/anthropic 等",
        ),
        sa.Column("model", sa.String(length=100), nullable=False, comment="模型名称"),
        sa.Column("api_key", sa.String(length=500), nullable=False, comment="API Key"),
        sa.Column(
            "base_url", sa.String(length=500), nullable=True, comment="自定义 Base URL"
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, comment="是否启用"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column(
            "is_default",
            sa.Boolean(),
            server_default=sa.text("0"),
            nullable=False,
            comment="是否为该用户该类型的默认配置（运行时取默认那条）",
        ),
        sa.Column(
            "name",
            sa.String(length=100),
            nullable=True,
            comment="配置别名/备注，用于区分同类型多个配置",
        ),
        sa.Column(
            "model_family",
            sa.String(length=32),
            nullable=True,
            comment="模型家族（Midscene VL grounding 必填，如 doubao-seed/qwen3-vl/glm-v；配错=坐标静默偏移。仅 vision 类型使用",
        ),
        sa.Index("ix_user_llm_config_user_id", "user_id"),
        sa.ForeignKeyConstraint(["user_id"], ["sys_user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "sys_user_role",
        sa.Column("user_id", mysql.BIGINT(), nullable=False, comment="用户ID"),
        sa.Column("role_id", mysql.BIGINT(), nullable=False, comment="角色ID"),
        sa.Column("created_by", mysql.BIGINT(), nullable=True, comment="创建人ID"),
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["sys_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["role_id"], ["sys_role.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["sys_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "role_id", name="uk_user_role"),
    )
    with op.batch_alter_table("sys_user_role", schema=None) as batch_op:
        batch_op.create_index("idx_role_id", ["role_id"], unique=False)
        batch_op.create_index("idx_user_id", ["user_id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_sys_user_role_role_id"), ["role_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_sys_user_role_user_id"), ["user_id"], unique=False
        )
    op.create_table(
        "sys_user_token",
        sa.Column("user_id", mysql.BIGINT(), nullable=False, comment="用户ID"),
        sa.Column(
            "token_type",
            mysql.VARCHAR(length=20),
            nullable=False,
            comment="Token类型：access/refresh",
        ),
        sa.Column(
            "token", mysql.VARCHAR(length=500), nullable=False, comment="Token值"
        ),
        sa.Column("expires_at", mysql.BIGINT(), nullable=False, comment="过期时间"),
        sa.Column("revoked", sa.Boolean(), nullable=False, comment="是否已撤销"),
        sa.Column("revoked_at", mysql.BIGINT(), nullable=True, comment="撤销时间"),
        sa.Column(
            "ip_address", mysql.VARCHAR(length=50), nullable=True, comment="创建时的IP"
        ),
        sa.Column(
            "user_agent", mysql.VARCHAR(length=500), nullable=True, comment="用户代理"
        ),
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["sys_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
        sa.UniqueConstraint("token", name="uk_token"),
    )
    with op.batch_alter_table("sys_user_token", schema=None) as batch_op:
        batch_op.create_index("idx_expires_at", ["expires_at"], unique=False)
        batch_op.create_index("idx_user_id", ["user_id"], unique=False)
        batch_op.create_index("idx_user_type", ["user_id", "token_type"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_sys_user_token_expires_at"), ["expires_at"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_sys_user_token_user_id"), ["user_id"], unique=False
        )
    op.create_table(
        "tb_project",
        sa.Column(
            "name", mysql.VARCHAR(length=100), nullable=False, comment="项目名称"
        ),
        sa.Column(
            "code",
            mysql.VARCHAR(length=50),
            nullable=False,
            comment="项目标识（用于URL和API路径）",
        ),
        sa.Column("description", mysql.TEXT(), nullable=True, comment="项目描述"),
        sa.Column(
            "avatar", mysql.VARCHAR(length=255), nullable=True, comment="项目图标URL"
        ),
        sa.Column(
            "status",
            mysql.VARCHAR(length=20),
            nullable=False,
            comment="项目状态：active/archived/deleted",
        ),
        sa.Column("is_public", mysql.TINYINT(), nullable=False, comment="是否公开项目"),
        sa.Column("start_date", sa.Date(), nullable=True, comment="计划开始日期"),
        sa.Column("end_date", sa.Date(), nullable=True, comment="计划结束日期"),
        sa.Column("created_by_id", mysql.BIGINT(), nullable=False, comment="创建者ID"),
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.Column("is_deleted", mysql.TINYINT(), nullable=False, comment="是否删除"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="删除时间"),
        sa.ForeignKeyConstraint(["created_by_id"], ["sys_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_project_code"),
        sa.UniqueConstraint("name", name="uq_project_name"),
    )
    with op.batch_alter_table("tb_project", schema=None) as batch_op:
        batch_op.create_index(
            "idx_status_created", ["status", "created_at"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_tb_project_code"), ["code"], unique=True)
        batch_op.create_index(
            batch_op.f("ix_tb_project_created_by_id"), ["created_by_id"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_tb_project_name"), ["name"], unique=True)
        batch_op.create_index(
            batch_op.f("ix_tb_project_status"), ["status"], unique=False
        )
    op.create_table(
        "ai_task",
        sa.Column("project_id", mysql.BIGINT(), nullable=False, comment="项目ID"),
        sa.Column("created_by", mysql.BIGINT(), nullable=False, comment="发起人ID"),
        sa.Column(
            "task_type",
            mysql.VARCHAR(length=50),
            nullable=False,
            comment="任务类型（registry key）：generate_case/parse_document/...",
        ),
        sa.Column(
            "title", mysql.VARCHAR(length=200), nullable=False, comment="任务展示名"
        ),
        sa.Column(
            "biz_ref_type",
            mysql.VARCHAR(length=50),
            nullable=True,
            comment="业务关联类型：document/requirement/interface...",
        ),
        sa.Column("biz_ref_id", mysql.BIGINT(), nullable=True, comment="业务关联ID"),
        sa.Column(
            "status",
            mysql.VARCHAR(length=20),
            nullable=False,
            comment="状态：pending/running/succeeded/failed/canceled",
        ),
        sa.Column(
            "progress", mysql.INTEGER(), nullable=False, comment="进度百分比（0-100）"
        ),
        sa.Column(
            "current_stage",
            mysql.VARCHAR(length=100),
            nullable=True,
            comment="当前阶段名",
        ),
        sa.Column(
            "stage_index", mysql.INTEGER(), nullable=True, comment="当前第几阶段"
        ),
        sa.Column("total_stages", mysql.INTEGER(), nullable=True, comment="阶段总数"),
        sa.Column(
            "ai_model",
            mysql.VARCHAR(length=100),
            nullable=True,
            comment="使用的 AI 模型",
        ),
        sa.Column(
            "input_params",
            mysql.JSON(),
            nullable=True,
            comment="任务输入参数快照（retry 用）",
        ),
        sa.Column(
            "result_summary",
            mysql.JSON(),
            nullable=True,
            comment="产出摘要（数量/覆盖率等）",
        ),
        sa.Column(
            "result_ref",
            mysql.JSON(),
            nullable=True,
            comment="结果定位（如 {case_ids:[...]}）",
        ),
        sa.Column("error_message", mysql.TEXT(), nullable=True, comment="错误信息"),
        sa.Column(
            "celery_task_id",
            mysql.VARCHAR(length=100),
            nullable=True,
            comment="Celery 任务 ID",
        ),
        sa.Column(
            "heartbeat_at",
            sa.DateTime(),
            nullable=True,
            comment="worker 心跳时间（僵尸巡检用）",
        ),
        sa.Column("started_at", sa.DateTime(), nullable=True, comment="开始时间"),
        sa.Column("completed_at", sa.DateTime(), nullable=True, comment="完成时间"),
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["sys_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["tb_project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("ai_task", schema=None) as batch_op:
        batch_op.create_index(
            "idx_ai_task_biz_ref", ["biz_ref_type", "biz_ref_id"], unique=False
        )
        batch_op.create_index(
            "idx_ai_task_project_status", ["project_id", "status"], unique=False
        )
        batch_op.create_index(
            "idx_ai_task_type_status", ["task_type", "status"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_ai_task_biz_ref_id"), ["biz_ref_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_ai_task_celery_task_id"), ["celery_task_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_ai_task_created_by"), ["created_by"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_ai_task_project_id"), ["project_id"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_ai_task_status"), ["status"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_ai_task_task_type"), ["task_type"], unique=False
        )
    op.create_table(
        "app_device",
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column("agent_id", mysql.BIGINT(), nullable=False, comment="所属执行机ID"),
        sa.Column(
            "serial",
            mysql.VARCHAR(length=128),
            nullable=False,
            comment="adb 设备序列号",
        ),
        sa.Column(
            "udid",
            mysql.VARCHAR(length=160),
            nullable=False,
            comment="平台级设备唯一标识：{agent_id}:{serial}",
        ),
        sa.Column(
            "model",
            mysql.VARCHAR(length=64),
            nullable=True,
            comment="设备型号，如 Pixel 6",
        ),
        sa.Column("brand", mysql.VARCHAR(length=64), nullable=True, comment="品牌"),
        sa.Column(
            "android_version",
            mysql.VARCHAR(length=32),
            nullable=True,
            comment="系统版本（android=Android 版本；harmony=HarmonyOS 版本，字段名历史遗留）",
        ),
        sa.Column(
            "resolution",
            mysql.VARCHAR(length=32),
            nullable=True,
            comment="分辨率，如 1080x2400",
        ),
        sa.Column(
            "source",
            mysql.VARCHAR(length=16),
            server_default=sa.text("'local_adb'"),
            nullable=False,
            comment="接入来源：local_adb/remote_adb",
        ),
        sa.Column(
            "connection",
            mysql.VARCHAR(length=16),
            server_default=sa.text("'usb'"),
            nullable=False,
            comment="连接方式：usb/tcpip",
        ),
        sa.Column(
            "state",
            mysql.VARCHAR(length=16),
            server_default=sa.text("'offline'"),
            nullable=False,
            comment="adb 原始状态：device/offline/unauthorized",
        ),
        sa.Column(
            "project_id",
            mysql.BIGINT(),
            nullable=True,
            comment="归属项目ID（可选，未分配则平台级共享）",
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(),
            nullable=True,
            comment="最近一次在 Agent 心跳/事件中出现的时间",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.Column(
            "platform",
            mysql.VARCHAR(length=16),
            server_default="android",
            nullable=False,
            comment="设备平台：android（adb）/ harmony（鸿蒙 NEXT hdc）",
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["app_agent.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["tb_project.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("app_device", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_app_device_agent_id"), ["agent_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_app_device_project_id"), ["project_id"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_app_device_udid"), ["udid"], unique=True)
    op.create_table(
        "app_script",
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column("project_id", mysql.BIGINT(), nullable=False, comment="所属项目ID"),
        sa.Column(
            "name", mysql.VARCHAR(length=128), nullable=False, comment="用例名称"
        ),
        sa.Column(
            "platform",
            mysql.VARCHAR(length=16),
            nullable=False,
            comment="平台：android（预留 ios/harmony）",
        ),
        sa.Column(
            "target_app",
            mysql.VARCHAR(length=128),
            nullable=True,
            comment="目标应用包名/名称（回放前 launch 用，可空）",
        ),
        sa.Column(
            "description", mysql.VARCHAR(length=500), nullable=True, comment="用例描述"
        ),
        sa.Column(
            "yaml_content",
            sa.Text(),
            nullable=False,
            comment="Midscene YAML（tasks 段为回放输入）",
        ),
        sa.Column(
            "status",
            mysql.VARCHAR(length=16),
            nullable=False,
            comment="状态：draft/active/disabled",
        ),
        sa.Column(
            "created_by", mysql.BIGINT(), nullable=True, comment="创建人（录制者）"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
            comment="更新时间",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["sys_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["tb_project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("app_script", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_app_script_project_id"), ["project_id"], unique=False
        )
    op.create_table(
        "app_suite",
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column("project_id", mysql.BIGINT(), nullable=False, comment="所属项目ID"),
        sa.Column(
            "name", mysql.VARCHAR(length=128), nullable=False, comment="套件名称"
        ),
        sa.Column(
            "description", mysql.VARCHAR(length=500), nullable=True, comment="套件描述"
        ),
        sa.Column(
            "device_udid",
            mysql.VARCHAR(length=160),
            nullable=True,
            comment="默认执行设备 udid（定时触发用；手动执行可覆盖）",
        ),
        sa.Column(
            "failure_strategy",
            mysql.VARCHAR(length=16),
            nullable=False,
            comment="失败策略：continue（单条失败继续）/ stop（遇错中断，余下记跳过）",
        ),
        sa.Column("created_by", mysql.BIGINT(), nullable=True, comment="创建人"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
            comment="更新时间",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["sys_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["tb_project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("app_suite", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_app_suite_project_id"), ["project_id"], unique=False
        )
    op.create_table(
        "chat_conversation",
        sa.Column("project_id", mysql.BIGINT(), nullable=False, comment="项目ID"),
        sa.Column(
            "title", mysql.VARCHAR(length=255), nullable=False, comment="对话标题"
        ),
        sa.Column(
            "status",
            mysql.VARCHAR(length=20),
            nullable=False,
            comment="状态：active/completed/archived",
        ),
        sa.Column("created_by", mysql.BIGINT(), nullable=False, comment="创建人ID"),
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["sys_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["tb_project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("chat_conversation", schema=None) as batch_op:
        batch_op.create_index(
            "idx_chat_conv_project_status", ["project_id", "status"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_chat_conversation_created_by"), ["created_by"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_chat_conversation_project_id"), ["project_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_chat_conversation_status"), ["status"], unique=False
        )
    op.create_table(
        "func_project_document",
        sa.Column("project_id", mysql.BIGINT(), nullable=False, comment="项目ID"),
        sa.Column(
            "name",
            mysql.VARCHAR(length=200),
            nullable=False,
            comment="文档名称（用户自定义）",
        ),
        sa.Column(
            "doc_type",
            mysql.VARCHAR(length=20),
            nullable=False,
            comment="文档类型：requirement/prototype/db_dict/other",
        ),
        sa.Column(
            "file_name", mysql.VARCHAR(length=255), nullable=False, comment="原始文件名"
        ),
        sa.Column(
            "file_path",
            mysql.VARCHAR(length=500),
            nullable=False,
            comment="存储路径（本地相对路径或 COS key）",
        ),
        sa.Column(
            "file_size", mysql.BIGINT(), nullable=False, comment="文件大小（字节）"
        ),
        sa.Column(
            "file_ext", mysql.VARCHAR(length=20), nullable=False, comment="文件扩展名"
        ),
        sa.Column("description", mysql.TEXT(), nullable=True, comment="文档描述"),
        sa.Column("version", mysql.VARCHAR(length=50), nullable=True, comment="版本号"),
        sa.Column(
            "status",
            mysql.VARCHAR(length=20),
            nullable=False,
            comment="状态：active/deleted",
        ),
        sa.Column("uploaded_by", mysql.BIGINT(), nullable=False, comment="上传人ID"),
        sa.Column(
            "parse_status",
            mysql.VARCHAR(length=20),
            nullable=False,
            comment="AI 解析状态：pending/parsing/parsed/failed",
        ),
        sa.Column(
            "parsed_content",
            mysql.LONGTEXT(),
            nullable=True,
            comment="AI 解析后的 Markdown 内容（适合 LightRAG 检索）",
        ),
        sa.Column(
            "parsed_at", sa.DateTime(), nullable=True, comment="最后解析完成时间"
        ),
        sa.Column(
            "parse_error_message", mysql.TEXT(), nullable=True, comment="解析失败原因"
        ),
        sa.Column(
            "kb_status",
            mysql.VARCHAR(length=20),
            nullable=False,
            comment="知识库入库状态：not_ingested/ingesting/ingested/ingest_failed",
        ),
        sa.Column(
            "kb_ingested_at", sa.DateTime(), nullable=True, comment="最后入库时间"
        ),
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.Column("is_deleted", mysql.TINYINT(), nullable=False, comment="是否删除"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="删除时间"),
        sa.Column(
            "kb_document_id",
            mysql.BIGINT(),
            nullable=True,
            comment="自研知识库文档 ID（kb_document.id，入库桥接回写；无 FK：跨模块软引用）",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["tb_project.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["sys_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("func_project_document", schema=None) as batch_op:
        batch_op.create_index(
            "idx_func_doc_project_type", ["project_id", "doc_type"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_func_project_document_doc_type"), ["doc_type"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_func_project_document_kb_document_id"),
            ["kb_document_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_func_project_document_kb_status"),
            ["kb_status"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_func_project_document_parse_status"),
            ["parse_status"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_func_project_document_project_id"),
            ["project_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_func_project_document_status"), ["status"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_func_project_document_uploaded_by"),
            ["uploaded_by"],
            unique=False,
        )
    op.create_table(
        "kb_document",
        sa.Column("project_id", mysql.BIGINT(), nullable=False, comment="项目ID"),
        sa.Column(
            "file_name", mysql.VARCHAR(length=255), nullable=False, comment="原始文件名"
        ),
        sa.Column(
            "file_size", mysql.BIGINT(), nullable=False, comment="文件大小（字节）"
        ),
        sa.Column(
            "file_ext", mysql.VARCHAR(length=20), nullable=False, comment="文件扩展名"
        ),
        sa.Column(
            "storage_key",
            mysql.VARCHAR(length=500),
            nullable=True,
            comment="原件存储路径（本地/COS）。新流程应用层必填；存量 LightRAG 行恒 NULL 故列可空",
        ),
        sa.Column(
            "status",
            mysql.VARCHAR(length=20),
            nullable=False,
            comment="状态：pending/parsing/chunking/embedding/ready/failed/deleted（任务事件驱动）",
        ),
        sa.Column("error_message", mysql.TEXT(), nullable=True, comment="错误信息"),
        sa.Column("uploaded_by", mysql.BIGINT(), nullable=False, comment="上传人ID"),
        sa.Column(
            "processed_at", sa.DateTime(), nullable=True, comment="最近一次入库完成时间"
        ),
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.Column(
            "doc_type",
            mysql.VARCHAR(length=30),
            server_default=sa.text("'other'"),
            nullable=False,
            comment="文档类型：requirement/api_doc/design/test_case/bug_review/meeting/other",
        ),
        sa.Column(
            "source_type",
            mysql.VARCHAR(length=30),
            server_default=sa.text("'upload'"),
            nullable=False,
            comment="来源：upload/text/func_doc/entity",
        ),
        sa.Column(
            "source_id",
            mysql.BIGINT(),
            nullable=True,
            comment="来源实体ID（func_doc→func_project_document.id；upload/text 为 NULL）",
        ),
        sa.Column(
            "content_md",
            mysql.LONGTEXT(),
            nullable=True,
            comment="解析产物 Markdown（重分块/重嵌入数据源；func_doc 源直取 parsed_content 时也回填）",
        ),
        sa.Column(
            "content_hash",
            mysql.VARCHAR(length=64),
            nullable=True,
            comment="content_md 的 SHA256（幂等/去重键）",
        ),
        sa.Column(
            "version",
            mysql.INTEGER(),
            server_default=sa.text("1"),
            nullable=False,
            comment="版本号（P1a 显式替换上传时 +1）",
        ),
        sa.Column(
            "validity",
            mysql.VARCHAR(length=20),
            server_default=sa.text("'effective'"),
            nullable=False,
            comment="生效性：effective/deprecated（deprecated 的 chunk 已物理删除）",
        ),
        sa.Column(
            "parse_mode",
            mysql.VARCHAR(length=20),
            nullable=True,
            comment="解析模式：raw=确定性提取 / llm_normalized=LLM 规整（引用忠实性标注）",
        ),
        sa.Column(
            "truncated",
            sa.Boolean(),
            server_default=sa.text("0"),
            nullable=False,
            comment="解析是否发生截断（用户可见,不静默丢内容）",
        ),
        sa.Column(
            "chunk_count",
            mysql.INTEGER(),
            server_default=sa.text("0"),
            nullable=False,
            comment="分块数（index 节点回写）",
        ),
        sa.Column(
            "ai_task_id",
            mysql.BIGINT(),
            nullable=True,
            comment="最近一次入库任务ID（统一壳执行，前端跳任务详情/SSE；无 FK：ai_task 生命周期独立）",
        ),
        sa.Column(
            "graph_status",
            mysql.VARCHAR(length=20),
            server_default=sa.text("'none'"),
            nullable=False,
            comment="图谱抽取状态：none/pending/extracting/extracted/failed/skipped（独立于主 status）",
        ),
        sa.Column(
            "graph_task_id",
            mysql.BIGINT(),
            nullable=True,
            comment="最近一次图谱抽取任务ID（无 FK）",
        ),
        sa.Column(
            "graph_source_hash",
            mysql.VARCHAR(length=64),
            nullable=True,
            comment="最近一次成功抽取时的 sha256(content_md)（增量短路键：hash 未变跳过重抽）",
        ),
        sa.Column(
            "entity_count",
            mysql.INTEGER(),
            server_default=sa.text("0"),
            nullable=False,
            comment="本文档贡献实体数（finalize 回写）",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["tb_project.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["sys_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("kb_document", schema=None) as batch_op:
        batch_op.create_index(
            "idx_kb_doc_project_hash", ["project_id", "content_hash"], unique=False
        )
        batch_op.create_index(
            "idx_kb_doc_project_status", ["project_id", "status"], unique=False
        )
        batch_op.create_index(
            "idx_kb_doc_project_type", ["project_id", "doc_type"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_kb_document_ai_task_id"), ["ai_task_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_kb_document_project_id"), ["project_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_kb_document_status"), ["status"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_kb_document_uploaded_by"), ["uploaded_by"], unique=False
        )
    op.create_table(
        "kb_project_knowledge_base",
        sa.Column("project_id", mysql.BIGINT(), nullable=False, comment="项目ID"),
        sa.Column(
            "status",
            mysql.VARCHAR(length=20),
            nullable=False,
            comment="状态：empty/ready/rebuilding/error",
        ),
        sa.Column(
            "total_documents",
            mysql.INTEGER(),
            nullable=False,
            comment="文档总数（本项目真实口径）",
        ),
        sa.Column(
            "total_chunks",
            mysql.INTEGER(),
            nullable=False,
            comment="chunk 总数（本项目真实口径，SQL 原子增量维护）",
        ),
        sa.Column(
            "total_nodes",
            mysql.INTEGER(),
            nullable=False,
            comment="知识图谱实体数（P1b kb_extract 维护，本项目口径）",
        ),
        sa.Column(
            "total_edges",
            mysql.INTEGER(),
            nullable=False,
            comment="知识图谱关系数（P1b kb_extract 维护，本项目口径）",
        ),
        sa.Column(
            "project_summary",
            mysql.TEXT(),
            nullable=True,
            comment="项目概要（AI 提炼）",
        ),
        sa.Column("error_message", mysql.TEXT(), nullable=True, comment="错误信息"),
        sa.Column(
            "last_built_at", sa.DateTime(), nullable=True, comment="最近一次构建时间"
        ),
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.Column(
            "embed_provider",
            mysql.VARCHAR(length=50),
            nullable=True,
            comment="钉定 embed 提供方（openai 兼容）",
        ),
        sa.Column(
            "embed_model",
            mysql.VARCHAR(length=200),
            nullable=True,
            comment="钉定 embed 模型名（换模型=全量重建）",
        ),
        sa.Column(
            "embed_base_url",
            mysql.VARCHAR(length=500),
            nullable=True,
            comment="钉定 embed base_url",
        ),
        sa.Column(
            "embed_dim",
            mysql.INTEGER(),
            nullable=True,
            comment="向量维度（首绑探针实测钉死，每批断言）",
        ),
        sa.Column(
            "embed_bound_by",
            mysql.BIGINT(),
            nullable=True,
            comment="钉定来源用户（api_key 实时从其 UserLlmConfig 读，轮换 key 免重建）",
        ),
        sa.Column("embed_bound_at", sa.DateTime(), nullable=True, comment="钉定时间"),
        sa.Column(
            "embed_status",
            mysql.VARCHAR(length=20),
            server_default=sa.text("'active'"),
            nullable=False,
            comment="embed 配置状态：active/invalid（invalid=来源配置失效，检索降级纯全文）",
        ),
        sa.Column(
            "index_version",
            mysql.INTEGER(),
            server_default=sa.text("0"),
            nullable=False,
            comment="索引版本（chunk 任何写路径 +1，检索向量缓存失效键）",
        ),
        sa.Column(
            "settings",
            mysql.JSON(),
            nullable=True,
            comment="库级参数（分块/检索开关等，缺省用全局常量）",
        ),
        sa.Column(
            "graph_doc_types",
            mysql.VARCHAR(length=200),
            server_default=sa.text("'requirement,design,api_doc'"),
            nullable=False,
            comment="图谱自动抽取 doc_type 白名单（逗号分隔；入库完成后按此派发 kb_extract）",
        ),
        sa.ForeignKeyConstraint(
            ["embed_bound_by"],
            ["sys_user.id"],
            ondelete="SET NULL",
            name="fk_kb_embed_bound_by_user",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["tb_project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_kb_project"),
    )
    with op.batch_alter_table("kb_project_knowledge_base", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_kb_project_knowledge_base_project_id"),
            ["project_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_kb_project_knowledge_base_status"), ["status"], unique=False
        )
    op.create_table(
        "kb_relation",
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "project_id", mysql.BIGINT(), nullable=False, comment="项目ID（硬隔离列）"
        ),
        sa.Column(
            "source_entity_id", mysql.BIGINT(), nullable=False, comment="源实体ID"
        ),
        sa.Column(
            "target_entity_id", mysql.BIGINT(), nullable=False, comment="目标实体ID"
        ),
        sa.Column(
            "keywords",
            mysql.VARCHAR(length=200),
            server_default=sa.text("''"),
            nullable=False,
            comment="关系关键词（开放词，展示为边标签）",
        ),
        sa.Column("description", mysql.TEXT(), nullable=True, comment="关系描述"),
        sa.Column(
            "weight",
            sa.Float(),
            server_default=sa.text("1"),
            nullable=False,
            comment="权重（重复抽取递增，前端映射边宽）",
        ),
        sa.Column(
            "ref_count",
            mysql.INTEGER(),
            server_default=sa.text("0"),
            nullable=False,
            comment="引用计数（台账重算）",
        ),
        sa.Column(
            "human_edited",
            sa.Boolean(),
            server_default=sa.text("0"),
            nullable=False,
            comment="手工编辑保护位（同实体语义）",
        ),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            server_default=sa.text("0"),
            nullable=False,
            comment="软删墓碑（防自动抽取复活）",
        ),
        sa.Column(
            "created_by",
            mysql.BIGINT(),
            nullable=True,
            comment="非空=手工创建，永不 GC",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["sys_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["source_entity_id"], ["kb_entity.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["target_entity_id"], ["kb_entity.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_entity_id", "target_entity_id", name="uq_kb_relation_pair"
        ),
    )
    with op.batch_alter_table("kb_relation", schema=None) as batch_op:
        batch_op.create_index("idx_kb_relation_project", ["project_id"], unique=False)
        batch_op.create_index(
            "idx_kb_relation_source", ["source_entity_id"], unique=False
        )
        batch_op.create_index(
            "idx_kb_relation_target", ["target_entity_id"], unique=False
        )
    op.create_table(
        "sys_scheduled_job",
        sa.Column("project_id", mysql.BIGINT(), nullable=False, comment="项目ID"),
        sa.Column(
            "name", mysql.VARCHAR(length=100), nullable=False, comment="计划名称"
        ),
        sa.Column(
            "description", mysql.VARCHAR(length=500), nullable=True, comment="描述"
        ),
        sa.Column(
            "job_type",
            mysql.VARCHAR(length=30),
            nullable=False,
            comment="执行对象类型：app_suite",
        ),
        sa.Column(
            "target_id",
            mysql.BIGINT(),
            nullable=False,
            comment="执行对象ID（App 套件）",
        ),
        sa.Column(
            "params",
            mysql.JSON(),
            nullable=True,
            comment="执行参数：{environment_id, run_mode, ...}",
        ),
        sa.Column(
            "schedule_type",
            mysql.VARCHAR(length=10),
            nullable=False,
            comment="调度方式：cron/interval",
        ),
        sa.Column(
            "cron_expr",
            mysql.VARCHAR(length=100),
            nullable=True,
            comment="5 段 cron 表达式（按本地时区语义）",
        ),
        sa.Column(
            "interval_seconds",
            mysql.INTEGER(),
            nullable=True,
            comment="固定间隔秒数（interval 模式）",
        ),
        sa.Column("enabled", sa.BOOLEAN(), nullable=False, comment="是否启用"),
        sa.Column(
            "allow_overlap",
            sa.BOOLEAN(),
            nullable=False,
            comment="上次执行未完成时是否允许并行触发",
        ),
        sa.Column(
            "next_run_at",
            sa.DateTime(),
            nullable=True,
            comment="下次运行时间（UTC，派发扫描键）",
        ),
        sa.Column(
            "last_run_at",
            sa.DateTime(),
            nullable=True,
            comment="最近一次派发时间（UTC）",
        ),
        sa.Column(
            "last_status",
            mysql.VARCHAR(length=20),
            nullable=True,
            comment="最近一次派发结果：dispatched/skipped/failed",
        ),
        sa.Column(
            "last_task_id",
            mysql.BIGINT(),
            nullable=True,
            comment="最近一次派发的 ai_task ID",
        ),
        sa.Column(
            "total_runs", mysql.INTEGER(), nullable=False, comment="累计派发次数"
        ),
        sa.Column(
            "created_by",
            mysql.BIGINT(),
            nullable=False,
            comment="创建人ID（派发任务以此身份执行）",
        ),
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.Column("is_deleted", mysql.TINYINT(), nullable=False, comment="是否删除"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="删除时间"),
        sa.ForeignKeyConstraint(["created_by"], ["sys_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["tb_project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("sys_scheduled_job", schema=None) as batch_op:
        batch_op.create_index(
            "idx_sched_job_due", ["enabled", "next_run_at"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_sys_scheduled_job_project_id"), ["project_id"], unique=False
        )
    op.create_table(
        "tb_project_config",
        sa.Column("project_id", mysql.BIGINT(), nullable=False, comment="项目ID"),
        sa.Column(
            "default_env_id", mysql.BIGINT(), nullable=True, comment="默认测试环境ID"
        ),
        sa.Column(
            "bug_auto_assign",
            mysql.TINYINT(),
            nullable=False,
            comment="Bug是否自动分配给创建者",
        ),
        sa.Column(
            "bug_severity_default",
            mysql.VARCHAR(length=20),
            nullable=False,
            comment="Bug默认严重程度：critical/high/medium/low/trivial",
        ),
        sa.Column(
            "test_case_priority_default",
            mysql.VARCHAR(length=20),
            nullable=False,
            comment="用例默认优先级：critical/high/medium/low",
        ),
        sa.Column(
            "allow_public_report",
            mysql.TINYINT(),
            nullable=False,
            comment="是否允许公开查看测试报告",
        ),
        sa.Column(
            "retention_days",
            mysql.INTEGER(),
            nullable=False,
            comment="数据保留天数（归档后）",
        ),
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["tb_project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_config_project"),
    )
    with op.batch_alter_table("tb_project_config", schema=None) as batch_op:
        batch_op.create_index(
            "idx_project_env", ["project_id", "default_env_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_tb_project_config_project_id"), ["project_id"], unique=True
        )
    op.create_table(
        "tb_project_member",
        sa.Column("project_id", mysql.BIGINT(), nullable=False, comment="项目ID"),
        sa.Column("user_id", mysql.BIGINT(), nullable=False, comment="用户ID"),
        sa.Column(
            "project_role_id",
            mysql.BIGINT(),
            nullable=False,
            comment="项目角色ID（关联 sys_role 表）",
        ),
        sa.Column(
            "last_active_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="最后活跃时间",
        ),
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["tb_project.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["project_role_id"], ["sys_role.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["sys_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_user"),
    )
    with op.batch_alter_table("tb_project_member", schema=None) as batch_op:
        batch_op.create_index(
            "idx_project_role", ["project_id", "project_role_id"], unique=False
        )
        batch_op.create_index(
            "idx_user_project", ["user_id", "project_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_tb_project_member_project_id"), ["project_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_tb_project_member_project_role_id"),
            ["project_role_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_tb_project_member_user_id"), ["user_id"], unique=False
        )
    op.create_table(
        "tb_project_module",
        sa.Column(
            "name", mysql.VARCHAR(length=100), nullable=False, comment="模块名称"
        ),
        sa.Column("parent_id", mysql.BIGINT(), nullable=True, comment="父模块ID"),
        sa.Column("project_id", mysql.BIGINT(), nullable=False, comment="所属项目ID"),
        sa.Column("sort_order", mysql.INTEGER(), nullable=False, comment="排序顺序"),
        sa.Column("description", mysql.TEXT(), nullable=True, comment="模块描述"),
        sa.Column(
            "module_type",
            mysql.VARCHAR(length=20),
            nullable=False,
            comment="模块类型：feature/business/interface/page",
        ),
        sa.Column("level", mysql.INTEGER(), nullable=False, comment="层级深度（1-5）"),
        sa.Column(
            "path",
            mysql.VARCHAR(length=500),
            nullable=True,
            comment="模块路径（如：用户模块/登录注册）",
        ),
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.CheckConstraint("level >= 1 AND level <= 5", name="ck_module_level"),
        sa.CheckConstraint("sort_order >= 0", name="ck_module_sort_order"),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["tb_project_module.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["tb_project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("tb_project_module", schema=None) as batch_op:
        batch_op.create_index(
            "idx_project_parent", ["project_id", "parent_id"], unique=False
        )
        batch_op.create_index(
            "idx_project_sort", ["project_id", "sort_order"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_tb_project_module_parent_id"), ["parent_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_tb_project_module_project_id"), ["project_id"], unique=False
        )
    op.create_table(
        "test_database",
        sa.Column("project_id", mysql.BIGINT(), nullable=False, comment="项目ID"),
        sa.Column(
            "name", mysql.VARCHAR(length=100), nullable=False, comment="连接名称"
        ),
        sa.Column(
            "db_type",
            mysql.VARCHAR(length=20),
            nullable=False,
            comment="数据库类型：MySQL/PostgreSQL/Oracle/SQLServer/MongoDB/Redis",
        ),
        sa.Column(
            "host", mysql.VARCHAR(length=255), nullable=False, comment="数据库地址"
        ),
        sa.Column("port", sa.Integer(), nullable=False, comment="端口号"),
        sa.Column(
            "database", mysql.VARCHAR(length=100), nullable=False, comment="数据库名"
        ),
        sa.Column(
            "username", mysql.VARCHAR(length=100), nullable=False, comment="用户名"
        ),
        sa.Column(
            "password",
            mysql.VARCHAR(length=255),
            nullable=False,
            comment="密码（AES-256加密）",
        ),
        sa.Column(
            "charset",
            mysql.VARCHAR(length=20),
            nullable=True,
            comment="字符集，默认utf8mb4",
        ),
        sa.Column(
            "connection_params",
            mysql.JSON(),
            nullable=True,
            comment="额外连接参数（JSON）",
        ),
        sa.Column(
            "connection_status",
            mysql.VARCHAR(length=20),
            nullable=False,
            comment="连接状态：connected/disconnected/unknown",
        ),
        sa.Column(
            "last_test_time", mysql.BIGINT(), nullable=True, comment="最后测试连接时间"
        ),
        sa.Column(
            "last_test_result",
            mysql.VARCHAR(length=500),
            nullable=True,
            comment="最后测试结果",
        ),
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.Column("is_deleted", mysql.TINYINT(), nullable=False, comment="是否删除"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="删除时间"),
        sa.Column(
            "allow_write",
            sa.Boolean(),
            server_default="0",
            nullable=False,
            comment="是否允许写操作（造数/清理等破坏性 SQL），默认关闭",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["tb_project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("test_database", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_test_database_db_type"), ["db_type"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_test_database_project_id"), ["project_id"], unique=False
        )
    op.create_table(
        "test_environment",
        sa.Column("project_id", mysql.BIGINT(), nullable=False, comment="项目ID"),
        sa.Column(
            "name", mysql.VARCHAR(length=100), nullable=False, comment="环境名称"
        ),
        sa.Column(
            "base_url", mysql.VARCHAR(length=500), nullable=False, comment="环境基础URL"
        ),
        sa.Column(
            "description", mysql.VARCHAR(length=500), nullable=True, comment="环境描述"
        ),
        sa.Column(
            "env_type",
            sa.SmallInteger(),
            nullable=False,
            comment="环境类型: 1=功能测试 2=App测试",
        ),
        sa.Column("is_default", sa.Boolean(), nullable=False, comment="是否默认环境"),
        sa.Column(
            "is_global",
            sa.Boolean(),
            nullable=False,
            comment="是否全局环境（所有项目可用）",
        ),
        sa.Column(
            "proxy_url", mysql.VARCHAR(length=500), nullable=True, comment="代理URL"
        ),
        sa.Column(
            "timeout", sa.Integer(), nullable=False, comment="请求超时时间（秒）"
        ),
        sa.Column(
            "pre_script", sa.Text(), nullable=True, comment="前置脚本（JSON格式）"
        ),
        sa.Column(
            "post_script", sa.Text(), nullable=True, comment="后置脚本（JSON格式）"
        ),
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.Column("is_deleted", mysql.TINYINT(), nullable=False, comment="是否删除"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="删除时间"),
        sa.Column(
            "verify_ssl",
            sa.Boolean(),
            server_default="1",
            nullable=False,
            comment="是否校验 HTTPS 证书（自签测试环境可关）",
        ),
        sa.Column(
            "allow_redirects",
            sa.Boolean(),
            server_default="1",
            nullable=False,
            comment="是否跟随重定向（关掉可断言 3xx）",
        ),
        sa.Column(
            "keep_cookies",
            sa.Boolean(),
            server_default="0",
            nullable=False,
            comment="是否保持 Cookie 会话（登录后续用例复用 Set-Cookie）",
        ),
        sa.Column(
            "retry_times",
            sa.Integer(),
            server_default="1",
            nullable=False,
            comment="连接类异常自动重试次数",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["tb_project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("test_environment", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_test_environment_is_global"), ["is_global"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_test_environment_project_id"), ["project_id"], unique=False
        )
    op.create_table(
        "test_global_function",
        sa.Column(
            "project_id",
            mysql.BIGINT(),
            nullable=True,
            comment="项目ID，NULL表示全局函数",
        ),
        sa.Column(
            "name",
            mysql.VARCHAR(length=100),
            nullable=False,
            comment="函数名称（调用标识）",
        ),
        sa.Column(
            "display_name",
            mysql.VARCHAR(length=100),
            nullable=False,
            comment="函数显示名称",
        ),
        sa.Column(
            "language",
            mysql.VARCHAR(length=20),
            nullable=False,
            comment="编程语言：python/javascript",
        ),
        sa.Column("code", sa.Text(), nullable=False, comment="函数代码"),
        sa.Column("description", sa.Text(), nullable=True, comment="函数描述"),
        sa.Column(
            "params", mysql.JSON(), nullable=True, comment="参数说明（JSON数组）"
        ),
        sa.Column(
            "return_type", mysql.VARCHAR(length=50), nullable=True, comment="返回值类型"
        ),
        sa.Column(
            "example", mysql.VARCHAR(length=500), nullable=True, comment="使用示例"
        ),
        sa.Column("is_built_in", sa.Boolean(), nullable=False, comment="是否内置函数"),
        sa.Column("is_active", sa.Boolean(), nullable=False, comment="是否启用"),
        sa.Column("created_by", mysql.BIGINT(), nullable=True, comment="创建人ID"),
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.Column("is_deleted", mysql.TINYINT(), nullable=False, comment="是否删除"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="删除时间"),
        sa.ForeignKeyConstraint(["created_by"], ["sys_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["tb_project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("test_global_function", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_test_global_function_is_active"), ["is_active"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_test_global_function_is_built_in"),
            ["is_built_in"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_test_global_function_project_id"),
            ["project_id"],
            unique=False,
        )
    op.create_table(
        "ai_task_event",
        sa.Column("task_id", mysql.BIGINT(), nullable=False, comment="所属 AI 任务ID"),
        sa.Column(
            "seq",
            mysql.INTEGER(),
            nullable=False,
            comment="任务内单调序号（SSE Last-Event-ID）",
        ),
        sa.Column(
            "event_type",
            mysql.VARCHAR(length=20),
            nullable=False,
            comment="事件类型：stage/progress/log/message_delta/result/...",
        ),
        sa.Column("payload", mysql.JSON(), nullable=True, comment="事件数据体"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.ForeignKeyConstraint(["task_id"], ["ai_task.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("ai_task_event", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_ai_task_event_event_type"), ["event_type"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_ai_task_event_task_id"), ["task_id"], unique=False
        )
        batch_op.create_index(
            "uq_ai_task_event_task_seq", ["task_id", "seq"], unique=True
        )
    op.create_table(
        "app_suite_case",
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column("suite_id", mysql.BIGINT(), nullable=False, comment="套件ID"),
        sa.Column("script_id", mysql.BIGINT(), nullable=False, comment="用例ID"),
        sa.Column(
            "sort_order", mysql.INTEGER(), nullable=False, comment="执行顺序（升序）"
        ),
        sa.Column("enabled", sa.BOOLEAN(), nullable=False, comment="是否参与执行"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
            comment="更新时间",
        ),
        sa.ForeignKeyConstraint(["script_id"], ["app_script.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["suite_id"], ["app_suite.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("suite_id", "script_id", name="uk_app_suite_script"),
    )
    with op.batch_alter_table("app_suite_case", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_app_suite_case_script_id"), ["script_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_app_suite_case_suite_id"), ["suite_id"], unique=False
        )
    op.create_table(
        "app_suite_execution",
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column("suite_id", mysql.BIGINT(), nullable=False, comment="套件ID"),
        sa.Column(
            "project_id",
            mysql.BIGINT(),
            nullable=False,
            comment="项目ID（免 join 列表）",
        ),
        sa.Column(
            "ai_task_id",
            mysql.VARCHAR(length=64),
            nullable=True,
            comment="统一任务框架 task_id（事件流/进度经 ai_task_event 回放）",
        ),
        sa.Column(
            "device_udid",
            mysql.VARCHAR(length=160),
            nullable=False,
            comment="执行设备 udid（{agent_id}:{serial}）",
        ),
        sa.Column(
            "trigger_type",
            mysql.VARCHAR(length=16),
            nullable=False,
            comment="触发方式：manual/scheduled",
        ),
        sa.Column(
            "status",
            mysql.VARCHAR(length=16),
            nullable=False,
            comment="状态：pending/running/success/failed/cancelled",
        ),
        sa.Column(
            "total_cases",
            mysql.INTEGER(),
            nullable=False,
            comment="参与执行的用例总数（enabled）",
        ),
        sa.Column("passed_count", mysql.INTEGER(), nullable=False, comment="通过数"),
        sa.Column("failed_count", mysql.INTEGER(), nullable=False, comment="失败数"),
        sa.Column(
            "skipped_count",
            mysql.INTEGER(),
            nullable=False,
            comment="跳过数（stop 策略中断/取消后未执行的余量）",
        ),
        sa.Column(
            "error",
            mysql.VARCHAR(length=500),
            nullable=True,
            comment="套件级错误信息（抢锁失败/设备离线等；单条失败看用例级记录）",
        ),
        sa.Column(
            "duration_ms", mysql.INTEGER(), nullable=True, comment="总耗时（毫秒）"
        ),
        sa.Column(
            "created_by",
            mysql.BIGINT(),
            nullable=True,
            comment="触发人（定时触发=计划创建人）",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
            comment="更新时间",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["sys_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["tb_project.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["suite_id"], ["app_suite.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("app_suite_execution", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_app_suite_execution_ai_task_id"),
            ["ai_task_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_app_suite_execution_project_id"),
            ["project_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_app_suite_execution_suite_id"), ["suite_id"], unique=False
        )
    op.create_table(
        "bug",
        sa.Column("project_id", mysql.BIGINT(), nullable=False, comment="项目ID"),
        sa.Column(
            "bug_key",
            mysql.VARCHAR(length=50),
            nullable=False,
            comment="Bug编号，格式：BUG-{YYYYMMDD}-{序号4位}",
        ),
        sa.Column(
            "title", mysql.VARCHAR(length=255), nullable=False, comment="Bug标题"
        ),
        sa.Column("description", mysql.TEXT(), nullable=False, comment="Bug详细描述"),
        sa.Column(
            "severity",
            mysql.VARCHAR(length=20),
            nullable=False,
            comment="严重程度：critical/major/moderate/minor/trivial",
        ),
        sa.Column(
            "priority",
            mysql.VARCHAR(length=20),
            nullable=False,
            comment="优先级：urgent/high/medium/low",
        ),
        sa.Column(
            "status",
            mysql.VARCHAR(length=20),
            nullable=False,
            comment="状态：new/assigned/in_progress/resolved/verified/reopened/closed/postponed/wontfix",
        ),
        sa.Column("module_id", mysql.BIGINT(), nullable=True, comment="关联模块ID"),
        sa.Column(
            "test_case_id", mysql.BIGINT(), nullable=True, comment="关联测试用例ID"
        ),
        sa.Column(
            "test_case_type",
            mysql.VARCHAR(length=20),
            nullable=True,
            comment="用例类型：functional/api/web",
        ),
        sa.Column(
            "assigned_to", mysql.BIGINT(), nullable=True, comment="指派给谁（用户ID）"
        ),
        sa.Column(
            "environment",
            mysql.VARCHAR(length=100),
            nullable=True,
            comment="发现环境描述",
        ),
        sa.Column(
            "reproduction_steps", mysql.TEXT(), nullable=True, comment="复现步骤"
        ),
        sa.Column("expected_result", mysql.TEXT(), nullable=True, comment="预期结果"),
        sa.Column("actual_result", mysql.TEXT(), nullable=True, comment="实际结果"),
        sa.Column(
            "external_bug_key",
            mysql.VARCHAR(length=100),
            nullable=True,
            comment="外部系统Bug编号（如Jira）",
        ),
        sa.Column("tags", mysql.JSON(), nullable=True, comment="标签列表（JSON数组）"),
        sa.Column("is_archived", sa.Boolean(), nullable=False, comment="是否已归档"),
        sa.Column("created_by", mysql.BIGINT(), nullable=False, comment="创建人ID"),
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.Column("is_deleted", mysql.TINYINT(), nullable=False, comment="是否删除"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="删除时间"),
        sa.ForeignKeyConstraint(["assigned_to"], ["sys_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["sys_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["module_id"], ["tb_project_module.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["tb_project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bug_key", name="uk_bug_key"),
    )
    with op.batch_alter_table("bug", schema=None) as batch_op:
        batch_op.create_index("idx_bug_assigned_to", ["assigned_to"], unique=False)
        batch_op.create_index("idx_bug_deleted_at", ["deleted_at"], unique=False)
        batch_op.create_index(
            "idx_bug_external_key", ["external_bug_key"], unique=False
        )
        batch_op.create_index("idx_bug_module_id", ["module_id"], unique=False)
        batch_op.create_index("idx_bug_priority", ["priority"], unique=False)
        batch_op.create_index(
            "idx_bug_project_status", ["project_id", "status"], unique=False
        )
        batch_op.create_index("idx_bug_severity", ["severity"], unique=False)
        batch_op.create_index("idx_bug_test_case_id", ["test_case_id"], unique=False)
    op.create_table(
        "chat_message",
        sa.Column("conversation_id", mysql.BIGINT(), nullable=False, comment="会话ID"),
        sa.Column(
            "role",
            mysql.VARCHAR(length=20),
            nullable=False,
            comment="角色：user/assistant/system",
        ),
        sa.Column("content", mysql.TEXT(), nullable=False, comment="消息文本内容"),
        sa.Column(
            "tool_calls",
            mysql.JSON(),
            nullable=True,
            comment="工具调用记录列表（runId/toolName/toolInput/toolOutput/status/...）",
        ),
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["chat_conversation.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("chat_message", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_chat_message_conversation_id"),
            ["conversation_id"],
            unique=False,
        )
    op.create_table(
        "func_test_requirement",
        sa.Column("project_id", mysql.BIGINT(), nullable=False, comment="项目ID"),
        sa.Column("code", mysql.VARCHAR(length=50), nullable=True, comment="需求编号"),
        sa.Column(
            "title", mysql.VARCHAR(length=200), nullable=False, comment="需求标题"
        ),
        sa.Column("module_id", mysql.BIGINT(), nullable=True, comment="所属模块ID"),
        sa.Column(
            "priority",
            mysql.VARCHAR(length=20),
            nullable=False,
            comment="优先级：urgent/high/medium/low",
        ),
        sa.Column(
            "status",
            mysql.VARCHAR(length=30),
            nullable=False,
            comment="状态：draft/pending_review/reviewed/published/deprecated",
        ),
        sa.Column(
            "description", mysql.TEXT(), nullable=True, comment="需求描述（Markdown）"
        ),
        sa.Column(
            "acceptance_criteria", mysql.TEXT(), nullable=True, comment="验收标准"
        ),
        sa.Column(
            "understood_content",
            mysql.TEXT(),
            nullable=True,
            comment="AI 需求理解结果（VLM + LLM 整理后的 Markdown）",
        ),
        sa.Column(
            "attachments", mysql.JSON(), nullable=True, comment="附件图片URL列表"
        ),
        sa.Column(
            "source",
            mysql.VARCHAR(length=20),
            nullable=False,
            comment="来源：manual/ai_generated",
        ),
        sa.Column("document_id", mysql.BIGINT(), nullable=True, comment="来源文档ID"),
        sa.Column(
            "review_comment",
            mysql.VARCHAR(length=500),
            nullable=True,
            comment="审核意见",
        ),
        sa.Column("reviewed_by", mysql.BIGINT(), nullable=True, comment="审核人ID"),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True, comment="审核时间"),
        sa.Column("created_by", mysql.BIGINT(), nullable=False, comment="创建人ID"),
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.Column("is_deleted", mysql.TINYINT(), nullable=False, comment="是否删除"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="删除时间"),
        sa.ForeignKeyConstraint(["created_by"], ["sys_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["document_id"], ["func_project_document.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["module_id"], ["tb_project_module.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["tb_project.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["sys_user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "code", name="uq_func_req_project_code"),
    )
    with op.batch_alter_table("func_test_requirement", schema=None) as batch_op:
        batch_op.create_index("idx_func_req_source", ["source"], unique=False)
        batch_op.create_index("idx_func_req_status", ["status"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_func_test_requirement_created_by"),
            ["created_by"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_func_test_requirement_document_id"),
            ["document_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_func_test_requirement_module_id"),
            ["module_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_func_test_requirement_project_id"),
            ["project_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_func_test_requirement_source"), ["source"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_func_test_requirement_status"), ["status"], unique=False
        )
    op.create_table(
        "kb_chunk",
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "project_id",
            mysql.BIGINT(),
            nullable=False,
            comment="项目ID（冗余硬隔离列，一切查询第一过滤条件；归属校验铁律）",
        ),
        sa.Column("document_id", mysql.BIGINT(), nullable=False, comment="所属文档ID"),
        sa.Column(
            "seq",
            mysql.INTEGER(),
            nullable=False,
            comment="文档内序号（parent/child 统一编号，相邻性用于区间去重）",
        ),
        sa.Column(
            "parent_chunk_id",
            mysql.BIGINT(),
            nullable=True,
            comment="父块ID（child 指向 parent；parent 行为 NULL。无 FK：同文档整批删插，应用层维护）",
        ),
        sa.Column(
            "chunk_type",
            mysql.VARCHAR(length=10),
            server_default=sa.text("'text'"),
            nullable=False,
            comment="类型：text/table/code/case/parent",
        ),
        sa.Column(
            "heading_path",
            mysql.VARCHAR(length=768),
            server_default=sa.text("''"),
            nullable=False,
            comment="标题面包屑（如「3 退款 › 3.2 退款时效」，引用溯源载体，与 content 同入全文索引）",
        ),
        sa.Column(
            "content",
            mysql.MEDIUMTEXT(),
            nullable=False,
            comment="分块正文（全文索引列；重嵌入的数据源）",
        ),
        sa.Column(
            "char_len",
            mysql.INTEGER(),
            server_default=sa.text("0"),
            nullable=False,
            comment="字符数",
        ),
        sa.Column(
            "token_len",
            mysql.INTEGER(),
            server_default=sa.text("0"),
            nullable=False,
            comment="token 数（上下文扩展 8000 封顶的计量）",
        ),
        sa.Column(
            "content_hash",
            mysql.VARCHAR(length=64),
            server_default=sa.text("''"),
            nullable=False,
            comment="content 的 SHA256（P1 图谱抽取缓存键）",
        ),
        sa.Column(
            "embedding",
            mysql.LONGBLOB(),
            nullable=True,
            comment="float32 LE packed 向量（len=embed_dim×4，numpy frombuffer 读；parent 为 NULL）",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["kb_document.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "seq", name="uq_kb_chunk_doc_seq"),
    )
    with op.batch_alter_table("kb_chunk", schema=None) as batch_op:
        batch_op.create_index("idx_kb_chunk_project", ["project_id"], unique=False)
        batch_op.create_index(
            "idx_kb_chunk_project_doc", ["project_id", "document_id"], unique=False
        )
    op.create_table(
        "kb_entity_mention",
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "project_id", mysql.BIGINT(), nullable=False, comment="项目ID（硬隔离列）"
        ),
        sa.Column("entity_id", mysql.BIGINT(), nullable=False, comment="实体ID"),
        sa.Column(
            "document_id",
            mysql.BIGINT(),
            nullable=False,
            comment="来源文档ID（文档删除/重入库按此列一把清）",
        ),
        sa.Column(
            "chunk_id",
            mysql.BIGINT(),
            server_default=sa.text("0"),
            nullable=False,
            comment="来源分块ID（无 FK 应用层维护；0=文档级出处）",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["kb_document.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["entity_id"], ["kb_entity.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "entity_id", "document_id", "chunk_id", name="uq_kb_entity_mention"
        ),
    )
    with op.batch_alter_table("kb_entity_mention", schema=None) as batch_op:
        batch_op.create_index(
            "idx_kb_entity_mention_doc", ["document_id"], unique=False
        )
        batch_op.create_index(
            "idx_kb_entity_mention_project", ["project_id"], unique=False
        )
    op.create_table(
        "kb_relation_mention",
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "project_id", mysql.BIGINT(), nullable=False, comment="项目ID（硬隔离列）"
        ),
        sa.Column("relation_id", mysql.BIGINT(), nullable=False, comment="关系ID"),
        sa.Column("document_id", mysql.BIGINT(), nullable=False, comment="来源文档ID"),
        sa.Column(
            "chunk_id",
            mysql.BIGINT(),
            server_default=sa.text("0"),
            nullable=False,
            comment="来源分块ID（无 FK；0=文档级出处）",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["kb_document.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["relation_id"], ["kb_relation.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "relation_id", "document_id", "chunk_id", name="uq_kb_relation_mention"
        ),
    )
    with op.batch_alter_table("kb_relation_mention", schema=None) as batch_op:
        batch_op.create_index(
            "idx_kb_relation_mention_doc", ["document_id"], unique=False
        )
        batch_op.create_index(
            "idx_kb_relation_mention_project", ["project_id"], unique=False
        )
    op.create_table(
        "sys_scheduled_job_run",
        sa.Column("job_id", mysql.BIGINT(), nullable=False, comment="所属定时计划ID"),
        sa.Column(
            "ai_task_id",
            mysql.BIGINT(),
            nullable=True,
            comment="派发产生的 ai_task ID（跳过时为空）",
        ),
        sa.Column("fired_at", sa.DateTime(), nullable=False, comment="派发时间（UTC）"),
        sa.Column(
            "status",
            mysql.VARCHAR(length=20),
            nullable=False,
            comment="派发结果：dispatched/skipped_overlap/failed",
        ),
        sa.Column(
            "note",
            mysql.VARCHAR(length=200),
            nullable=True,
            comment="说明（跳过/失败原因）",
        ),
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["sys_scheduled_job.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("sys_scheduled_job_run", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_sys_scheduled_job_run_job_id"), ["job_id"], unique=False
        )
    op.create_table(
        "test_dataset",
        sa.Column("project_id", mysql.BIGINT(), nullable=False, comment="项目ID"),
        sa.Column(
            "name", mysql.VARCHAR(length=255), nullable=False, comment="数据集名称"
        ),
        sa.Column("description", sa.Text(), nullable=True, comment="数据集描述"),
        sa.Column(
            "columns", mysql.JSON(), nullable=True, comment="列定义[{name,desc,kind}]"
        ),
        sa.Column(
            "rows", mysql.JSON(), nullable=True, comment="数据行[{列名:值}](明文)"
        ),
        sa.Column(
            "row_count",
            mysql.INTEGER(),
            nullable=False,
            comment="行数(冗余,免每次 len(JSON))",
        ),
        sa.Column(
            "source",
            mysql.VARCHAR(length=20),
            server_default="manual",
            nullable=False,
            comment="来源：manual/csv/ai",
        ),
        sa.Column("ai_task_id", mysql.BIGINT(), nullable=True, comment="AI 生成任务ID"),
        sa.Column("created_by", mysql.BIGINT(), nullable=True, comment="创建人ID"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="删除时间(软删)"),
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.ForeignKeyConstraint(["ai_task_id"], ["ai_task.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["sys_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["tb_project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("test_dataset", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_test_dataset_ai_task_id"), ["ai_task_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_test_dataset_created_by"), ["created_by"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_test_dataset_project_id"), ["project_id"], unique=False
        )
    op.create_table(
        "test_env_variable",
        sa.Column("env_id", mysql.BIGINT(), nullable=False, comment="环境ID"),
        sa.Column("name", mysql.VARCHAR(length=100), nullable=False, comment="变量名"),
        sa.Column("value", sa.Text(), nullable=False, comment="变量值"),
        sa.Column(
            "type",
            mysql.VARCHAR(length=20),
            nullable=False,
            comment="变量类型：text/password/json/dynamic",
        ),
        sa.Column(
            "description", mysql.VARCHAR(length=500), nullable=True, comment="变量描述"
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, comment="是否启用"),
        sa.Column("sort_order", sa.Integer(), nullable=False, comment="排序顺序"),
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.ForeignKeyConstraint(
            ["env_id"], ["test_environment.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("test_env_variable", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_test_env_variable_env_id"), ["env_id"], unique=False
        )
    op.create_table(
        "test_file_asset",
        sa.Column("project_id", mysql.BIGINT(), nullable=False, comment="项目ID"),
        sa.Column(
            "name",
            mysql.VARCHAR(length=255),
            nullable=False,
            comment="资产名（项目内引用键 file:名）",
        ),
        sa.Column(
            "file_name",
            mysql.VARCHAR(length=255),
            nullable=False,
            comment="文件名（含扩展名）",
        ),
        sa.Column(
            "storage_key",
            mysql.VARCHAR(length=500),
            nullable=False,
            comment="平台存储键（本地/COS）",
        ),
        sa.Column(
            "mime", mysql.VARCHAR(length=100), nullable=True, comment="MIME 类型"
        ),
        sa.Column(
            "size_bytes", mysql.BIGINT(), nullable=True, comment="文件大小（字节）"
        ),
        sa.Column(
            "source",
            mysql.VARCHAR(length=20),
            server_default="manual",
            nullable=False,
            comment="来源：manual/ai",
        ),
        sa.Column(
            "spec",
            sa.Text(),
            nullable=True,
            comment="造数意图/文件内容说明（AI 生成时记录规格）",
        ),
        sa.Column("ai_task_id", mysql.BIGINT(), nullable=True, comment="AI 生成任务ID"),
        sa.Column("created_by", mysql.BIGINT(), nullable=True, comment="创建人ID"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="删除时间(软删)"),
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.ForeignKeyConstraint(["ai_task_id"], ["ai_task.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["sys_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["tb_project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("test_file_asset", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_test_file_asset_ai_task_id"), ["ai_task_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_test_file_asset_created_by"), ["created_by"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_test_file_asset_project_id"), ["project_id"], unique=False
        )
    op.create_table(
        "app_execution",
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column("script_id", mysql.BIGINT(), nullable=False, comment="用例ID"),
        sa.Column(
            "ai_task_id",
            mysql.VARCHAR(length=64),
            nullable=True,
            comment="统一任务框架 task_id（事件流/进度经 ai_task_event 回放）",
        ),
        sa.Column(
            "device_udid",
            mysql.VARCHAR(length=160),
            nullable=False,
            comment="执行设备 udid（{agent_id}:{serial}）",
        ),
        sa.Column(
            "status",
            mysql.VARCHAR(length=16),
            nullable=False,
            comment="状态：pending/running/success/failed/cancelled",
        ),
        sa.Column(
            "steps_summary",
            sa.JSON(),
            nullable=True,
            comment="步骤结果摘要 JSON（总数/通过/失败/错误信息等）",
        ),
        sa.Column(
            "report_path",
            mysql.VARCHAR(length=255),
            nullable=True,
            comment="Midscene HTML 报告相对路径（鉴权端点展示，绝不落 /uploads）",
        ),
        sa.Column(
            "duration_ms", mysql.INTEGER(), nullable=True, comment="执行耗时（毫秒）"
        ),
        sa.Column(
            "retry_index", mysql.INTEGER(), nullable=False, comment="重试序号（0=首跑）"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
            comment="更新时间",
        ),
        sa.Column(
            "suite_execution_id",
            mysql.BIGINT(),
            nullable=True,
            comment="所属套件执行汇总ID（套件批量回放时挂靠；单跑为空）",
        ),
        sa.ForeignKeyConstraint(["script_id"], ["app_script.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["suite_execution_id"],
            ["app_suite_execution.id"],
            ondelete="SET NULL",
            name="fk_app_execution_suite_execution",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("app_execution", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_app_execution_ai_task_id"), ["ai_task_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_app_execution_script_id"), ["script_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_app_execution_suite_execution_id"),
            ["suite_execution_id"],
            unique=False,
        )
    op.create_table(
        "bug_ai_analysis",
        sa.Column(
            "bug_id", mysql.BIGINT(), nullable=False, comment="Bug ID（唯一，一对一）"
        ),
        sa.Column(
            "analysis_id",
            mysql.VARCHAR(length=100),
            nullable=False,
            comment="分析任务ID（唯一）",
        ),
        sa.Column(
            "root_cause_analysis", mysql.JSON(), nullable=True, comment="根因分析结果"
        ),
        sa.Column(
            "solution_recommendation",
            mysql.JSON(),
            nullable=True,
            comment="解决方案推荐",
        ),
        sa.Column("similar_bugs", mysql.JSON(), nullable=True, comment="相似Bug列表"),
        sa.Column(
            "severity_assessment", mysql.JSON(), nullable=True, comment="严重程度评估"
        ),
        sa.Column(
            "analysis_status",
            mysql.VARCHAR(length=20),
            nullable=False,
            comment="分析状态：processing/completed/failed",
        ),
        sa.Column(
            "error_message", mysql.TEXT(), nullable=True, comment="失败时的错误信息"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column("completed_at", sa.DateTime(), nullable=True, comment="完成时间"),
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.ForeignKeyConstraint(["bug_id"], ["bug.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("analysis_id", name="uk_bug_ai_analysis_id"),
        sa.UniqueConstraint("bug_id", name="uk_bug_ai_bug_id"),
    )
    op.create_table(
        "bug_history",
        sa.Column("bug_id", mysql.BIGINT(), nullable=False, comment="Bug ID"),
        sa.Column(
            "action", mysql.VARCHAR(length=50), nullable=False, comment="操作类型"
        ),
        sa.Column(
            "from_value", mysql.VARCHAR(length=100), nullable=True, comment="变更前的值"
        ),
        sa.Column(
            "to_value", mysql.VARCHAR(length=100), nullable=True, comment="变更后的值"
        ),
        sa.Column("comment", mysql.TEXT(), nullable=True, comment="操作备注"),
        sa.Column("operated_by", mysql.BIGINT(), nullable=False, comment="操作人ID"),
        sa.Column(
            "operated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="操作时间",
        ),
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.ForeignKeyConstraint(["bug_id"], ["bug.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["operated_by"], ["sys_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("bug_history", schema=None) as batch_op:
        batch_op.create_index("idx_bug_history_action", ["action"], unique=False)
        batch_op.create_index("idx_bug_history_bug_id", ["bug_id"], unique=False)
        batch_op.create_index(
            "idx_bug_history_operated_by", ["operated_by"], unique=False
        )
    op.create_table(
        "func_test_case",
        sa.Column("project_id", mysql.BIGINT(), nullable=False, comment="项目ID"),
        sa.Column("code", mysql.VARCHAR(length=80), nullable=True, comment="用例编号"),
        sa.Column(
            "title", mysql.VARCHAR(length=200), nullable=False, comment="用例标题"
        ),
        sa.Column("module_id", mysql.BIGINT(), nullable=True, comment="所属模块ID"),
        sa.Column(
            "requirement_id", mysql.BIGINT(), nullable=True, comment="关联需求ID"
        ),
        sa.Column(
            "priority", mysql.VARCHAR(length=20), nullable=False, comment="优先级"
        ),
        sa.Column(
            "case_type", mysql.VARCHAR(length=20), nullable=False, comment="用例类型"
        ),
        sa.Column(
            "validation_level",
            mysql.VARCHAR(length=20),
            nullable=False,
            comment="验证层级",
        ),
        sa.Column("status", mysql.VARCHAR(length=30), nullable=False, comment="状态"),
        sa.Column(
            "preconditions",
            mysql.TEXT(),
            nullable=True,
            comment="前置条件（文本或 JSON 字符串）",
        ),
        sa.Column(
            "test_data", mysql.JSON(), nullable=True, comment="测试数据（JSON 对象）"
        ),
        sa.Column("steps", mysql.JSON(), nullable=True, comment="测试步骤列表"),
        sa.Column(
            "expected_result", mysql.JSON(), nullable=True, comment="预期结果列表"
        ),
        sa.Column("tags", mysql.JSON(), nullable=True, comment="标签"),
        sa.Column(
            "review_info",
            mysql.JSON(),
            nullable=True,
            comment="AI 评审结果：{review_result, review_decs}",
        ),
        sa.Column(
            "review_comment",
            mysql.VARCHAR(length=500),
            nullable=True,
            comment="人工评审意见",
        ),
        sa.Column("reviewed_by", mysql.BIGINT(), nullable=True, comment="评审人ID"),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True, comment="评审时间"),
        sa.Column(
            "source",
            mysql.VARCHAR(length=20),
            nullable=False,
            comment="来源：manual/ai_generated",
        ),
        sa.Column("created_by", mysql.BIGINT(), nullable=False, comment="创建人ID"),
        sa.Column("updated_by", mysql.BIGINT(), nullable=True, comment="最后更新人ID"),
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.Column("is_deleted", mysql.TINYINT(), nullable=False, comment="是否删除"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="删除时间"),
        sa.Column(
            "ui_automatable",
            sa.Boolean(),
            nullable=True,
            comment="是否适合 Web UI 自动化：true=适合，false=不适合（本质是接口/后端层校验、页面上无对应操作路径），null=未评估。生成期由 AI 初判，评审期定判（更可靠）；下游转 Web 自动化脚本据此把关",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["sys_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["module_id"], ["tb_project_module.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["tb_project.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["requirement_id"], ["func_test_requirement.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["reviewed_by"], ["sys_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["sys_user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "code", name="uq_func_case_project_code"),
    )
    with op.batch_alter_table("func_test_case", schema=None) as batch_op:
        batch_op.create_index("idx_func_case_req", ["requirement_id"], unique=False)
        batch_op.create_index("idx_func_case_source", ["source"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_func_test_case_created_by"), ["created_by"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_func_test_case_module_id"), ["module_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_func_test_case_project_id"), ["project_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_func_test_case_requirement_id"),
            ["requirement_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_func_test_case_source"), ["source"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_func_test_case_status"), ["status"], unique=False
        )
    op.create_table(
        "func_case_execution",
        sa.Column("test_case_id", mysql.BIGINT(), nullable=False, comment="测试用例ID"),
        sa.Column("project_id", mysql.BIGINT(), nullable=False, comment="项目ID"),
        sa.Column(
            "environment_id", mysql.BIGINT(), nullable=True, comment="测试环境ID"
        ),
        sa.Column(
            "execute_result",
            mysql.VARCHAR(length=20),
            nullable=False,
            comment="执行结果：passed/failed/blocked/skipped",
        ),
        sa.Column("executor_id", mysql.BIGINT(), nullable=False, comment="执行人ID"),
        sa.Column(
            "notes", mysql.TEXT(), nullable=True, comment="备注（失败原因/缺陷链接）"
        ),
        sa.Column("executed_at", sa.DateTime(), nullable=False, comment="执行时间"),
        sa.Column("duration", mysql.BIGINT(), nullable=True, comment="执行耗时（秒）"),
        sa.Column(
            "id", mysql.BIGINT(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.ForeignKeyConstraint(
            ["environment_id"], ["test_environment.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["executor_id"], ["sys_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["tb_project.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["test_case_id"], ["func_test_case.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("func_case_execution", schema=None) as batch_op:
        batch_op.create_index(
            "idx_func_exec_case_time", ["test_case_id", "executed_at"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_func_case_execution_environment_id"),
            ["environment_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_func_case_execution_execute_result"),
            ["execute_result"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_func_case_execution_executor_id"),
            ["executor_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_func_case_execution_project_id"),
            ["project_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_func_case_execution_test_case_id"),
            ["test_case_id"],
            unique=False,
        )
    op.execute(
        "ALTER TABLE kb_chunk ADD FULLTEXT INDEX ft_kb_chunk_content (heading_path, content) WITH PARSER ngram"
    )
    op.execute("SET FOREIGN_KEY_CHECKS=1")


def downgrade() -> None:
    """Downgrade schema：基线迁移直接整库回滚。"""
    op.execute("ALTER TABLE kb_chunk DROP INDEX ft_kb_chunk_content")
    op.execute("SET FOREIGN_KEY_CHECKS=0")
    op.drop_table("func_case_execution")
    op.drop_table("func_test_case")
    op.drop_table("bug_history")
    op.drop_table("bug_ai_analysis")
    op.drop_table("app_execution")
    op.drop_table("test_file_asset")
    op.drop_table("test_env_variable")
    op.drop_table("test_dataset")
    op.drop_table("sys_scheduled_job_run")
    op.drop_table("kb_relation_mention")
    op.drop_table("kb_entity_mention")
    op.drop_table("kb_chunk")
    op.drop_table("func_test_requirement")
    op.drop_table("chat_message")
    op.drop_table("bug")
    op.drop_table("app_suite_execution")
    op.drop_table("app_suite_case")
    op.drop_table("ai_task_event")
    op.drop_table("test_global_function")
    op.drop_table("test_environment")
    op.drop_table("test_database")
    op.drop_table("tb_project_module")
    op.drop_table("tb_project_member")
    op.drop_table("tb_project_config")
    op.drop_table("sys_scheduled_job")
    op.drop_table("kb_relation")
    op.drop_table("kb_project_knowledge_base")
    op.drop_table("kb_document")
    op.drop_table("func_project_document")
    op.drop_table("chat_conversation")
    op.drop_table("app_suite")
    op.drop_table("app_script")
    op.drop_table("app_device")
    op.drop_table("ai_task")
    op.drop_table("tb_project")
    op.drop_table("sys_user_token")
    op.drop_table("sys_user_role")
    op.drop_table("sys_user_llm_config")
    op.drop_table("sys_role_permission")
    op.drop_table("sys_operation_log")
    op.drop_table("kb_entity")
    op.drop_table("sys_user")
    op.drop_table("sys_role")
    op.drop_table("sys_permission")
    op.drop_table("kb_retrieval_log")
    op.drop_table("app_control_session")
    op.drop_table("app_agent")
    op.execute("SET FOREIGN_KEY_CHECKS=1")
