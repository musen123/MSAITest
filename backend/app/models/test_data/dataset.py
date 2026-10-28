"""测试数据集数据模型

对应数据库表：test_dataset

测试数据中心的"固定值"数据源：一张 N 行的参数表，Web/接口用例执行前绑定
（选数据集 + 取行策略），选中行的各列注入为执行变量覆盖脚本 variables 默认值。
结构镜像 perf_dataset（列定义/行/来源/AI 回溯），但独立建表——功能/Web 测试数据
与压测数据分池管理，产品归属、权限与生命周期互不干扰。

行**明文存储**（内部测试平台，不加密）；``kind`` 仅作语义标签 + AI 造数填充策略
（identity/secret 列不让 AI 编造，留空待导入真实账号）。
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, JSON, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IDMixin, TimestampMixin


class TestDataset(Base, IDMixin, TimestampMixin):
    """测试数据集：N 行参数表，执行时按行注入为变量（数据驱动）。"""

    __tablename__ = "test_dataset"

    project_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey("tb_project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="项目ID",
    )
    name: Mapped[str] = mapped_column(VARCHAR(255), nullable=False, comment="数据集名称")
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="数据集描述"
    )
    # 列定义(自描述 + 标注列性质,AI 造数用):
    # [{"name":"username","desc":"账号","kind":"identity"},
    #  {"name":"sku","desc":"商品","kind":"synthetic"}, ...]
    # kind: identity(真实身份) | secret(密码/令牌) | synthetic(合成)——AI 造数填充策略,不加密
    columns: Mapped[list | None] = mapped_column(
        JSON, nullable=True, comment="列定义[{name,desc,kind}]"
    )
    # 数据行 list[dict],键对齐 columns[*].name;明文存储(内部测试平台)
    rows: Mapped[list | None] = mapped_column(
        JSON, nullable=True, comment="数据行[{列名:值}](明文)"
    )
    row_count: Mapped[int] = mapped_column(
        INTEGER, nullable=False, default=0, comment="行数(冗余,免每次 len(JSON))"
    )
    source: Mapped[str] = mapped_column(
        VARCHAR(20),
        nullable=False,
        default="manual",
        server_default="manual",
        comment="来源：manual/csv/ai",
    )
    # 回溯 AI 生成任务;SET NULL:删 ai_task 不连带删数据集
    ai_task_id: Mapped[int | None] = mapped_column(
        BIGINT,
        ForeignKey("ai_task.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="AI 生成任务ID",
    )
    created_by: Mapped[int | None] = mapped_column(
        BIGINT,
        ForeignKey("sys_user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="创建人ID",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None, comment="删除时间(软删)"
    )

    def __repr__(self) -> str:
        return (
            f"<TestDataset(id={self.id}, name='{self.name}', "
            f"rows={self.row_count}, source='{self.source}')>"
        )
