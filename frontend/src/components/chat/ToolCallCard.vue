<template>
  <div class="tool-card" :class="`status-${block.status}`">
    <div class="tool-header" @click="expanded = !expanded">
      <i
        v-if="block.status === 'streaming'"
        class="i-solar-refresh-linear tool-icon rotating"
      />
      <i
        v-else-if="block.status === 'success'"
        class="i-solar-check-circle-bold tool-icon"
      />
      <i
        v-else-if="block.status === 'error'"
        class="i-solar-close-circle-bold tool-icon"
      />
      <i v-else class="i-solar-info-circle-linear tool-icon" />
      <div class="tool-meta">
        <span class="tool-name">{{ toolLabel }}</span>
        <span class="tool-status">{{ statusLabel }}</span>
      </div>
      <span class="tool-duration">{{ durationText }}</span>
      <i class="i-solar-alt-arrow-down-bold expand-icon" :class="{ expanded }" />
    </div>

    <!-- 动作卡片：工具返回的跳转按钮，无需展开即可见 -->
    <div v-if="block.action" class="tool-action">
      <button class="action-btn" @click.stop="handleAction">
        <i class="i-solar-square-top-down-linear" />
        {{ block.action.label }}
      </button>
    </div>

    <div v-if="expanded" class="tool-body">
      <!-- 输入参数 -->
      <div v-if="block.toolInput" class="tool-section">
        <div class="section-title">
          <i class="i-solar-alt-arrow-right-linear" />
          输入参数
        </div>
        <pre class="json-block">{{ formatJson(block.toolInput) }}</pre>
      </div>

      <!-- 输出结果 -->
      <div v-if="block.toolOutput || block.content" class="tool-section">
        <div class="section-title">
          <i class="i-solar-alt-arrow-down-linear" />
          返回结果
        </div>
        <pre class="json-block">{{ formatJson(block.toolOutput || block.content) }}</pre>
      </div>

      <!-- 错误 -->
      <div v-if="block.errorMessage" class="tool-section">
        <div class="section-title error-title">
          <i class="i-solar-danger-triangle-bold" />
          错误
        </div>
        <pre class="json-block error-block">{{ block.errorMessage }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">import { ref, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import type { UiBlock } from '@/types/chat';
const props = defineProps<{
    block: UiBlock;
}>();
const route = useRoute();
const router = useRouter();
const expanded = ref(false);
/** 工具名 → 中文展示名 */
const TOOL_LABELS: Record<string, string> = {
    get_project_overview: '查询项目概况',
    query_requirements: '查询需求列表',
    get_requirement_detail: '查询需求详情',
    query_func_cases: '查询功能用例',
    query_app_assets: '查询 App 测试资产',
    query_app_devices: '查询接入设备',
    query_bugs: '查询缺陷',
    query_environments: '查询测试环境',
    query_scheduled_jobs: '查询定时任务',
    query_ai_tasks: '查询任务中心',
    query_members: '查询项目成员',
    get_execution_report: '查询执行汇总报表',
    kb_search: '检索知识库',
    query_kb_graph: '查询知识图谱',
    analyze_change_impact: '变更影响分析',
    create_scheduled_job: '创建定时计划',
    update_scheduled_job: '编辑定时计划',
    create_environment: '创建测试环境',
    update_environment: '编辑测试环境',
    kb_ingest_text: '知识库文本入库',
    run_scheduled_job: '触发定时任务',
    toggle_scheduled_job: '启停定时任务',
    create_bug: '创建缺陷',
    review_func_cases: '批量评审用例',
    generate_func_cases: '派发用例生成',
    extract_requirements: 'AI 需求盘点',
    remember: '记住事项',
    recall: '查看已记事项',
    forget: '删除已记事项',
    open_page: '页面导航',
    // 旧会话历史里的已下线工具
    query_all_requirements: '查询需求列表',
    query_exist_cases: '查询已有用例',
    generate_test_cases: '生成测试用例',
    review_cases: '评审用例',
    check_coverage: '覆盖率检查',
    supplement_test_cases: '补充用例',
    save_cases_to_database: '保存用例'
};
const toolLabel = computed(() => {
    const name = props.block.toolName || '';
    return TOOL_LABELS[name] || name || '工具调用';
});
const statusLabel = computed(() => {
    const map: Record<string, string> = {
        streaming: '运行中',
        success: '成功',
        error: '失败',
        interrupted: '已中断',
    };
    return map[props.block.status] || props.block.status;
});
function handleAction() {
    const action = props.block.action;
    if (!action || action.kind !== 'navigate')
        return;
    const projectId = Number(route.params.id);
    if (!projectId) {
        ElMessage.warning('请在项目工作区内使用跳转');
        return;
    }
    router
        .push({
        name: action.route_name,
        params: { id: projectId, ...(action.params || {}) },
    })
        .catch(() => ElMessage.error('页面跳转失败'));
}
const durationText = computed(() => {
    if (!props.block.endedAt) {
        // 运行中：实时显示
        const ms = Date.now() - props.block.startedAt;
        return `${(ms / 1000).toFixed(0)}s`;
    }
    const ms = props.block.endedAt - props.block.startedAt;
    if (ms < 1000)
        return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
});
function formatJson(text: string | undefined): string {
    if (!text)
        return '';
    // 尝试格式化 JSON；非 JSON 则原样返回
    try {
        return JSON.stringify(JSON.parse(text), null, 2);
    }
    catch {
        return text;
    }
}
</script>

<style scoped>
.tool-card {
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: var(--bg-card);
  overflow: hidden;
}

.status-streaming {
  border-color: var(--brand-200);
  background: var(--brand-50);
}

.status-success {
  border-color: var(--color-success-200);
}

.status-error {
  border-color: var(--color-danger-200);
  background: var(--color-danger-50);
}

.tool-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  cursor: pointer;
  user-select: none;
  transition: background 0.2s;
}

