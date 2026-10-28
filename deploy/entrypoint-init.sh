#!/usr/bin/env sh
# =============================================================================
# entrypoint-init.sh —— init 一次性初始化容器入口
# -----------------------------------------------------------------------------
# 职责（one-shot，跑完即退，restart: "no"）：
#   1. 等待 MySQL 8 就绪（用 pymysql 真连，避免 sleep + exec 竞态）
#   2. alembic upgrade head —— 单一基线迁移建全部表（含 kb_chunk FULLTEXT ngram
#      索引、列级 server_default）+ 写入 alembic_version 版本记录
#   3. python -m app.db.init_db —— 播种 权限/角色/管理员（其 create_all 在基线
#      之后全命中幂等跳过；建库动作由 compose MYSQL_DATABASE 先行完成）
#
# 为什么是 upgrade 而不是 create_all + stamp：
#   迁移已合并为单一基线（01e74825fd25）。全新库 upgrade head 一条命令建出全部
#   表并留下版本记录。旧的 create_all+stamp 路子建出的库缺 FULLTEXT ngram 索引
#   与列级默认值（模型层表达不了），知识库检索会直接失效。
#
# 编排（docker-compose）：
#   - init depends_on mysql/redis service_healthy（DB/缓存先就绪）
#   - 其余服务 depends_on init service_completed_successfully（靠本脚本 exit 0 触发）
#
# 该脚本由契约中的 init 服务 command 等价实现，落成文件便于维护与阅读。
# 容器内路径 / 环境变量 key 严格对齐部署契约，勿自创不一致命名。
# =============================================================================

# 任一命令失败立即退出，未定义变量报错（保证失败可被 compose 捕获为非 0 退出）
set -eu

echo "============================================================"
echo "[init] 一次性数据库初始化开始"
echo "============================================================"

# -----------------------------------------------------------------------------
# 步骤 0：校验关键环境变量已注入（契约 env_keys，全部小写：db_* / database）
#   db_host  必须为 compose 服务名 mysql（非 localhost）
#   db_port  容器内部固定 3306（对外映射 3307 不影响）
# -----------------------------------------------------------------------------
: "${db_host:?[init] 缺少环境变量 db_host（应为 compose 服务名 mysql）}"
: "${db_port:=3306}"
: "${db_user:?[init] 缺少环境变量 db_user（应用账号，非 root）}"
: "${db_password:?[init] 缺少环境变量 db_password（应用账号密码）}"

echo "[init] 目标 MySQL: ${db_host}:${db_port}（user=${db_user}）"

# -----------------------------------------------------------------------------
# 步骤 1：等待 MySQL 就绪
#   用 pymysql 真实建连探活，比 sleep 固定时长更可靠；MySQL 8 首启建库 +
#   初始化耗时较长（compose 已配 start_period 40s），这里轮询直到连通。
#   仅探活是否能建立连接，不指定 database（库可能尚未由 MYSQL_DATABASE 建好）。
# -----------------------------------------------------------------------------
echo "[init] 步骤 1/3：等待 MySQL 就绪 ..."
until uv run python -c "import pymysql, os; pymysql.connect(host=os.environ['db_host'], port=int(os.environ['db_port']), user=os.environ['db_user'], password=os.environ['db_password'])" 2>/dev/null; do
  echo "[init]   MySQL 尚未就绪，2 秒后重试 ..."
  sleep 2
done
echo "[init] 步骤 1/3：MySQL 已就绪 ✅"

# -----------------------------------------------------------------------------
# 步骤 2：执行数据库迁移（alembic upgrade head）
#   单一基线迁移建出全部表（含 kb_chunk FULLTEXT ngram 索引、列级 server_default）
#   并写入 alembic_version。幂等：重复执行只会校验版本号，不重复 DDL。
# -----------------------------------------------------------------------------
echo "[init] 步骤 2/3：alembic upgrade head（基线建表 + 版本记录）..."
uv run alembic upgrade head
echo "[init] 步骤 2/3：迁移完成 ✅"

# -----------------------------------------------------------------------------
# 步骤 3：执行数据播种（幂等）
#   app.db.init_db.main() 在迁移之后运行：create_all 全命中跳过（表已由迁移建好），
#   实际执行 播种 权限 / 角色 / 项目角色 + 创建管理员（按 admin_username 查重）。
#   故重复运行安全；backend-api 的 lifespan 也会跑 init_db.main()，全部幂等。
# -----------------------------------------------------------------------------
echo "[init] 步骤 3/3：init_db（播种 权限/角色/管理员）..."
uv run python -m app.db.init_db
echo "[init] 步骤 3/3：init_db 完成 ✅"

echo "============================================================"
echo "[init] 数据库初始化全部完成，容器正常退出（exit 0）"
echo "[init] compose 将据此触发 service_completed_successfully，放行其余服务"
echo "============================================================"

# 显式以 0 退出，确保 service_completed_successfully 条件成立
exit 0
