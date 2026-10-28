#!/usr/bin/env bash
# =============================================================================
# AI 智能测试平台 — 生产运维脚本（单机 Docker Compose 一键运维）
# -----------------------------------------------------------------------------
# 部署形态：单台 Linux 云服务器 + Docker Compose，容器自建 MySQL 8 + Redis 7，
#           数据落本地命名卷；公网 IP + HTTP（nginx 预留 443 + 证书挂载点）。
#
# 子命令：
#   deploy   首次部署（构建镜像→起有状态服务→一次性 init→起其余服务→冒烟）
#   up       起全部服务（不重建镜像，日常拉起）
#   down     停止并移除容器（保留命名卷数据）
#   restart  滚动重启业务服务（不动 mysql/redis 数据面）
#   logs     跟随查看日志（可选服务名）
#   status   查看服务状态 / 健康度
#   migrate  数据库迁移（alembic upgrade head；首启 deploy 已含基线迁移，本命令用于后续增量）
#   scale    横向扩缩 celery worker 副本（如 scale celery-worker-app=3）
#   backup   备份所有命名卷（mysql-data / redis-data / app-* / web-* / aicore-data）
#
# 关键纠正（对齐部署契约，唯一事实来源）：
#   - 前端构建走 Docker 多阶段（build: ./frontend），不再依赖宿主 pnpm。
#   - 服务名/端口/卷名/容器内路径/env key 全部以契约为准，脚本不自创命名。
#   - 首启用一次性 init 容器（service_completed_successfully），不用 sleep+exec。
# =============================================================================
set -Eeuo pipefail

# ---- 路径锚定（脚本可在任意 cwd 调用）-------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# compose 文件与环境文件均位于 deploy/ 目录
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"
ENV_FILE="$SCRIPT_DIR/.env.production"
ENV_EXAMPLE="$SCRIPT_DIR/.env.production.example"

# 备份输出目录（命名卷打包落地）
BACKUP_DIR="$SCRIPT_DIR/backups"

# ---- 契约定义的服务名（严格一致，勿改）------------------------------------
SVC_STATEFUL=(mysql redis)                       # 有状态：先起、healthcheck 后才放行
SVC_INIT="init"                                   # 一次性初始化容器（建库+建表+播种）
SVC_RUNTIME=(backend-api celery-worker-ai celery-worker-app celery-beat nginx)

# ---- worker 默认副本数 -----------------------------------------------------
# compose 的 deploy.replicas 在 `docker compose up`（非 swarm）下被忽略，必须用 --scale 落副本。
# 几十人并发：App 回放 celery-worker-app 默认 2 副本、AI 生成 celery-worker-ai 默认 1 副本。
# 可用环境变量覆盖：SCALE_WORKER_APP=3 SCALE_WORKER_AI=2 ./deploy.sh deploy
# 注意：beat / backend-api / mysql / redis 带 container_name，严禁 --scale（beat 必须单例）。
SCALE_ARGS=(--scale "celery-worker-app=${SCALE_WORKER_APP:-2}" --scale "celery-worker-ai=${SCALE_WORKER_AI:-1}")

# ---- 契约定义的命名卷（备份用，严格一致）----------------------------------
NAMED_VOLUMES=(mysql-data redis-data app-data app-archives aicore-data)

# ---- 颜色与日志 ------------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_step()  { echo -e "${BLUE}[STEP]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }

# 出错时打印失败行号，便于定位
trap 'log_error "脚本在第 $LINENO 行失败（退出码 $?）"' ERR

# =============================================================================
# 前置检查
# =============================================================================

# 校验 docker 与 docker compose v2 可用
check_docker() {
    if ! command -v docker >/dev/null 2>&1; then
        log_error "未检测到 docker，请先安装 Docker Engine。"
        exit 1
    fi
    if ! docker compose version >/dev/null 2>&1; then
        log_error "未检测到 docker compose v2（请使用 'docker compose' 而非旧版 'docker-compose'）。"
        exit 1
    fi
}

# 校验 compose 文件存在
check_compose() {
    if [ ! -f "$COMPOSE_FILE" ]; then
        log_error "compose 文件不存在：$COMPOSE_FILE"
        exit 1
    fi
}

