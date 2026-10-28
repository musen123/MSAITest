/**
 * AI 任务中心共享元数据
 *
 * task_type / status / result_ref.kind 的展示映射，列表页与详情页共用。
 * 与后端 registry（app/ai_core/graphs/）保持同步：新增 task_type 时在此补一行。
 */
import type { Router } from 'vue-router';
import type { AiTask, AiTaskStatus } from '@/types/ai-task';
export type MetaColor = 'brand' | 'info' | 'purple' | 'warning' | 'success' | 'danger';
// ============ 任务类型 ============
export interface TaskTypeMeta {
    label: string;
    icon: string;
    color: MetaColor;
}
export const TASK_TYPE_META: Record<string, TaskTypeMeta> = {
    // 功能测试域
    parse_document: { label: '文档解析', icon: 'i-solar-document-text-bold', color: 'info' },
    understand_requirement: { label: '需求理解', icon: 'i-solar-lightbulb-bolt-bold', color: 'info' },
    generate_case: { label: '功能用例生成', icon: 'i-app-test-case', color: 'purple' },
    review_cases: { label: 'AI 用例评审', icon: 'i-solar-checklist-bold', color: 'purple' },
    extract_requirements: { label: 'AI 需求盘点', icon: 'i-solar-radar-2-bold', color: 'purple' },
    // App 自动化域
    run_app_script: { label: 'App 用例回放', icon: 'i-solar-smartphone-2-bold', color: 'success' },
    run_app_suite: { label: 'App 套件执行', icon: 'i-solar-play-circle-bold', color: 'success' },
    explore_app_script: { label: 'App 探索生成', icon: 'i-solar-compass-bold', color: 'brand' },
    // 测试数据中心域（AI 造数）
    generate_test_files: { label: 'AI 造测试文件', icon: 'i-solar-folder-with-files-bold', color: 'purple' },
    generate_test_dataset: { label: 'AI 造测试数据集', icon: 'i-solar-database-bold', color: 'purple' },
    // 知识库域
    kb_ingest: { label: '知识入库', icon: 'i-solar-book-bookmark-bold', color: 'info' },
    kb_extract: { label: '知识图谱抽取', icon: 'i-solar-structure-bold', color: 'info' },
    // 演示
    demo: { label: '演示任务', icon: 'i-app-ai-spark', color: 'brand' }
};
/** 执行类任务（与后端 registry.exec_task_types() 同步：kind ∈ exec / app_exec） */
export const EXEC_TASK_TYPES = new Set([
    'run_app_script',
    'run_app_suite',
    'explore_app_script'
]);
// ============ 详情页布局档案 ============
// 详情页的共享外壳（头部/操作按钮/生命周期）对所有类型一致；壳内各区块是否展示
// 由此按 task_type 声明。未声明的类型全部展示（保持既有行为，零回归）。
// 需要整体接管壳内内容的特殊类型走 detail-renderers.ts 的 BODY_RENDERERS。
export interface TaskLayoutProfile {
    /** 隐藏 2×2 统计小卡（进度 / 耗时 / 阶段 / 模型） */
    hideStats?: boolean;
    /** 隐藏执行阶段横向时间轴 */
    hideStages?: boolean;
    /** 隐藏运行日志列（隐藏后 AI 实时输出占满整行） */
    hideLogs?: boolean;
    /** 隐藏 AI 实时输出列（隐藏后运行日志占满整行） */
    hideConsole?: boolean;
    /** 隐藏产出结果面板（结果已由定制实时区呈现时避免重复） */
    hideResult?: boolean;
}
export const TASK_LAYOUT: Record<string, TaskLayoutProfile> = {
    // App 自动化：观战投屏移到右侧常驻手机框（DEVICE_PANEL_RENDERERS），左主区只留
    // 统计卡 + 运行日志（模型思考）+ 产出结果。故隐藏中间「AI 实时输出」列（投屏已在
    // 右侧，避免重复）与阶段轴（回放/套件/探索仅寥寥几段，价值低于占位）。
    run_app_script: { hideStages: true, hideConsole: true },
    run_app_suite: { hideStages: true, hideConsole: true },
    explore_app_script: { hideStages: true, hideConsole: true },
};
export function layoutProfile(t?: string | null): TaskLayoutProfile {
    return (t && TASK_LAYOUT[t]) || {};
}
const FALLBACK_TYPE: TaskTypeMeta = { label: '', icon: 'i-app-ai-brain', color: 'brand' };
export function typeMeta(t?: string | null): TaskTypeMeta {
    if (!t)
        return { ...FALLBACK_TYPE, label: '—' };
    return TASK_TYPE_META[t] || { ...FALLBACK_TYPE, label: t };
}
/** 筛选下拉选项（不含 demo） */
export const TASK_TYPE_OPTIONS = Object.entries(TASK_TYPE_META)
    .filter(([k]) => k !== 'demo')
    .map(([value, m]) => ({ value, label: m.label }));
