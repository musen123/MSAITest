"""
APP 自动化测试套件数据模型

对应数据库表：app_suite / app_suite_case（P4 套件+定时执行）。
套件 = 有序用例编组，run_app_suite 图在同一设备上一锁贯穿顺序回放；
device_udid 为默认执行设备（定时触发无人交互时的落点，手动可覆盖）。
对齐 web_test 先例（web_test_suite / web_suite_case），但沿用 App 域
硬删除约定（无软删；套件删除级联清关联与套件执行汇总，用例级
app_execution 经 SET NULL 保留在用例名下）。
"""

from typing import TYPE_CHECKING

from sqlalchemy import BOOLEAN, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IDMixin, TimestampMixin

if TYPE_CHECKING:
    pass


class AppSuite(Base, IDMixin, TimestampMixin):
    """APP 自动化测试套件（有序用例编组）"""

    __tablename__ = "app_suite"

    project_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("tb_project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属项目ID",
    )
    name: Mapped[str] = mapped_column(
        VARCHAR(128),
        nullable=False,
        comment="套件名称",
    )
    description: Mapped[str | None] = mapped_column(
        VARCHAR(500),
        nullable=True,
        comment="套件描述",
    )
    device_udid: Mapped[str | None] = mapped_column(
        VARCHAR(160),
        nullable=True,
        comment="默认执行设备 udid（定时触发用；手动执行可覆盖）",
    )
    failure_strategy: Mapped[str] = mapped_column(
        VARCHAR(16),
        nullable=False,
        default="continue",
        comment="失败策略：continue（单条失败继续）/ stop（遇错中断，余下记跳过）",
    )
    created_by: Mapped[int | None] = mapped_column(
        BIGINT,
        ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True,
        comment="创建人",
    )

    # 编排（passive_deletes：删除交给数据库级 ON DELETE CASCADE，
    # 否则 ORM 会把已加载子行外键置 NULL 撞 NOT NULL；同 web 先例）
    cases: Mapped[list["AppSuiteCase"]] = relationship(
        "AppSuiteCase",
        lazy="selectin",
        order_by="AppSuiteCase.sort_order",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<AppSuite(id={self.id}, name='{self.name}')>"


class AppSuiteCase(Base, IDMixin, TimestampMixin):
    """套件-用例关联（有序，多对多）"""

    __tablename__ = "app_suite_case"
    __table_args__ = (
        UniqueConstraint("suite_id", "script_id", name="uk_app_suite_script"),
    )

    suite_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("app_suite.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="套件ID",
    )
    script_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("app_script.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="用例ID",
    )
    sort_order: Mapped[int] = mapped_column(
        INTEGER,
        nullable=False,
        default=0,
        comment="执行顺序（升序）",
    )
    enabled: Mapped[bool] = mapped_column(
        BOOLEAN,
        nullable=False,
        default=True,
        comment="是否参与执行",
    )

    def __repr__(self) -> str:
        return f"<AppSuiteCase(id={self.id}, suite_id={self.suite_id}, script_id={self.script_id})>"