# 校验 .env.production 存在，并对危险默认值做提醒
check_env() {
    if [ ! -f "$ENV_FILE" ]; then
        log_error ".env.production 不存在！生产环境必须显式配置后再部署。"
        log_info  "请基于示例复制并填写强随机密钥："
        log_info  "  cp \"$ENV_EXAMPLE\" \"$ENV_FILE\""
        log_info  "  # SECRET_KEY:   openssl rand -hex 32"
        log_info  "  # 各类密码:     openssl rand -base64 24"
        log_info  "  vim \"$ENV_FILE\""
        exit 1
    fi

    # 危险默认值/必填项快速体检（仅告警 + 阻断已知危险默认值，不做完整解析）
    local dangerous=0
    if grep -Eq '^[[:space:]]*SECRET_KEY=your-secret-key-change-in-production[[:space:]]*$' "$ENV_FILE"; then
        log_error "SECRET_KEY 仍为默认占位值，必须改为 openssl rand -hex 32 生成的随机值。"
        dangerous=1
    fi
    if grep -Eq '^[[:space:]]*admin_password=admin123456[[:space:]]*$' "$ENV_FILE"; then
        log_error "admin_password 仍为默认弱密码 admin123456，且首启后无法更新已建账号，必须首启前改强密码。"
        dangerous=1
    fi
    if grep -Eq '^[[:space:]]*ENV=production[[:space:]]*$' "$ENV_FILE"; then
        :
    else
        log_warn "建议显式设置 ENV=production（生产环境）。"
    fi
    if grep -Eq '^[[:space:]]*DEBUG=([Tt]rue|1)[[:space:]]*$' "$ENV_FILE"; then
        log_warn "DEBUG 处于开启状态，生产环境务必设为 false 以免泄露调试信息。"
    fi
    if [ "$dangerous" -ne 0 ]; then
        exit 1
    fi
}

# compose 命令封装：始终带上 compose 文件与 env 文件
# 用法： dc <compose 子命令...>
# 可选：设置 COMPOSE_OVERRIDE=/path/to/override.yml 时额外叠加一个 compose 覆盖文件
#       （用于本地验证端口重映射等场景，生产部署不需要）
dc() {
    docker compose -f "$COMPOSE_FILE" ${COMPOSE_OVERRIDE:+-f "$COMPOSE_OVERRIDE"} --env-file "$ENV_FILE" "$@"
}

# 仅检查 docker/compose/文件（不强制 env，供只读子命令使用）
preflight_light() {
    check_docker
    check_compose
}

# 完整前置检查（变更面子命令使用，强制 env）
preflight_full() {
    check_docker
    check_compose
    check_env
}

# =============================================================================
# 子命令实现
# =============================================================================

# ---- deploy：首次部署完整编排 ---------------------------------------------
# 步骤严格对应契约 first_deploy_sequence：
#   build → 起 mysql/redis → 一次性 init → 起其余服务 → 冒烟
cmd_deploy() {
    preflight_full

    log_step "1/5 构建镜像（后端业务镜像；前端多阶段构建 dist）"
    # 前端走 Docker 多阶段（build: ./frontend），无需宿主 pnpm；浏览器二进制 build 期烘焙入层
    dc build

    log_step "2/5 启动有状态服务 mysql / redis，并等待健康检查通过"
    dc up -d "${SVC_STATEFUL[@]}"
    wait_healthy mysql 120
    wait_healthy redis 60

    log_step "3/5 运行一次性 init 容器（alembic upgrade head 基线建表 + 播种 权限/角色/管理员）"
    # init 为 one-shot（restart: no）：--abort-on-container-exit 跟随其退出码，非 0 即失败
    if ! dc up --abort-on-container-exit --exit-code-from "$SVC_INIT" "$SVC_INIT"; then
        log_error "init 初始化失败，请查看日志：$0 logs $SVC_INIT"
        exit 1
    fi
    log_info "init 已成功退出（exit 0），数据库初始化完成。"

    log_step "4/5 启动其余业务服务（backend-api / 两组 worker / beat / nginx），按默认副本数扩 worker"
    dc up -d "${SCALE_ARGS[@]}" "${SVC_RUNTIME[@]}"

    log_step "5/5 等待 backend-api 与 nginx 健康，执行冒烟检查"
    wait_healthy backend-api 120
    wait_healthy nginx 60
    smoke_test

    echo
    log_info "====================================================="
    log_info "部署完成！"
    log_info "前端入口（公网 IP + HTTP）: http://<公网IP>/"
    log_info "后端 API 文档（本机）     : http://127.0.0.1:8888/docs"
    log_info "用 .env.production 中设置的 admin_username/admin_password 登录。"
    log_warn "提示学员：首次使用 AI 前需各自在前端配置 文本/嵌入/视觉 模型（UserLlmConfig），"
    log_warn "          否则 AI 接口返回 HTTP400 '请先配置大模型'。"
    log_info "====================================================="
}