/** 按任务类别拆分的下拉选项（任务中心 tabs 联动） */
export function taskTypeOptions(kind: 'ai' | 'exec' | ''): {
    value: string;
    label: string;
}[] {
    if (!kind)
        return TASK_TYPE_OPTIONS;
    return TASK_TYPE_OPTIONS.filter((o) => EXEC_TASK_TYPES.has(o.value) === (kind === 'exec'));
}
// ============ 状态 ============
export const STATUS_META: Record<AiTaskStatus, {
    label: string;
    color: MetaColor;
}> = {
    pending: { label: '排队中', color: 'info' },
    running: { label: '运行中', color: 'brand' },
    succeeded: { label: '已成功', color: 'success' },
    failed: { label: '失败', color: 'danger' },
    canceled: { label: '已取消', color: 'warning' },
};
export function statusLabel(s: string): string {
    return STATUS_META[s as AiTaskStatus]?.label || s;
}
export function statusColor(s: string): MetaColor {
    return STATUS_META[s as AiTaskStatus]?.color || 'info';
}
export const STATUS_OPTIONS = Object.entries(STATUS_META).map(([value, m]) => ({
    value,
    label: m.label,
}));
// ============ result_ref.kind → 产出跳转 ============
export interface RefKindMeta {
    label: string;
    color: MetaColor;
    /** 跳转按钮文案；无则不可跳转 */
    jumpText?: string;
    /** 构造跳转，ref 为 result_ref 原始对象 */
    jump?: (router: Router, projectId: number, ref: Record<string, unknown>) => void;
}
export const REF_KIND_META: Record<string, RefKindMeta> = {
    func_document: {
        label: '功能文档',
        color: 'info',
        jumpText: '查看解析文档',
        jump: (router, id) => router.push({ name: 'FuncTestDocuments', params: { id } }),
    },
    func_requirement: {
        label: '需求',
        color: 'info',
        jumpText: '查看需求详情',
        jump: (router, id, ref) => ref.requirement_id
            ? router.push({ name: 'FuncTestRequirementDetail', params: { id, reqId: ref.requirement_id as number } })
            : router.push({ name: 'FuncTestRequirements', params: { id } }),
    },
    func_cases: {
        label: '功能用例',
        color: 'purple',
        jumpText: '查看生成用例列表',
        jump: (router, id) => router.push({ name: 'FuncTestCases', params: { id } }),
    },
    app_execution: {
        label: 'App 执行记录',
        color: 'success',
        jumpText: '查看执行记录',
        jump: (router, id) => router.push({ name: 'AppExecutions', params: { id } }),
    },
    app_suite_execution: {
        label: 'App 套件执行',
        color: 'success',
        jumpText: '查看执行记录',
        jump: (router, id) => router.push({ name: 'AppExecutions', params: { id } }),
    },
    app_script: {
        label: 'App 用例',
        color: 'brand',
        jumpText: '查看生成用例',
        jump: (router, id) => router.push({ name: 'AppCases', params: { id } }),
    },
    test_dataset: {
        label: '测试数据集',
        color: 'purple',
        jumpText: '查看数据集',
        jump: (router, id) => router.push({ name: 'TestDataDatasets', params: { id } }),
    },
    test_files: {
        label: '测试文件资产',
        color: 'purple',
        jumpText: '查看文件资产',
        jump: (router, id) => router.push({ name: 'TestDataFiles', params: { id } }),
    },
    kb_document: {
        label: '知识文档',
        color: 'info',
        jumpText: '查看知识文档',
        jump: (router, id) => router.push({ name: 'KnowledgeDocuments', params: { id } }),
    },
    requirements: {
        label: '需求草稿',
        color: 'purple',
        jumpText: '查看需求列表',
        jump: (router, id) => router.push({ name: 'FuncTestRequirements', params: { id } }),
    }
};
export function refKindMeta(ref?: Record<string, unknown> | null): RefKindMeta | null {
    const kind = ref?.kind as string | undefined;
    if (kind && REF_KIND_META[kind])
        return REF_KIND_META[kind];
    // 兼容早期无 kind 的 ref
    if (ref?.doc_id)
        return REF_KIND_META.func_document!;
    if (ref?.case_ids)
        return REF_KIND_META.func_cases!;
    // App 域老数据（补 kind 前入库）：字段名唯一可辨（web/api ref 均带 kind）
    if (ref?.suite_execution_id)
        return REF_KIND_META.app_suite_execution!;
    if (ref?.execution_id)
        return REF_KIND_META.app_execution!;
    if (ref?.script_id)
        return REF_KIND_META.app_script!;
    return null;
}
// ============ 产出摘要（列表页「产出」列） ============
export interface Metric {
    label: string;
    value: unknown;
    unit?: string;
    color?: string | null;
    highlight?: boolean;
}
export function resultMetrics(summary?: Record<string, unknown> | null): Metric[] {
    const m = summary?.metrics;
    return Array.isArray(m) ? (m as Metric[]) : [];
}
/** 列表页产出列主指标：优先 highlight 的 metric，其次第一个 metric */
export function primaryMetric(task: AiTask): Metric | null {
    const ms = resultMetrics(task.result_summary);
    if (!ms.length)
        return null;
    return ms.find((m) => m.highlight) || ms[0] || null;
}
// ============ 时间格式化 ============
export function formatDurationMs(ms: number): string {
    const sec = Math.floor(Math.max(0, ms) / 1000);
    if (sec < 60)
        return `${sec}s`;
    if (sec < 3600)
        return `${Math.floor(sec / 60)}m${String(sec % 60).padStart(2, '0')}s`;
    return `${Math.floor(sec / 3600)}h${Math.floor((sec % 3600) / 60)}m`;
}
export function durationText(task: Pick<AiTask, 'started_at' | 'completed_at'>): string {
    if (!task.started_at)
        return '—';
    const start = new Date(task.started_at).getTime();
    const end = task.completed_at ? new Date(task.completed_at).getTime() : Date.now();
    return formatDurationMs(end - start);
}
export function formatDateTime(s?: string | null): string {
    if (!s)
        return '—';
    const d = new Date(s);
    const p = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}
export function formatTime(s: string): string {
    const d = new Date(s);
    const p = (n: number) => String(n).padStart(2, '0');
    return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}
