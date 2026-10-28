/**
 * 路由配置
 *
 * AI 智能测试平台 - 路由配置
 */
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router';
import { useUserStore } from '@/stores/user';
import { ElMessage } from 'element-plus';
/**
 * 路由元信息类型
 */
export interface RouteMeta {
    /** 页面标题 */
    title?: string;
    /** 是否需要认证 */
    requiresAuth?: boolean;
    /** 所需权限列表 */
    permissions?: string[];
    /** 所需角色列表 */
    roles?: string[];
    /** 是否隐藏（不在菜单中显示） */
    hidden?: boolean;
    /** 图标 */
    icon?: string;
    /** 排序 */
    sort?: number;
    /** 任务监控中心分页：ai=AI 任务 / exec=用例执行 */
    taskKind?: 'ai' | 'exec';
    /** 允许其他任意属性 */
    [key: string]: unknown;
}
// 路由配置
const routes: RouteRecordRaw[] = [
    {
        path: '/',
        redirect: '/workspace/projects',
    },
    // ==================== 认证授权路由 ====================
    {
        path: '/login',
        name: 'Login',
        component: () => import('@/views/auth/LoginView.vue'),
        meta: {
            title: '登录',
            requiresAuth: false,
            hidden: true,
        } as RouteMeta,
    },
    {
        path: '/register',
        name: 'Register',
        component: () => import('@/views/auth/RegisterView.vue'),
        meta: {
            title: '注册',
            requiresAuth: false,
            hidden: true,
        } as RouteMeta,
    },
    {
        path: '/welcome',
        name: 'Welcome',
        component: () => import('@/views/auth/WelcomeView.vue'),
        meta: {
            title: '欢迎使用',
            requiresAuth: true,
            hidden: true,
        } as RouteMeta,
    },
    // ==================== 工作台路由 ====================
    {
        path: '/workspace',
        component: () => import('@/layouts/WorkspaceLayout.vue'),
        meta: {
            requiresAuth: true,
        } as RouteMeta,
        children: [
            {
                path: 'projects',
                name: 'Projects',
                component: () => import('@/views/workspace/ProjectsView.vue'),
                meta: {
                    title: '项目管理',
                    icon: 'FolderOpened',
                    permissions: ['project:view'],
                } as RouteMeta,
            },
            {
                path: 'profile',
                name: 'Profile',
                component: () => import('@/views/workspace/ProfileView.vue'),
                meta: {
                    title: '个人中心',
                    icon: 'User',
                } as RouteMeta,
            },
            {
                path: 'llm-config',
                name: 'LlmConfig',
                component: () => import('@/views/workspace/LlmConfigView.vue'),
                meta: {
                    title: '大模型配置',
                    icon: 'Setting',
                } as RouteMeta,
            },
            {
                path: 'permissions',
                name: 'Permissions',
                component: () => import('@/views/workspace/PermissionsView.vue'),
                meta: {
                    title: '权限管理',
                    icon: 'Key',
                    permissions: ['user:view'],
                } as RouteMeta,
            },
            {
                path: 'users',
                name: 'Users',
                component: () => import('@/views/users/UserListView.vue'),
                meta: {
                    title: '用户管理',
                    icon: 'UserFilled',
                    permissions: ['user:view'],
                } as RouteMeta,
            },
            {
                path: 'users/:id',
                name: 'UserDetail',
                component: () => import('@/views/users/UserDetailView.vue'),
                meta: {
                    title: '用户详情',
                    hidden: true,
                    permissions: ['user:view'],
                } as RouteMeta,
            },
            {
                path: 'operation-logs',
                name: 'OperationLogs',
                component: () => import('@/views/workspace/OperationLogsView.vue'),
                meta: {
                    title: '操作日志',
                    icon: 'Notebook',
                } as RouteMeta,
            },
            // 开发调试
            {
                path: 'dev/code-editor',
                name: 'CodeEditorDemo',
                component: () => import('@/views/dev/CodeEditorDemo.vue'),
                meta: {
                    title: '代码编辑器演示',
                    icon: 'Edit',
                } as RouteMeta,
            },
            {
                path: 'dev/design-system',
                name: 'DesignSystem',
                component: () => import('@/views/dev/DesignSystemView.vue'),
                meta: {
                    title: '视觉系统预览',
                    icon: 'MagicStick',
                } as RouteMeta,
            },
        ],
    },
    // ==================== 项目工作空间路由（独立页面）====================
    {
        path: '/project-workspace/:id',
        component: () => import('@/views/project-workspace/ProjectWorkspace.vue'),
        meta: {
            requiresAuth: true,
        } as RouteMeta,
        children: [
            // 项目概览（作为默认子路由）
            {
                path: '',
                redirect: { name: 'ProjectOverview' },
            },
            {
                path: 'overview',
                name: 'ProjectOverview',
                component: () => import('@/views/project-workspace/project/ProjectDashboard.vue'),
                meta: {
                    title: '项目概览',
                } as RouteMeta,
            },
            {
                path: 'members',
                name: 'ProjectMembers',
                component: () => import('@/views/project-workspace/project/MembersView.vue'),
                meta: {
                    title: '成员管理',
                } as RouteMeta,
            },
            {
                path: 'modules',
                name: 'ProjectModules',
                component: () => import('@/views/project-workspace/project/ModulesView.vue'),
                meta: {
                    title: '模块管理',
                } as RouteMeta,
            },
            // 测试环境管理
            {
                path: 'environments',
                name: 'Environments',
                component: () => import('@/views/project-workspace/environments/EnvironmentsView.vue'),
                meta: {
                    title: '环境管理',
                } as RouteMeta,
            },
            {
                path: 'environments/:envId',
                name: 'EnvironmentDetail',
                component: () => import('@/views/project-workspace/environments/EnvironmentDetail.vue'),
                meta: {
                    title: '环境详情',
                    hidden: true,
                } as RouteMeta,
            },
            {
                path: 'environments/databases',
                name: 'EnvironmentDatabases',
                component: () => import('@/views/project-workspace/environments/DatabasesView.vue'),
                meta: {
                    title: '数据库连接',
                } as RouteMeta,
            },
            {
                path: 'environments/functions',
                name: 'EnvironmentFunctions',
                component: () => import('@/views/project-workspace/environments/FunctionsView.vue'),
                meta: {
                    title: '全局函数',
                } as RouteMeta,
            },
            // 测试数据中心：文件资产和测试数据集
            {
                path: 'test-data',
                name: 'TestDataFiles',
                component: () => import('@/views/project-workspace/test-data/FileDatasetView.vue'),
                meta: {
                    title: '文件数据集',
                    permissions: ['test_data:view'],
                } as RouteMeta,
            },
            {
                path: 'test-data/datasets',
                name: 'TestDataDatasets',
                component: () => import('@/views/project-workspace/test-data/TestDatasetView.vue'),
                meta: {
                    title: '测试数据集',
                    permissions: ['test_data:view'],
                } as RouteMeta,
            },
            {
                path: 'celery-monitor',
                name: 'CeleryMonitor',
                component: () => import('@/views/project-workspace/system/CeleryMonitorView.vue'),
                meta: {
                    title: 'Worker 监控',
                    permissions: ['system:monitor'],
                } as RouteMeta,
            },
            // App自动化
            {
                path: 'app/console',
                name: 'AppConsole',
                component: () => import('@/views/project-workspace/app/AppConsoleView.vue'),
                meta: {
                    title: '智能操作台',
                    permissions: ['app_test:create'],
                } as RouteMeta,
            },
            {
                path: 'app/pages',
                name: 'AppPages',
                component: () => import('@/views/project-workspace/app/AppPagesView.vue'),
                meta: {
                    title: 'App页面管理',
                } as RouteMeta,
            },
            {
                path: 'app/elements',
                name: 'AppElements',
                component: () => import('@/views/project-workspace/app/AppElementsView.vue'),
                meta: {
                    title: 'App元素管理',
                } as RouteMeta,
            },
            {
                path: 'app/cases',
                name: 'AppCases',
                component: () => import('@/views/project-workspace/app/AppCasesView.vue'),
                meta: {
                    title: 'App自动化测试用例',
                } as RouteMeta,
            },
            {
                path: 'app/suites',
                name: 'AppSuites',
                component: () => import('@/views/project-workspace/app/AppSuitesView.vue'),
                meta: {
                    title: 'App自动化测试套件',
                } as RouteMeta,
            },
            {
                path: 'app/suites/:suiteId',
                name: 'AppSuiteDetail',
                component: () => import('@/views/project-workspace/app/AppSuiteDetailView.vue'),
                meta: {
                    title: 'App套件详情',
                    hidden: true,
                } as RouteMeta,
            },
            {
                path: 'app/executions',
                name: 'AppExecutions',
                component: () => import('@/views/project-workspace/app/AppExecutionsView.vue'),
                meta: {
                    title: 'App自动化测试执行记录',
                } as RouteMeta,
            },
            {
                // 设备管理：设备域本身是全局资源（非项目内），此处挂在项目工作空间
                // App 自动化导航下，作为统一入口；页面按需展示全部设备。
                path: 'app/devices',
                name: 'AppDevices',
                component: () => import('@/views/workspace/device/DeviceListView.vue'),
                meta: {
                    title: '设备管理',
                    permissions: ['app_device:view'],
                } as RouteMeta,
            },
            // ========================== 功能测试模块 ==========================
            {
                path: 'function-test/documents',
                name: 'FuncTestDocuments',
                component: () => import('@/views/project-workspace/function-test/DocumentsView.vue'),
                meta: { title: '功能测试 - 测试文档' } as RouteMeta,
            },
            {
                path: 'function-test/requirements',
                name: 'FuncTestRequirements',
                component: () => import('@/views/project-workspace/function-test/RequirementsView.vue'),
                meta: { title: '功能测试 - 需求管理' } as RouteMeta,
            },
            {
                path: 'function-test/requirements/create',
                name: 'FuncTestRequirementCreate',
                component: () => import('@/views/project-workspace/function-test/RequirementCreateView.vue'),
                meta: { title: '新建需求' } as RouteMeta,
            },
            {
                path: 'function-test/requirements/:reqId',
                name: 'FuncTestRequirementDetail',
                component: () => import('@/views/project-workspace/function-test/RequirementDetailView.vue'),
                meta: { title: '需求详情' } as RouteMeta,
            },
            {
                path: 'function-test/cases',
                name: 'FuncTestCases',
                component: () => import('@/views/project-workspace/function-test/CasesView.vue'),
                meta: { title: '功能测试 - 用例管理' } as RouteMeta,
            },
            {
                path: 'function-test/cases/create',
                name: 'FuncTestCaseCreate',
                component: () => import('@/views/project-workspace/function-test/CaseCreateView.vue'),
                meta: { title: '新建用例' } as RouteMeta,
            },
            {
                path: 'function-test/cases/:caseId',
                name: 'FuncTestCaseDetail',
                component: () => import('@/views/project-workspace/function-test/CaseDetailView.vue'),
                meta: { title: '用例详情' } as RouteMeta,
            },
            // 注：AI 用例生成原独立路由已废弃，改为需求管理页面的弹框
            //     入口：RequirementsView 行内「生成用例」按钮 → CaseGenerateDialog
            //     组件：@/components/func-test/CaseGenerateDialog.vue
            // ========================== AI 中心（公共能力，原 function-test 子能力上移） ==========================
            // 注：旧任务中心（ai/tasks → AiTasksView）已随旧 AI 任务体系下线，
            //     统一使用 ai/task-center（AiTaskCenterView）
            {
                path: 'ai/chat',
                alias: 'function-test/chat',
                name: 'FuncTestChat',
                component: () => import('@/views/project-workspace/function-test/ChatView.vue'),
                meta: { title: 'AI 中心 - AI 助手' } as RouteMeta,
            },
            {
                // AI 任务中心（AI 生成/分析类：文档解析/用例生成/造数/AI分析…）
                path: 'ai/task-center',
                name: 'AiTaskCenter',
                component: () => import('@/views/project-workspace/ai/AiTaskCenterView.vue'),
                meta: { title: 'AI 任务中心', taskKind: 'ai' } as RouteMeta,
            },
            {
                // 执行监控中心：App 用例与套件执行
                path: 'ai/exec-center',
                name: 'AiExecCenter',
                component: () => import('@/views/project-workspace/ai/AiTaskCenterView.vue'),
                meta: { title: '执行监控中心', taskKind: 'exec' } as RouteMeta,
            },
            {
                path: 'ai/task-center/:taskId',
                name: 'AiTaskDetail',
                component: () => import('@/views/project-workspace/ai/AiTaskDetailView.vue'),
                meta: { title: 'AI 中心 - 任务详情' } as RouteMeta,
            },
            // ========================== 项目知识库 ==========================
            {
                path: 'knowledge/documents',
                name: 'KnowledgeDocuments',
                component: () => import('@/views/project-workspace/knowledge/DocumentsView.vue'),
                meta: { title: '知识库 - 内容管理' } as RouteMeta,
            },
            {
                path: 'knowledge/query',
                name: 'KnowledgeQuery',
                component: () => import('@/views/project-workspace/knowledge/QueryView.vue'),
                meta: { title: '知识库 - 检索' } as RouteMeta,
            },
            {
                path: 'knowledge/graph',
                name: 'KnowledgeGraph',
                component: () => import('@/views/project-workspace/knowledge/GraphView.vue'),
                meta: { title: '知识库 - 知识图谱' } as RouteMeta,
            },
            // 缺陷管理
            {
                path: 'bugs',
                name: 'ProjectBugs',
                component: () => import('@/views/project-workspace/BugsView.vue'),
                meta: {
                    title: '缺陷管理',
                } as RouteMeta,
            },
            // 定时任务
            {
                path: 'scheduled-jobs',
                name: 'ScheduledJobs',
                component: () => import('@/views/project-workspace/scheduled/ScheduledJobsView.vue'),
                meta: {
                    title: '定时任务',
                } as RouteMeta,
            },
            // 数据报表
            {
                path: 'reports',
                name: 'ProjectReports',
                component: () => import('@/views/project-workspace/reports/ReportExecutionView.vue'),
                meta: {
                    title: '执行汇总',
                } as RouteMeta,
            },
            {
                path: 'reports/assets',
                name: 'ReportAssets',
                component: () => import('@/views/project-workspace/reports/ReportAssetsView.vue'),
                meta: {
                    title: '测试资产报表',
                } as RouteMeta,
            },
            {
                path: 'reports/quality',
                name: 'ReportQuality',
                component: () => import('@/views/project-workspace/reports/ReportQualityView.vue'),
                meta: {
                    title: '缺陷质量报表',
                } as RouteMeta,
            },
            {
                path: 'reports/ai',
                name: 'ReportAi',
                component: () => import('@/views/project-workspace/reports/ReportAiView.vue'),
                meta: {
                    title: 'AI 提效报表',
                } as RouteMeta,
            },
            // 常用工具
            {
                path: 'tools/json-formatter',
                name: 'JsonFormatter',
                component: () => import('@/views/project-workspace/tools/JsonFormatter.vue'),
                meta: { title: 'JSON 格式化' } as RouteMeta,
            },
            {
                path: 'tools/diff',
                name: 'DiffTool',
                component: () => import('@/views/project-workspace/tools/DiffTool.vue'),
                meta: { title: '文本 Diff' } as RouteMeta,
            },
            {
                path: 'tools/encoder',
                name: 'EncoderDecoder',
                component: () => import('@/views/project-workspace/tools/EncoderDecoder.vue'),
                meta: { title: '编解码工具' } as RouteMeta,
            },
            {
                path: 'tools/timestamp',
                name: 'TimestampConverter',
                component: () => import('@/views/project-workspace/tools/TimestampConverter.vue'),
                meta: { title: '时间戳转换' } as RouteMeta,
            },
            {
                path: 'tools/hash',
                name: 'HashGenerator',
                component: () => import('@/views/project-workspace/tools/HashGenerator.vue'),
                meta: { title: 'Hash 计算器' } as RouteMeta,
            }
        ],
    },
];
// 创建路由实例
const router = createRouter({
    history: createWebHistory(import.meta.env.BASE_URL),
    routes,
});
// 路由守卫
router.beforeEach((to, from, next) => {
    // 设置页面标题
    if (to.meta.title) {
        document.title = `${to.meta.title} - AI 智能测试平台`;
    }
    const userStore = useUserStore();
    const isLoggedIn = userStore.isLoggedIn;
    const requiresAuth = (to.meta as RouteMeta).requiresAuth !== false; // 默认需要认证
    const requiredPermissions = (to.meta as RouteMeta).permissions || [];
    const requiredRoles = (to.meta as RouteMeta).roles || [];
    // 不需要认证的页面直接放行
    if (!requiresAuth) {
        // 如果已登录，访问登录页时跳转到工作台
        if (isLoggedIn && (to.name === 'Login' || to.name === 'Register')) {
            next('/workspace/projects');
            return;
        }
        next();
        return;
    }
    // 需要认证但未登录，跳转到登录页
    if (requiresAuth && !isLoggedIn) {
        ElMessage.warning('请先登录');
        next({
            name: 'Login',
            query: { redirect: to.fullPath }, // 保存原始路径，登录后跳转回去
        });
        return;
    }
    // 检查角色权限
    if (requiredRoles.length > 0) {
        const hasRole = userStore.hasAnyRole(...requiredRoles);
        if (!hasRole) {
            ElMessage.error('没有权限访问');
            next('/workspace/profile');
            return;
        }
    }
    // 检查操作权限
    if (requiredPermissions.length > 0) {
        const hasPermission = userStore.hasAnyPermission(...requiredPermissions);
        if (!hasPermission) {
            ElMessage.error('没有权限访问');
            next('/workspace/profile');
            return;
        }
    }
    next();
});
// 路由后置守卫
router.afterEach(() => {
    // 可以在这里添加页面访问统计等逻辑
    // console.log('Navigation:', from.fullPath, '->', to.fullPath)
});
// 路由错误处理
router.onError((error) => {
    console.error('Router error:', error);
    ElMessage.error('页面加载失败');
});
export default router;