# ---- up：日常拉起全部服务（不重建镜像）------------------------------------
cmd_up() {
    preflight_full
    log_step "拉起全部服务（按 compose 依赖编排：mysql/redis healthy → init 完成 → 其余服务）"
    # init 为 one-shot，up -d 会随依赖触发其执行；其余服务 depends_on init 的
    # service_completed_successfully，compose 自动保证顺序。--scale 落 worker 默认副本。
    dc up -d "${SCALE_ARGS[@]}"
    log_info "已拉起，查看状态：$0 status"
}

# ---- down：停止并移除容器（保留命名卷）------------------------------------
cmd_down() {
    preflight_light
    log_step "停止并移除容器（命名卷数据保留，不加 -v）"
    dc down
    log_info "已停止。命名卷数据仍在，重新 $0 up 即可恢复。"
}

# ---- restart：滚动重启业务服务（不动 mysql/redis 数据面）-------------------
# 可选传入具体服务名：restart backend-api
cmd_restart() {
    preflight_full
    if [ "$#" -ge 1 ] && [ -n "${1:-}" ]; then
        log_step "重启指定服务：$*"
        dc restart "$@"
    else
        log_step "滚动重启全部业务服务（保留 mysql/redis 运行，不重跑 init）"
        dc restart "${SVC_RUNTIME[@]}"
    fi
    log_info "重启完成。"
}

# ---- logs：跟随日志 --------------------------------------------------------
cmd_logs() {
    preflight_light
    if [ "$#" -ge 1 ] && [ -n "${1:-}" ]; then
        dc logs -f --tail=200 "$@"
    else
        dc logs -f --tail=200
    fi
}

# ---- status：服务状态 + 健康度 --------------------------------------------
cmd_status() {
    preflight_light
    log_step "服务状态："
    dc ps
    echo
    log_step "Celery worker 在线探测（ai@ / test@ 应均在）："
    # 通过 backend-api 同镜像的 worker 自带 inspect ；这里直接连任一 worker 容器探测
    if dc exec -T celery-worker-ai uv run celery -A app.tasks.celery_app inspect ping >/dev/null 2>&1; then
        dc exec -T celery-worker-ai uv run celery -A app.tasks.celery_app inspect ping || true
    else
        log_warn "celery-worker-ai 未就绪或无法探测（服务可能尚未启动）。"
    fi
}

# ---- migrate：数据库迁移 ---------------------------------------------------
# 注意：迁移已合并为单一基线，全新库的首启迁移由 deploy 的 init 完成；
#       本命令用于后续版本升级，对【已初始化的库】执行增量迁移。
cmd_migrate() {
    preflight_full
    log_warn "本命令对【已初始化的库】执行增量迁移（alembic upgrade head）。"
    log_warn "全新库请直接走 $0 deploy（init 容器会完成基线迁移 + 播种）。"
    log_step "在 backend-api 容器内执行 alembic upgrade head"
    dc exec -T backend-api uv run alembic upgrade head
    log_info "迁移完成。"
}

# ---- scale：横向扩缩 celery worker 副本 ------------------------------------
# 用法：scale celery-worker-app=3 [celery-worker-ai=2 ...]
# 硬规则：celery-beat 严格单例，禁止扩 >1（reap/archive/dispatch 重复触发竞态）。
cmd_scale() {
    preflight_full
    if [ "$#" -lt 1 ]; then
        log_error "缺少扩缩参数。用法：$0 scale celery-worker-app=3 [celery-worker-ai=2]"
        log_info  "可横扩：celery-worker-app（App 回放吞吐，吃内存）、celery-worker-ai（AI 生成吞吐）。"
        log_info  "禁止扩：celery-beat（严格单例）、mysql / redis（有状态不可横扩）。"
        exit 1
    fi

    # 守护：拦截对单例/有状态服务的非法扩缩
    for arg in "$@"; do
        local name="${arg%%=*}"
        local num="${arg#*=}"
        case "$name" in
            celery-beat)
                if [ "$num" != "1" ]; then
                    log_error "celery-beat 必须严格单例（=1），扩 >1 会导致 reap/archive/dispatch 重复触发竞态。已拒绝。"
                    exit 1
                fi
                ;;
            mysql|redis)
                log_error "$name 为有状态服务，不可横向扩展。已拒绝。"
                exit 1
                ;;
            celery-worker-ai|celery-worker-app|backend-api) : ;;  # 允许
            *)
                log_warn "未识别的服务名 '$name'，将原样透传给 compose（请确认与契约一致）。"
                ;;
        esac
    done

    log_step "应用扩缩：$*"
    # --no-recreate：仅增减副本，不重建既有容器；扩容前提醒内存与 MySQL 连接数约束
    log_warn "扩容约束提醒：每副本×concurrency×连接数勿超 MySQL max-connections=200（DB_POOL_SIZE=40 已留余量）；"
    log_warn "             App 设备执行由独立队列处理，按执行机容量配置并发。"
    # compose 的 --scale 需对每个 服务=N 重复一次，逐个拼进参数数组
    local scale_args=()
    for arg in "$@"; do
        scale_args+=(--scale "$arg")
    done
    dc up -d --no-recreate "${scale_args[@]}"
    echo
    cmd_status
}