.tool-header:hover {
  background: var(--gray-50);
}

.tool-icon {
  font-size: 14px;
  color: var(--text-secondary);
}

.status-streaming .tool-icon {
  color: var(--brand-500);
}

.status-success .tool-icon {
  color: var(--color-success-600);
}

.status-error .tool-icon {
  color: var(--color-danger-600);
}

.rotating {
  animation: rotate 1.2s linear infinite;
}

@keyframes rotate {
  to {
    transform: rotate(360deg);
  }
}

.tool-meta {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.tool-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  font-family: 'JetBrains Mono', Menlo, monospace;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tool-status {
  font-size: 11px;
  color: var(--text-secondary);
}

.tool-duration {
  font-size: 11px;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

.expand-icon {
  font-size: 12px;
  color: var(--text-placeholder);
  transition: transform 0.2s;
}

.expand-icon.expanded {
  transform: rotate(180deg);
}

.tool-action {
  padding: 0 10px 8px;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border: 1px solid var(--brand-200);
  border-radius: 6px;
  background: var(--brand-50);
  color: var(--brand-600);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition:
    background 0.2s,
    border-color 0.2s;
}

.action-btn:hover {
  background: color-mix(in srgb, var(--brand-500) 14%, transparent);
  border-color: var(--brand-500);
}

.tool-body {
  border-top: 1px solid var(--border-light);
  padding: 10px;
  background: var(--gray-50);
}

.tool-section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tool-section + .tool-section {
  margin-top: 10px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--text-secondary);
  font-weight: 600;
}

.section-title.error-title {
  color: var(--color-danger-600);
}

.json-block {
  margin: 0;
  padding: 8px 10px;
  background: #1e1e2e;
  color: #d4d4d8;
  border-radius: 4px;
  font-family: 'JetBrains Mono', Menlo, monospace;
  font-size: 11.5px;
  line-height: 1.5;
  max-height: 260px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.json-block.error-block {
  background: var(--color-danger-50);
  color: var(--color-danger-600);
  border: 1px solid var(--color-danger-200);
}
</style>
