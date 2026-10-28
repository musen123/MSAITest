<div align="center">
  <img src="assets/logo.svg" alt="MSAITest" width="80" />

  <h1>MSAITest · AI 智能测试平台</h1>

  <p><strong>从需求到执行，让 AI 参与测试全流程</strong></p>
  <p>功能测试 · 接口自动化 · Web 自动化 · App 自动化 · 性能测试</p>

  <p>
    <a href="https://www.mstest.vip"><strong>体验商业版</strong></a> ·
    <a href="#商业版咨询">商业版咨询</a> ·
    <a href="#商业版亮点">产品亮点</a> ·
    <a href="#开源版与商业版">版本对比</a> ·
    <a href="#全部菜单截图">全部菜单截图</a>
  </p>
</div>



> 本仓库提供开源版源码，具体功能范围见[版本对比](#开源版与商业版)。

![MSAITest 商业版项目概览：完整菜单、测试资产、执行趋势与最近执行](assets/screenshots/commercial-overview.jpg)

## 为什么选择 MSAITest

| 测试工作中的问题 | MSAITest 的处理方式 |
| --- | --- |
| 需求、文档和测试用例分散，业务上下文容易丢失 | 将文档、需求、用例与知识库放在同一项目内，支持 AI 提取需求、生成与评审用例 |
| 接口、Web、App 与压测使用多个独立工具 | 商业版提供多种测试方式，共享项目配置、测试资产与执行监控 |
| 核心业务链路复杂，测试准备与参数依赖难维护 | 商业版通过公共夹具、业务流画布、SQL 节点和测试数据组织接口场景 |
| 回归测试依赖重复操作，执行过程难追踪 | 使用用例、套件、任务与定时计划组织执行，集中查看进度与产出 |
| 项目经验停留在个人记忆里 | 使用项目知识库、知识图谱与 Agent 经验库沉淀业务知识和测试经验 |

适用于希望引入 AI 辅助测试、统一管理自动化资产，或围绕核心业务建立回归流程的测试团队。

## 商业版亮点

### 接口自动化：从单接口到完整业务链路

支持接口文档导入与 AI 解析、接口资产管理、公共前置夹具、核心业务流、测试用例、套件与任务。通过可视化画布组织请求与 SQL 节点，管理参数依赖，将注册、登录、下单、支付等步骤串成业务场景。

![商业版接口自动化：用户下单支付流程的可视化编排](assets/screenshots/commercial-api-workflow.jpg)

### Web 自动化：让功能用例进入浏览器执行

支持 AI 生成自动化脚本、脚本执行与自愈入口，以及页面、元素、用例、套件、任务和报表管理。把分散的脚本整理为可维护的测试资产，再按业务组织回归。

![商业版 Web 自动化：用例、脚本生成与执行管理](assets/screenshots/commercial-web-automation.jpg)

### 性能测试：统一配置协议、负载与验收标准

提供 HTTP、WebSocket、MQTT、TCP、gRPC 协议配置入口，支持压测环境、数据集、场景、计划与执行报告。通过负载模型、SLA 阈值和数据驱动配置表达测试目标。

![商业版性能测试：协议选择、负载模型、SLA 与数据驱动配置](assets/screenshots/commercial-performance-editor.jpg)

*此图为新建场景配置页；协议与参数的实际执行需要配置对应环境和压测资源。*

### 功能测试、知识库与 App 自动化协同

- **功能测试**：从文档提取需求，AI 生成与评审用例，结构化管理前置条件、步骤、预期结果和测试数据。
- **项目知识库**：文档分块入库、向量与全文检索、知识问答、实体关系图谱，让项目上下文能够被查询与复用。
- **App 自动化**：设备管理、自然语言操作台、录制沉淀、用例与套件回放、执行记录，支持结合宿主机 Agent 接入设备。
- **AI 与执行监控**：统一查看 AI 任务、执行任务、Worker 状态和定时计划，追踪执行过程及产出。
- **测试管理**：项目与成员协作、环境配置、测试数据、缺陷跟踪，以及测试资产、执行、缺陷质量和 AI 提效报表。

AI 生成、自愈和分析效果受模型能力、业务上下文与环境配置影响，关键结果应由测试人员评审。

**[立即体验商业版 →](https://www.mstest.vip)　商业版咨询微信：`python771`**
---

**MSAITest 是面向测试团队的 AI 一体化测试平台。** 将需求理解、用例设计、自动化执行、性能压测、缺陷跟踪和质量分析汇聚到同一个项目工作空间，让测试资产持续积累，让日常回归更容易组织与追踪。

**想体验完整产品？访问 [商业版体验站](https://www.mstest.vip)，或添加微信 `python771` 咨询功能、授权与购买。**

## 开源版与商业版

| 能力 | 本仓库开源版 | 商业版 |
| --- | --- | --- |
| 项目、成员、模块与权限 | 包含源码 | 支持 |
| 文档、需求与功能用例 | 包含源码 | 支持 |
| AI 用例生成与评审 | 包含源码，需配置模型 | 支持，需配置模型 |
| 知识检索与知识图谱 | 包含源码 | 支持 |
| AI 助手、任务监控 | 包含保留模块相关源码 | 覆盖完整产品模块 |
| App 设备、操作台、用例与套件 | 包含源码 | 支持完整产品流程 |
| 测试数据、缺陷管理与报表 | 包含保留模块相关源码 | 覆盖完整产品模块 |
| 接口导入、接口测试与业务流编排 | 不包含 | 支持 |
| Web 自动化、页面与元素管理 | 不包含 | 支持 |
| 性能测试、多协议场景与压测计划 | 不包含 | 支持 |
| 授权与购买 | 见仓库现有版权说明 | 微信 `python771` 咨询 |

开源版用于了解项目设计、体验保留模块与参与改进。需要接口、Web、性能测试等完整能力，或希望评估团队使用方案，可直接体验商业版并联系咨询。商业版的交付范围、授权方式与价格以实际沟通为准。

开源版采用前后端分离架构，可配置自己的大模型服务；当前源码快照的运行条件见[开源版开发与运行](#开源版开发与运行)。

## 全部菜单截图

以下 **58 张真实截图**于 **2026 年 10 月 28 日**从 [ai.mstest.vip 演示环境](https://ai.mstest.vip)截取，覆盖全部 14 组导航及其子菜单页面。所有截图保留完整侧栏；压测数据集在两个菜单中共用同一页面。

截图中的统计、任务状态与示例数据仅展示拍摄时的演示环境；空列表和未连接设备的页面保留真实状态。演示环境的数据、账号与配置不随本仓库分发。商业版体验统一访问 **[www.mstest.vip](https://www.mstest.vip)**。

按模块展开查看，点击图片可查看大图。

<details>
<summary><strong>项目概览</strong> · 1 张界面截图</summary>

#### 项目概览

![项目概览 · 项目概览](assets/screenshots/commercial-overview.jpg)

</details>

<details>
<summary><strong>数据报表</strong> · 4 张界面截图</summary>

#### 测试资产

![数据报表 · 测试资产](assets/screenshots/commercial-reports.jpg)

#### 执行汇总

![数据报表 · 执行汇总](assets/screenshots/commercial-report-execution.jpg)

#### 缺陷质量

![数据报表 · 缺陷质量](assets/screenshots/commercial-report-quality.jpg)

#### AI 提效

![数据报表 · AI 提效](assets/screenshots/commercial-report-ai.jpg)

</details>

<details>
<summary><strong>AI Agent 中心</strong> · 2 张界面截图</summary>

#### AI 智能助手

![AI Agent 中心 · AI 智能助手](assets/screenshots/commercial-ai-assistant.jpg)

#### Agent 经验

![AI Agent 中心 · Agent 经验](assets/screenshots/commercial-agent-experience.jpg)

</details>

<details>
<summary><strong>任务监控中心</strong> · 4 张界面截图</summary>

#### Worker 节点监控

![任务监控中心 · Worker 节点监控](assets/screenshots/commercial-worker-monitor.jpg)

#### Agent 任务监控

![任务监控中心 · Agent 任务监控](assets/screenshots/commercial-task-monitor.jpg)

#### 用例执行监控

![任务监控中心 · 用例执行监控](assets/screenshots/commercial-execution-monitor.jpg)

#### 定时任务

![任务监控中心 · 定时任务](assets/screenshots/commercial-schedules.jpg)

</details>

<details>
<summary><strong>项目配置</strong> · 6 张界面截图</summary>

#### 成员管理

![项目配置 · 成员管理](assets/screenshots/commercial-members.jpg)

#### 模块管理

![项目配置 · 模块管理](assets/screenshots/commercial-project-config.jpg)

#### 环境管理

![项目配置 · 环境管理](assets/screenshots/commercial-environments.jpg)

#### 数据库连接

![项目配置 · 数据库连接](assets/screenshots/commercial-db-connections.jpg)

#### 全局函数

![项目配置 · 全局函数](assets/screenshots/commercial-global-functions.jpg)

#### 全局 SQL

![项目配置 · 全局 SQL](assets/screenshots/commercial-global-sql.jpg)

</details>

<details>
<summary><strong>项目知识库</strong> · 4 张界面截图</summary>

#### 项目文档

![项目知识库 · 项目文档](assets/screenshots/commercial-documents.jpg)

#### 知识内容

![项目知识库 · 知识内容](assets/screenshots/commercial-knowledge-content.jpg)

#### 知识检索

![项目知识库 · 知识检索](assets/screenshots/commercial-knowledge-search.jpg)

#### 知识图谱

![项目知识库 · 知识图谱](assets/screenshots/knowledge-graph.jpg)

</details>

<details>
<summary><strong>AI 造数中心</strong> · 3 张界面截图</summary>

#### 压测数据集

![AI 造数中心 · 压测数据集](assets/screenshots/commercial-load-data.jpg)

#### 文件数据集

![AI 造数中心 · 文件数据集](assets/screenshots/commercial-file-data.jpg)

#### 测试数据集

![AI 造数中心 · 测试数据集](assets/screenshots/commercial-test-data.jpg)

</details>

<details>
<summary><strong>功能测试</strong> · 3 张界面截图</summary>

#### 需求管理

![功能测试 · 需求管理](assets/screenshots/requirements.jpg)

#### 用例管理

![功能测试 · 用例管理](assets/screenshots/functional-cases.jpg)

#### 用例详情与步骤（补充）

![功能测试 · 用例详情与步骤（补充）](assets/screenshots/functional-case-detail.jpg)

</details>

<details>
<summary><strong>Web 自动化</strong> · 6 张界面截图</summary>

#### 自动化用例

![Web 自动化 · 自动化用例](assets/screenshots/commercial-web-automation.jpg)

#### 页面管理

![Web 自动化 · 页面管理](assets/screenshots/commercial-web-pages.jpg)

#### 元素管理

![Web 自动化 · 元素管理](assets/screenshots/commercial-web-elements.jpg)

#### 测试套件

![Web 自动化 · 测试套件](assets/screenshots/commercial-web-suites.jpg)

#### 测试任务

![Web 自动化 · 测试任务](assets/screenshots/commercial-web-tasks.jpg)

#### 测试报表

![Web 自动化 · 测试报表](assets/screenshots/commercial-web-reports.jpg)

</details>

<details>
<summary><strong>接口自动化</strong> · 9 张界面截图</summary>

#### 接口导入

![接口自动化 · 接口导入](assets/screenshots/commercial-api-import.jpg)

#### 接口管理

![接口自动化 · 接口管理](assets/screenshots/commercial-api-management.jpg)

#### 公共夹具

![接口自动化 · 公共夹具](assets/screenshots/commercial-api-fixtures.jpg)

#### 核心业务流

![接口自动化 · 核心业务流](assets/screenshots/commercial-api-flows.jpg)

#### 业务流可视化编排（补充）

![接口自动化 · 业务流可视化编排（补充）](assets/screenshots/commercial-api-workflow.jpg)

#### 测试用例

![接口自动化 · 测试用例](assets/screenshots/commercial-api-cases.jpg)

#### 测试套件

![接口自动化 · 测试套件](assets/screenshots/commercial-api-suites.jpg)

#### 测试任务

![接口自动化 · 测试任务](assets/screenshots/commercial-api-tasks.jpg)

#### 测试报表

![接口自动化 · 测试报表](assets/screenshots/commercial-api-reports.jpg)

</details>

<details>
<summary><strong>性能测试</strong> · 6 张界面截图</summary>

#### 压测环境

![性能测试 · 压测环境](assets/screenshots/commercial-load-environments.jpg)

#### 压测数据集

![性能测试 · 压测数据集](assets/screenshots/commercial-load-data.jpg)

#### 压测场景

![性能测试 · 压测场景](assets/screenshots/commercial-performance.jpg)

#### 压测场景配置（补充）

![性能测试 · 压测场景配置（补充）](assets/screenshots/commercial-performance-editor.jpg)

#### 压测计划

![性能测试 · 压测计划](assets/screenshots/commercial-load-plans.jpg)

#### 执行报告

![性能测试 · 执行报告](assets/screenshots/commercial-load-reports.jpg)

</details>

<details>
<summary><strong>App 自动化</strong> · 5 张界面截图</summary>

#### 设备管理

![App 自动化 · 设备管理](assets/screenshots/commercial-app-devices.jpg)

#### 智能操作台

![App 自动化 · 智能操作台](assets/screenshots/app-console.jpg)

#### 测试用例

![App 自动化 · 测试用例](assets/screenshots/commercial-app-cases.jpg)

#### 测试套件

![App 自动化 · 测试套件](assets/screenshots/commercial-app-suites.jpg)

#### 执行记录

![App 自动化 · 执行记录](assets/screenshots/commercial-app-reports.jpg)

</details>

<details>
<summary><strong>常用工具</strong> · 5 张界面截图</summary>

#### JSON 格式化

![常用工具 · JSON 格式化](assets/screenshots/commercial-tools.jpg)

#### 文本 Diff

![常用工具 · 文本 Diff](assets/screenshots/commercial-tools-diff.jpg)

#### 编解码工具

![常用工具 · 编解码工具](assets/screenshots/commercial-tools-codec.jpg)

#### 时间戳转换

![常用工具 · 时间戳转换](assets/screenshots/commercial-tools-timestamp.jpg)

#### Hash 计算

![常用工具 · Hash 计算](assets/screenshots/commercial-tools-hash.jpg)

</details>

<details>
<summary><strong>缺陷管理</strong> · 1 张界面截图</summary>

#### 缺陷管理

![缺陷管理 · 缺陷管理](assets/screenshots/commercial-bugs.jpg)

</details>

## 商业版咨询

**完整能力体验：[www.mstest.vip](https://www.mstest.vip)**  
**咨询与购买微信：`python771`**

欢迎带着你的测试场景来交流，例如接口业务流回归、Web 自动化、App 测试或性能压测。添加微信时可备注「MSAITest 商业版」，并说明团队规模、希望使用的模块和部署需求，便于沟通适合的产品方案。

## 开源版开发与运行

<details>
<summary><strong>展开查看技术栈、目录结构与本地启动步骤</strong></summary>

以下说明仅适用于本仓库保留的源码模块。开始部署前，请先阅读[当前源码快照说明](#当前源码快照说明)。

### 技术栈

| 层次 | 技术 |
| --- | --- |
| 前端 | Vue 3、TypeScript、Vite、Element Plus、Pinia、ECharts |
| 后端 | FastAPI、Pydantic、SQLAlchemy、Alembic |
| AI 编排 | LangChain、LangGraph、用户级大模型配置 |
| 异步任务 | Celery、Redis、SSE / WebSocket |
| 数据存储 | MySQL、Redis、本地文件或腾讯云 COS |
| 知识检索 | MySQL 全文索引、向量存储与 NumPy 计算 |
| 设备代理 | Node.js、TypeScript、Midscene、ADB / HDC / iOS 相关组件 |

```mermaid
flowchart LR
    Web[Web 工作台] --> API[FastAPI 业务服务]
    API --> DB[(MySQL)]
    API --> Redis[(Redis)]
    Redis --> AI[Celery AI Worker]
    AI --> LLM[大模型服务]
    AI --> DB
    Redis --> App[Celery App Worker]
    App --> Gateway[AppGateway]
    Gateway <-->|WebSocket| Agent[宿主机 App Agent]
    Agent --> Device[测试设备]
```

### 目录结构

```text
.
├── assets/                 # README 使用的标识与界面截图
├── frontend/               # Vue 前端
├── backend/
│   ├── app/
│   │   ├── api/            # 业务接口
│   │   ├── ai_core/        # AI 助手、任务图与运行时
│   │   ├── models/         # 数据模型
│   │   ├── services/       # 业务服务
│   │   ├── gateway/        # App 网关组件
│   │   └── tasks/          # Celery 任务
│   ├── alembic/            # 数据库迁移脚本
│   └── tests/              # 后端测试
├── app-agent/              # 宿主机设备代理
└── deploy/                 # Docker Compose 与 Nginx 配置
```

### 本地运行

#### 环境要求

| 环境 | 要求 |
| --- | --- |
| Python | 3.13 或更高，建议使用 3.13 |
| Node.js | 建议 22.12 或更高版本 |
| pnpm | 建议 10.x |
| Python 包管理 | uv |
| MySQL | 8.0 或更高，需先创建数据库与应用账号 |
| Redis | 建议 7.x |

#### 1. 获取代码

克隆仓库后进入项目根目录。以下命令中的目录均相对仓库根目录。

#### 2. 配置并启动后端

```bash
cd backend
uv sync --frozen
cp .env.example .env
```

编辑 `backend/.env`，填写自己的配置：

| 配置项 | 说明 |
| --- | --- |
| `db_host`、`db_port`、`db_user`、`db_password`、`database` | MySQL 连接参数 |
| `SECRET_KEY` | 自行生成的随机签名密钥，可使用 `openssl rand -hex 32` |
| `admin_username`、`admin_password`、`admin_email` | 首次初始化时创建的管理员信息 |
| `REDIS_URL` | Redis 连接地址 |
| `CELERY_BROKER_URL`、`CELERY_RESULT_BACKEND` | Celery 消息与结果存储地址 |
| `BACKEND_CORS_ORIGINS` | 前端访问来源，本地可设为 `http://localhost:5173` |

配置键名区分大小写，按 `.env.example` 中的名称填写。管理员初始化配置只用于首次创建账号，后续修改配置文件不会直接更改已有账号密码。

```bash
# 在 backend/ 下运行
uv run uvicorn main:app --host 127.0.0.1 --port 8888
```

服务启动时会执行基础建表与种子数据初始化。开发环境下可访问 `http://127.0.0.1:8888/docs` 查看业务接口文档。

> 基础建表不等同于完整数据库迁移，知识库全文索引还依赖迁移脚本。当前快照缺少的迁移配置见[当前源码快照说明](#当前源码快照说明)。

#### 3. 启动后台任务

另开终端，在 `backend/` 中启动 AI Worker：

```bash
uv run celery -A app.tasks.celery_app worker -Q ai_tasks --loglevel=info
```

需要运行 App 自动化时，再启动 App Worker：

```bash
uv run celery -A app.tasks.celery_app worker -Q app_tasks --loglevel=info
```

需要定时任务派发和任务维护时，单独启动一个 Beat 进程：

```bash
uv run celery -A app.tasks.celery_app beat --loglevel=info
```

同一部署环境中只运行一个 Beat 实例。

#### 4. 启动前端

另开终端，在项目根目录进入 `frontend/`：

```bash
cd frontend
pnpm install --frozen-lockfile
cp .env.example .env
pnpm dev --host 127.0.0.1 --port 5173
```

访问 `http://localhost:5173`，使用自己在 `backend/.env` 中配置的初始管理员账号登录。前端开发代理默认连接业务后端 `127.0.0.1:8888`。

#### 5. 配置大模型

登录后进入「大模型配置」，根据需要设置模型服务地址、模型名称和 API Key：

- **文本模型**：需求提取、用例生成、用例评审与 AI 助手。
- **视觉模型**：图片或原型相关的理解能力。
- **嵌入模型**：知识库向量化与检索。

不同功能会使用不同类型的模型，所需能力和参数以配置页面提示为准。

#### 6. 配置 App Agent（可选）

在连接设备的宿主机上执行：

```bash
cd app-agent
npm ci
cp agent.config.example.json agent.config.json
```

在平台的设备管理中创建执行机，将获得的 Agent Token 和网关地址填写到 `agent.config.json`，然后启动：

```bash
npm start
```

Android 设备需要 ADB；可自行安装，或使用 `node scripts/populate-sdks.mjs` 获取。HarmonyOS 与 iOS 设备需分别准备对应的工具和运行环境。

App 执行依赖独立的 AppGateway。当前代码快照尚需补齐网关启动入口，不能仅启动业务 API 后直接连接设备。

</details>

### 当前源码快照说明

当前开源精简版保留了业务源码与环境模板，不包含开发资料、真实 `.env`、模型密钥、设备配置、数据库备份或在线演示站的业务数据。

以下事项仍影响完整部署：

- **数据库迁移**：已保留迁移脚本，但缺少 `backend/alembic.ini`，使用 Alembic 和相关部署流程前需要补齐配置。基础自动建表不会代替知识库全文索引迁移。
- **App 网关**：已保留 `backend/app/gateway/` 组件，但缺少 `backend/gateway_main.py` 启动入口，App 端到端执行仍需完成网关接线。
- **容器部署**：`deploy/` 中的数据库初始化依赖迁移配置，需先完成上述事项。

保留模块的 372 项后端测试及前端生产构建已通过；真实数据库、外部模型服务和设备的全链路部署尚未验证，前端仍有原项目已有的类型诊断。

<details>
<summary>开发验证命令</summary>

在相应目录执行：

```bash
# backend/：不依赖真实 MySQL 的测试集合
uv run pytest -o addopts='' -p no:cacheprovider tests \
  --ignore=tests/knowledge/test_isolation_mysql.py

# frontend/：生产构建
pnpm build

# app-agent/：设备代理单元测试
npm test
```

</details>

## 参与贡献

欢迎通过 Issue 反馈问题或建议，通过 Pull Request 参与改进。反馈时请提供复现步骤、预期结果、实际结果和必要的日志，并移除账号凭据与密钥。

如果这个项目对你有帮助，欢迎 Star，也欢迎将项目分享给需要 AI 测试工具的同事。

## 版权与授权

本仓库目前先公开源码，保留现有版权及用途说明，暂不新增统一的 `LICENSE` 文件。部分源文件保留课程配套代码的版权与用途限制；使用、修改与再分发前，请先确认适用授权并保留现有声明。

商业版授权与购买咨询：微信 **`python771`**。

---

<p align="center">
  <strong>MSAITest · 让 AI 参与测试全流程</strong><br />
  <a href="https://www.mstest.vip">体验商业版</a> · 微信 python771
</p>