# ---- backup：备份全部命名卷 -----------------------------------------------
# 通过临时 alpine 容器挂载每个命名卷，tar 打包落到宿主 BACKUP_DIR。
# mysql-data 优先级最高（唯一数据源）；redis-data 含 AOF；app-* / web-* 为运行态产物。
cmd_backup() {
    preflight_light
    local stamp; stamp="$(date +%Y%m%d-%H%M%S)"
    local out_dir="$BACKUP_DIR/$stamp"
    mkdir -p "$out_dir"
    log_step "备份命名卷 → $out_dir"

    # compose 工程名（卷的真实前缀）：默认取 deploy 目录名，可由 COMPOSE_PROJECT_NAME 覆盖
    local project; project="$(dc config --format json 2>/dev/null | grep -o '"name":[^,]*' | head -1 | cut -d'"' -f4 || true)"
    if [ -z "$project" ]; then
        project="$(basename "$SCRIPT_DIR")"
    fi

    # ---- MySQL：一致性逻辑备份 ----------------------------------------------
    # 绝不 tar 在线 InnoDB 数据目录（边写边 tar 会抓到撕裂页 + 不一致 redo/undo，恢复必坏）。
    # 用 mysqldump --single-transaction 拿一致性快照（InnoDB 不锁表）。
    if dc ps --status running 2>/dev/null | grep -q '\bmysql\b'; then
        log_info "  mysqldump（--single-transaction 一致性快照）..."
        if dc exec -T mysql sh -c \
            'exec mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction --quick --routines --triggers --events --databases "$MYSQL_DATABASE"' \
            2>/dev/null | gzip > "$out_dir/mysql-dump.sql.gz"; then
            log_info "    → mysql-dump.sql.gz 完成"
        else
            log_warn "    ! mysqldump 失败（检查 MySQL 是否运行 / 凭据是否正确）。"
        fi
    else
        log_warn "  mysql 未运行，跳过逻辑备份（如需冷备份：先 $0 down 再 tar mysql-data 卷）。"
    fi

    # ---- Redis：先 BGSAVE 落盘再随文件卷打包（broker 多为瞬态，best-effort）--
    if dc ps --status running 2>/dev/null | grep -q '\bredis\b'; then
        dc exec -T redis sh -c 'redis-cli -a "$REDIS_PASSWORD" --no-auth-warning BGSAVE >/dev/null 2>&1 || true'
        sleep 1
    fi

    # ---- 文件型卷：tar 打包（含 redis AOF；app-*/web-*/aicore 为文件产物）-----
    local file_vols=(redis-data app-data app-archives aicore-data)
    for vol in "${file_vols[@]}"; do
        # compose 命名卷在 docker 中的真实名称为 <project>_<vol>
        local full="${project}_${vol}"
        if ! docker volume inspect "$full" >/dev/null 2>&1; then
            log_warn "卷 $full 不存在（服务可能尚未首次启动），跳过。"
            continue
        fi
        log_info "  打包 $full ..."
        docker run --rm \
            -v "${full}:/volume:ro" \
            -v "${out_dir}:/backup" \
            alpine:3 \
            sh -c "tar czf /backup/${vol}.tar.gz -C /volume ." \
            && log_info "    → ${vol}.tar.gz 完成" \
            || log_warn "    ! ${vol} 备份失败，请检查。"
    done

    log_info "备份完成：$out_dir"
    log_warn "恢复 MySQL：gunzip < $out_dir/mysql-dump.sql.gz | $0 ... 或"
    log_warn "  docker compose exec -T mysql sh -c 'mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\"' < dump.sql"
    log_warn "恢复文件卷：docker run --rm -v <project>_<vol>:/volume -v <备份目录>:/backup alpine:3 \\"
    log_warn "         sh -c 'tar xzf /backup/<vol>.tar.gz -C /volume'（恢复前请先 $0 down 并清空目标卷）。"
}

# =============================================================================
# 辅助函数
# =============================================================================

