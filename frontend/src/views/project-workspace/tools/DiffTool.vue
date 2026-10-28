<template>
  <div class="diff-tool-page">
    <!-- 页头 -->
    <AppPageHeader
      icon="i-solar-document-text-bold"
      :illustration="illustTools"
      title="文本 Diff"
      description="对比两段文本的差异，高亮显示增减内容"
      :breadcrumbs="['工具箱', '文本 Diff']"
    />

    <!-- 输入双栏 -->
    <div class="diff-layout">
      <AppSectionCard class="input-panel" content-class="panel-body">
        <template #header>
          <div class="panel-hd">
            <div class="panel-hd-left">
              <i class="i-solar-document-text-bold hd-icon" style="color: var(--text-secondary)" />
              <span class="hd-title">原始文本</span>
              <span v-if="leftText" class="hd-meta">{{ leftText.length }} 字符</span>
            </div>
            <el-button size="small" link @click="leftText = ''">
              <i class="i-solar-trash-bin-trash-linear btn-icon-sm" />
              清空
            </el-button>
          </div>
        </template>
        <el-input
          v-model="leftText"
          type="textarea"
          :rows="10"
          placeholder="粘贴原始文本..."
          resize="none"
          class="diff-textarea"
        />
      </AppSectionCard>

      <AppSectionCard class="input-panel" content-class="panel-body">
        <template #header>
          <div class="panel-hd">
            <div class="panel-hd-left">
              <i class="i-solar-document-text-bold hd-icon" style="color: var(--brand-500)" />
              <span class="hd-title">新文本</span>
              <span v-if="rightText" class="hd-meta">{{ rightText.length }} 字符</span>
            </div>
            <el-button size="small" link @click="rightText = ''">
              <i class="i-solar-trash-bin-trash-linear btn-icon-sm" />
              清空
            </el-button>
          </div>
        </template>
        <el-input
          v-model="rightText"
          type="textarea"
          :rows="10"
          placeholder="粘贴新文本..."
          resize="none"
          class="diff-textarea"
        />
      </AppSectionCard>
    </div>

    <!-- 操作行 -->
    <div class="action-row">
      <el-button type="primary" size="large" @click="computeDiff">
        <i class="i-solar-git-diff-bold btn-icon" />
        对比差异
      </el-button>
      <div v-if="diffResult" class="diff-stats">
        <span class="stat-pill stat-added">
          <i class="i-solar-add-circle-bold" />
          {{ stats.added }} 行
        </span>
        <span class="stat-pill stat-removed">
          <i class="i-solar-minus-circle-bold" />
          {{ stats.removed }} 行
        </span>
        <span class="stat-pill stat-unchanged">
          <i class="i-solar-equalizer-bold" />
          {{ stats.unchanged }} 行
        </span>
      </div>
      <div style="flex:1" />
      <el-button v-if="diffResult" @click="diffResult = ''">
        <i class="i-solar-close-circle-linear btn-icon" />
        清除结果
      </el-button>
    </div>

    <!-- 差异结果 -->
    <AppSectionCard v-if="diffResult" class="result-panel" content-class="panel-body">
      <template #header>
        <div class="panel-hd">
          <div class="panel-hd-left">
            <i class="i-solar-git-diff-bold hd-icon" />
            <span class="hd-title">差异结果</span>
          </div>
          <el-button size="small" type="primary" plain @click="copyDiff">
            <i class="i-solar-copy-bold btn-icon-sm" />
            复制差异
          </el-button>
        </div>
      </template>
      <div class="diff-output" v-html="diffResult" />
    </AppSectionCard>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { AppPageHeader, AppSectionCard } from '@/components/common'
import illustTools from '@/assets/illustrations/tools.svg'

const leftText = ref('')
const rightText = ref('')
const diffResult = ref('')

