/**
 * AI 任务详情页 — 按任务类型注册的定制渲染器
 *
 * 详情页骨架（头部/统计卡/阶段/日志/操作）所有任务共享；
 * 「AI 实时输出」与「产出结果」两个区域可按 task_type 挂定制组件：
 *   - STREAM_RENDERERS：替换默认 Markdown 控制台（props: events / active）
 *   - RESULT_RENDERERS：替换默认 metrics 卡片网格（props: summary / resultRef）
 * 未注册的任务类型自动回退通用渲染。
 *
 * 仅详情页 import 本文件（组件引用别放进 task-meta.ts，避免列表页 chunk 变大）。
 */
import type { Component } from 'vue';
import AppExecStreamView from './renderers/AppExecStreamView.vue';
import AppTaskDevicePanel from './renderers/AppTaskDevicePanel.vue';
/** task_type → 实时输出区渲染器 */
export const STREAM_RENDERERS: Record<string, Component> = {
    // App 自动化三态：观战直播（只读投屏，不占设备锁；模型日志走左侧运行日志）
    run_app_script: AppExecStreamView,
    run_app_suite: AppExecStreamView,
    explore_app_script: AppExecStreamView
};
/** task_type → 产出结果区渲染器 */
export const RESULT_RENDERERS: Record<string, Component> = {};
/**
 * task_type → 右侧常驻设备面板渲染器。
 *
 * 注册后详情页正文变为「左主区 + 右手机面板」两栏：右栏用手机框包住观战投屏，
 * 常驻页面右侧随任务运行直播真机画面。App 自动化三类专用（投屏从中间实时输出区
 * 移到右侧手机框，故这些类型的布局档案同步 hideConsole 避免重复）。
 * 组件 props：task / active。
 */
export const DEVICE_PANEL_RENDERERS: Record<string, Component> = {
    run_app_script: AppTaskDevicePanel,
    run_app_suite: AppTaskDevicePanel,
    explore_app_script: AppTaskDevicePanel,
};
/**
 * task_type → 整体接管渲染器（逃生舱）。
 *
 * 注册后，详情页状态色条以下的整块（统计卡/阶段/日志/实时输出/结果/参数）全部
 * 交给该组件自行编排，仅共享头部/操作按钮/生命周期（SSE 订阅、取消/重试/删除）。
 * 用于内容形态与通用骨架差异极大的类型（如需要整屏投屏、专属大盘的场景）。
 * 组件 props：task / events / active / summary / resultRef / projectId。
 *
 * STREAM/RESULT/BODY 三者优先级：BODY 存在时独占，忽略前两者与布局档案。
 * 目前无类型走此路（各特殊类型用 STREAM+RESULT+布局档案已足够）；这是预留扩展点。
 */
export const BODY_RENDERERS: Record<string, Component> = {};
