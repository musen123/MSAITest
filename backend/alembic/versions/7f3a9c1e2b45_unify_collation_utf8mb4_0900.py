"""统一全库 collation 为 utf8mb4_0900_ai_ci

Revision ID: 7f3a9c1e2b45
Revises: 01e74825fd25
Create Date: 2026-08-10 10:30:00.000000

背景：生产库由 MySQL 5.7 时代数据演化而来，74 张老表是 utf8mb4_general_ci，
而服务器默认已是 MySQL 8 的 utf8mb4_0900_ai_ci（新建表自动继承），
跨表字符串等值 JOIN 直接报错 1267 Illegal mix of collations——
线上 app/executions 列表（app_device.udid = app_execution.device_udid）
因此稳定 500（2026-08-09/10 日志实锤）。

修复：把库默认与所有非 0900_ai_ci 的表统一 CONVERT 到 utf8mb4_0900_ai_ci
（与本地开发库 MySQL 9 默认一致，未来 create_all 新表不再漂移）。
按 information_schema 动态圈定，已符合的环境执行时为无操作。
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = '7f3a9c1e2b45'
down_revision: Union[str, Sequence[str], None] = '01e74825fd25'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TARGET_CHARSET = 'utf8mb4'
_TARGET_COLLATION = 'utf8mb4_0900_ai_ci'
_OLD_COLLATION = 'utf8mb4_general_ci'


def _convert_tables_not_in(collation: str) -> list[str]:
    """把当前库中所有非目标 collation 的表 CONVERT 到目标，返回被转换的表名。"""
    bind = op.get_bind()
    db_name = bind.execute(text('SELECT DATABASE()')).scalar()
    rows = bind.execute(
        text(
            'SELECT table_name FROM information_schema.TABLES '
            'WHERE table_schema = :db AND table_type = :tt '
            "AND (table_collation IS NULL OR table_collation != :col)"
        ),
        {'db': db_name, 'tt': 'BASE TABLE', 'col': collation},
    ).fetchall()
    converted = []
    # 转换期间关闭 FK 检查：字符串 FK 两侧 collation 中间态不一致会误拦
    op.execute('SET FOREIGN_KEY_CHECKS=0')
    try:
        for (table_name,) in rows:
            op.execute(
                f'ALTER TABLE `{table_name}` '
                f'CONVERT TO CHARACTER SET {_TARGET_CHARSET} COLLATE {collation}'
            )
            converted.append(table_name)
    finally:
        op.execute('SET FOREIGN_KEY_CHECKS=1')
    return converted


def upgrade() -> None:
    """统一库默认与全部表到 utf8mb4_0900_ai_ci（未来新表不再漂移）。"""
    op.execute(
        f'ALTER DATABASE CHARACTER SET {_TARGET_CHARSET} COLLATE {_TARGET_COLLATION}'
    )
    converted = _convert_tables_not_in(_TARGET_COLLATION)
    if converted:
        print(f'collation 统一到 {_TARGET_COLLATION}：{len(converted)} 张表 -> {converted}')


def downgrade() -> None:
    """回退到 utf8mb4_general_ci（生产 5.7 时代旧值）。"""
    op.execute(
        f'ALTER DATABASE CHARACTER SET {_TARGET_CHARSET} COLLATE {_OLD_COLLATION}'
    )
    _convert_tables_not_in(_OLD_COLLATION)