const stats = computed(() => {
  if (!diffResult.value) return { added: 0, removed: 0, unchanged: 0 }
  const h = diffResult.value
  const added = (h.match(/class="diff-added/g) || []).length
  const removed = (h.match(/class="diff-removed/g) || []).length
  const unchanged = (h.match(/class="diff-unchanged/g) || []).length
  return { added, removed, unchanged }
})

function computeDiff() {
  if (!leftText.value && !rightText.value) { diffResult.value = ''; return }
  const l = leftText.value.split('\n')
  const r = rightText.value.split('\n')
  const dp = buildLCS(l, r)
  diffResult.value = renderDiff(l, r, dp)
}

function buildLCS(a: string[], b: string[]): number[][] {
  const m = a.length, n = b.length
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0) as number[])
  for (let i = 1; i <= m; i++)
    for (let j = 1; j <= n; j++)
      dp[i][j] = a[i - 1] === b[j - 1] ? dp[i - 1][j - 1] + 1 : Math.max(dp[i - 1][j], dp[i][j - 1])
  return dp
}

function renderDiff(l: string[], r: string[], dp: number[][]): string {
  const ops: { op: string; text: string }[] = []
  let i = l.length, j = r.length
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && l[i - 1] === r[j - 1]) { ops.unshift({ op: '=', text: l[i - 1] }); i--; j-- }
    else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) { ops.unshift({ op: '+', text: r[j - 1] }); j-- }
    else { ops.unshift({ op: '-', text: l[i - 1] }); i-- }
  }
  let html = ''
  let num = 0
  for (const op of ops) {
    num++
    const cls = op.op === '+' ? 'diff-added' : op.op === '-' ? 'diff-removed' : 'diff-unchanged'
    const pf = op.op === '+' ? '+' : op.op === '-' ? '-' : ' '
    html += `<div class="${cls}"><span class="ln">${num}</span><span class="pf">${pf}</span><span class="tx">${esc(op.text)}</span></div>`
  }
  return html
}

function esc(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/ /g, '&nbsp;').replace(/\t/g, '&nbsp;&nbsp;&nbsp;&nbsp;')
}

function copyDiff() {
  if (!diffResult.value) return
  const text = diffResult.value.replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&')
  navigator.clipboard.writeText(text).then(() => ElMessage.success('已复制'))
}
</script>

<style scoped lang="scss">
.diff-tool-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  height: 100%;
}

.btn-icon {
  margin-right: 6px;
  font-size: 16px;
  vertical-align: -3px;
}
.btn-icon-sm {
  margin-right: 4px;
  font-size: 14px;
  vertical-align: -2px;
}

/* ============ 输入双栏 ============ */
.diff-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
  min-height: 0;
}

.input-panel {
  display: flex;
  flex-direction: column;
  min-height: 280px;
}
.panel-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 0;
  min-height: 0;
}

.panel-hd {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}
.panel-hd-left {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.hd-icon {
  font-size: 16px;
  color: var(--brand-500);
}
.hd-title {
  font-size: 14px;
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}
.hd-meta {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: var(--font-weight-regular);
}

.diff-textarea {
  flex: 1;
  display: flex;
}
.diff-textarea :deep(.el-textarea__inner) {
  border: none;
  border-radius: 0;
  font-family: 'SF Mono', Menlo, Consolas, 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  height: 100% !important;
  padding: var(--space-3) var(--space-4);
}

/* ============ 操作行 ============ */
.action-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) 0;
}

.diff-stats {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.stat-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 26px;
  padding: 0 12px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: var(--font-weight-semibold);

  &.stat-added      { background: var(--color-success-50); color: var(--color-success-700); }
  &.stat-removed    { background: var(--color-danger-50);  color: var(--color-danger-600); }
  &.stat-unchanged  { background: var(--gray-100);         color: var(--text-secondary); }
}

/* ============ 结果面板 ============ */
.result-panel {
  flex: 1;
  min-height: 200px;
  display: flex;
  flex-direction: column;
}

.diff-output {
  flex: 1;
  overflow: auto;
  font-family: 'SF Mono', Menlo, Consolas, 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  padding: var(--space-2) 0;
  background: var(--bg-card);

  :deep(.diff-unchanged) {
    color: var(--text-regular);
  }
  :deep(.diff-added) {
    background: var(--color-success-50);
    color: var(--color-success-700);
  }
  :deep(.diff-removed) {
    background: var(--color-danger-50);
    color: var(--color-danger-600);
  }
  :deep(.diff-added),
  :deep(.diff-removed),
  :deep(.diff-unchanged) {
    display: flex;
    padding: 1px var(--space-4);

    .ln {
      width: 45px;
      text-align: right;
      padding-right: 10px;
      color: var(--text-placeholder);
      flex-shrink: 0;
      user-select: none;
    }
    .pf {
      width: 16px;
      flex-shrink: 0;
      font-weight: 700;
    }
    .tx {
      flex: 1;
      word-break: break-all;
      white-space: pre-wrap;
    }
  }
}
</style>