# 等待某服务 healthcheck 变为 healthy（无 healthcheck 的服务退化为等 running）
# 用法： wait_healthy <service> <timeout_seconds>
wait_healthy() {
    local svc="$1"; local timeout="${2:-120}"; local waited=0; local interval=3
    log_info "等待服务 [$svc] 健康（超时 ${timeout}s）..."
    while true; do
        local cid; cid="$(dc ps -q "$svc" 2>/dev/null | head -1 || true)"
        if [ -n "$cid" ]; then
            # 读取健康状态；无 healthcheck 时 .Health 为空，退化看 running
            local health; health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$cid" 2>/dev/null || echo "unknown")"
            local state;  state="$(docker inspect -f '{{.State.Status}}' "$cid" 2>/dev/null || echo "unknown")"
            case "$health" in
                healthy) log_info "  [$svc] healthy"; return 0 ;;
                none)
                    if [ "$state" = "running" ]; then
                        log_info "  [$svc] running（该服务未定义 healthcheck）"; return 0
                    fi
                    ;;
                unhealthy)
                    log_error "  [$svc] unhealthy，请查看日志：$0 logs $svc"; return 1 ;;
            esac
        fi
        if [ "$waited" -ge "$timeout" ]; then
            log_error "  [$svc] 等待超时（${timeout}s 仍未健康），请查看日志：$0 logs $svc"
            return 1
        fi
        sleep "$interval"; waited=$((waited + interval))
    done
}

# 冒烟检查：经 nginx 入口验证前端与 /api 反代连通
smoke_test() {
    log_step "冒烟检查（经 nginx 80 端口入口）"
    # nginx 自身健康端点
    if curl -fsS -o /dev/null "http://127.0.0.1/healthz" 2>/dev/null; then
        log_info "  nginx /healthz 通"
    else
        log_warn "  nginx /healthz 未通（可能 nginx 尚未就绪或站点配置缺失）。"
    fi
    # 经 nginx 反代到 backend-api 的健康端点
    if curl -fsS -o /dev/null "http://127.0.0.1/api/v1/health" 2>/dev/null; then
        log_info "  /api/v1/health 反代通"
    elif curl -fsS -o /dev/null "http://127.0.0.1:8888/docs" 2>/dev/null; then
        log_info "  backend-api /docs 可达（health 端点未返回，降级判定通过）"
    else
        log_warn "  后端 API 未通，请查看日志：$0 logs backend-api"
    fi
}

# =============================================================================
# 用法说明
# =============================================================================
usage() {
    cat <<'EOF'
AI 智能测试平台 — 生产运维脚本（Docker Compose 单机一键运维）

用法：deploy.sh <子命令> [参数]

  deploy                首次部署：构建镜像 → 起 mysql/redis → 一次性 init → 起其余服务 → 冒烟
  up                    日常拉起全部服务（不重建镜像）
  down                  停止并移除容器（保留命名卷数据，不删数据）
  restart [服务名...]   滚动重启业务服务（缺省重启 backend-api/worker×2/beat/nginx，不动 mysql/redis）
  logs [服务名...]      跟随查看日志（缺省全部；如 logs backend-api）
  status                查看服务状态 + Celery worker 在线探测
  migrate               增量数据库迁移 alembic upgrade head（仅用于已初始化的库，全新库走 deploy）
  scale 服务=N [...]     横扩 celery worker（如 scale celery-worker-app=3 celery-worker-ai=2）
  backup                备份全部命名卷到 deploy/backups/<时间戳>/

服务名（与部署契约一致）：
  有状态：mysql redis          一次性：init
  业务  ：backend-api celery-worker-ai celery-worker-app celery-beat nginx

扩缩规则：
  可横扩 celery-worker-app（App 回放吞吐，吃内存）/ celery-worker-ai（AI 生成吞吐）
  禁止扩 celery-beat（严格单例）/ mysql / redis（有状态）

首次部署前：cp deploy/.env.production.example deploy/.env.production 并填写强随机密钥
  SECRET_KEY: openssl rand -hex 32     各类密码: openssl rand -base64 24
EOF
}

# =============================================================================
# 入口分发
# =============================================================================
main() {
    local cmd="${1:-}"
    shift || true
    case "$cmd" in
        deploy|start) cmd_deploy "$@" ;;
        up)           cmd_up "$@" ;;
        down|stop)    cmd_down "$@" ;;
        restart)      cmd_restart "$@" ;;
        logs)         cmd_logs "$@" ;;
        status|ps)    cmd_status "$@" ;;
        migrate)      cmd_migrate "$@" ;;
        scale)        cmd_scale "$@" ;;
        backup)       cmd_backup "$@" ;;
        -h|--help|help|"") usage ;;
        *)
            log_error "未知子命令：$cmd"
            echo
            usage
            exit 1
            ;;
    esac
}

main "$@"
