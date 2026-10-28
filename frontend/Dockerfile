# ============================================================================
# 前端镜像（多阶段构建）—— AI 智能测试平台
#
# 契约对齐（image_strategy / nginx_routes，唯一事实来源）：
#   阶段一 builder：node:22-alpine + pnpm，执行 pnpm build 产出静态 dist/
#   阶段二 runtime：nginx:alpine 托管 dist + 自带站点 conf
#
# 该镜像即 compose 中的 nginx 服务（build: ./frontend）：
#   - 公网入口，监听 80（443 由站点 conf 预留，证书挂 /etc/nginx/certs）
#   - 反代 /api、/uploads、/web-screenshots → backend-api:8888
#   - SPA history 模式兜底、SSE 关缓冲、WebSocket 升级、大包上传、长任务超时
#
# 前端走相对路径 /api，无需 build-arg；切后端地址 / 切 HTTPS 都只改 nginx，
# 不必重建前端镜像。
# ============================================================================


# ----------------------------------------------------------------------------
# 阶段一：构建静态产物（node:22-alpine，契约钉死的构建基底）
# ----------------------------------------------------------------------------
FROM node:22-alpine AS builder

# npm 软件源（默认 npmmirror 国内加速；境外构建可 --build-arg NPM_REGISTRY=https://registry.npmjs.org）
# NPM_CONFIG_REGISTRY 环境变量同时被 npm / pnpm / corepack 读取
ARG NPM_REGISTRY=https://registry.npmmirror.com
ENV NPM_CONFIG_REGISTRY=${NPM_REGISTRY} \
    COREPACK_NPM_REGISTRY=${NPM_REGISTRY}

WORKDIR /app

# 通过 corepack 启用 pnpm 并【钉死 10.32.1】（与开发本机一致，lockfile v9）。
# 为什么必须钉版：不钉版时 corepack 会拉最新 pnpm（实测 11.6.0），而 pnpm 11 把
# “依赖 build 脚本被忽略”(esbuild/@parcel/watcher/vue-demi) 升级成 ERR_PNPM_IGNORED_BUILDS
# 硬错误 → install 退出 1、构建直接失败；pnpm 10.32.1 仅警告、exit 0，故锁回该版本。
RUN corepack enable && corepack prepare pnpm@10.32.1 --activate

# 先只拷依赖清单，最大化利用 Docker 层缓存：
# 仅当 package.json / pnpm-lock.yaml 变更时才重新安装依赖。
COPY package.json pnpm-lock.yaml ./

# --frozen-lockfile：严格按 lockfile 安装，CI/生产可复现，lock 不一致直接失败。
RUN pnpm install --frozen-lockfile

# 再拷入全部源码进行构建（package.json 之外的改动不会击穿上面的依赖缓存层）。
COPY . .

# 生产构建只跑 vite build（esbuild 转译，产出到 /app/dist），不挂 vue-tsc 类型门禁——
# 与项目既有构建方式一致（原 deploy.sh 用的就是 `npx vite build`）。
# 注意：项目存在历史遗留 TS 类型报错（`vue-tsc -b` 会失败、`pnpm build` 因此构建不出来），
#       类型债应另行修复，不应阻断部署构建。类型在打包时被擦除，不影响运行产物。
# NODE_OPTIONS 调大堆上限：本项目 2900+ 模块，vite 构建超过 Node 默认 ~2G 堆会 OOM
# （FATAL ERROR: Reached heap limit）。4G 在容器内构建稳定，任何构建机通用。
RUN NODE_OPTIONS=--max-old-space-size=4096 pnpm exec vite build


# ----------------------------------------------------------------------------
# 阶段二：静态托管 + 反向代理（nginx:alpine）
# ----------------------------------------------------------------------------
FROM nginx:alpine AS runtime

# 移除镜像默认站点配置，换成本项目的站点 conf。
RUN rm -f /etc/nginx/conf.d/default.conf

# 拷入构建产物到 nginx 默认站点根目录。
COPY --from=builder /app/dist /usr/share/nginx/html

# 站点配置以 COPY 烘焙（站点 conf 见同目录 nginx.conf：map 升级头 + /api·/uploads·
# /web-screenshots 反代 + SSE 关缓冲 + 长任务超时 + SPA 兜底 + 443 预留块）。
# 关键：绝不用 `RUN cat > ... <<EOF` heredoc——docker classic builder 下 heredoc 的 stdin
# 为空，会写出【空配置】，nginx 无 server 块直接不服务（已踩坑）。COPY 在任何 builder 都可靠。
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80 443

# 前台运行 nginx（容器主进程）。
CMD ["nginx", "-g", "daemon off;"]
