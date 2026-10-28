<template>
  <div class="json-formatter-page">
    <!-- 页头 -->
    <AppPageHeader
      icon="i-solar-code-bold"
      :illustration="illustTools"
      title="JSON 格式化"
      description="格式化、压缩、校验 JSON 数据"
      :breadcrumbs="['工具箱', 'JSON 格式化']"
    >
      <template #actions>
        <el-select v-model="indentSize" style="width: 120px">
          <el-option :value="2" label="2 空格" />
          <el-option :value="4" label="4 空格" />
          <el-option :value="0" label="Tab" />
        </el-select>
      </template>
    </AppPageHeader>

    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-button type="primary" @click="formatJson">
          <i class="i-solar-cpu-bolt-bold btn-icon-sm" />
          格式化
        </el-button>
        <el-button @click="compressJson">
          <i class="i-solar-compress-bold btn-icon-sm" />
          压缩
        </el-button>
        <el-button @click="sortJson">
          <i class="i-solar-sort-from-top-to-bottom-bold btn-icon-sm" />
          按键排序
        </el-button>
      </div>
      <div class="toolbar-right">
        <el-button :disabled="!formattedResult" @click="copyJson">
          <i class="i-solar-copy-bold btn-icon-sm" />
          复制结果
        </el-button>
        <el-button @click="clearJson">
          <i class="i-solar-trash-bin-trash-linear btn-icon-sm" />
          清空
        </el-button>
      </div>
    </div>

    <!-- 双栏 -->
    <div class="json-panels">
      <!-- 输入 -->
      <AppSectionCard class="json-panel" content-class="json-panel-body">
        <template #header>
          <div class="panel-hd">
            <div class="panel-hd-left">
              <i class="i-solar-import-bold hd-icon" />
              <span class="hd-title">输入</span>
              <span v-if="jsonText" class="hd-meta">{{ jsonText.length }} 字符</span>
            </div>
            <div class="panel-hd-right">
              <span v-if="errorMsg" class="status-pill status-error">
                <i class="i-solar-close-circle-bold" />
                JSON 无效
              </span>
              <span v-else-if="jsonText" class="status-pill status-ok">
                <i class="i-solar-check-circle-bold" />
                JSON 有效
              </span>
            </div>
          </div>
        </template>
        <el-input
          v-model="jsonText"
          type="textarea"
          :rows="20"
          placeholder="在此粘贴 JSON..."
          resize="none"
          class="json-input"
          @input="validateJson"
        />
      </AppSectionCard>

      <!-- 输出 -->
      <AppSectionCard class="json-panel" content-class="json-panel-body">
        <template #header>
          <div class="panel-hd">
            <div class="panel-hd-left">
              <i class="i-solar-export-bold hd-icon" />
              <span class="hd-title">输出</span>
              <span v-if="formattedResult" class="hd-meta">
                {{ formattedResult.length }} 字符 · {{ lineCount }} 行
              </span>
            </div>
          </div>
        </template>
        <pre v-if="formattedResult" class="json-output">{{ formattedResult }}</pre>
        <div v-else class="output-placeholder">
          <i class="i-solar-document-text-linear placeholder-icon" />
          <span>格式化结果将显示在这里</span>
        </div>
      </AppSectionCard>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { AppPageHeader, AppSectionCard } from '@/components/common'
import illustTools from '@/assets/illustrations/tools.svg'

const jsonText = ref('')
const errorMsg = ref('')
const indentSize = ref(2)
const formattedResult = ref('')

const lineCount = computed(() => formattedResult.value.split('\n').length)

function getIndent() {
  return indentSize.value === 0 ? '\t' : ' '.repeat(indentSize.value)
}

function validateJson() {
  if (!jsonText.value.trim()) {
    errorMsg.value = ''
    return
  }
  try {
    JSON.parse(jsonText.value)
    errorMsg.value = ''
  } catch (e: any) {
    errorMsg.value = e.message
  }
}

function formatJson() {
  try {
    const obj = JSON.parse(jsonText.value || 'null')
    formattedResult.value = JSON.stringify(obj, null, getIndent())
    errorMsg.value = ''
  } catch (e: any) {
    errorMsg.value = e.message
    ElMessage.error('JSON 格式错误')
  }
}

function compressJson() {
  try {
    const obj = JSON.parse(jsonText.value || 'null')
    formattedResult.value = JSON.stringify(obj)
    errorMsg.value = ''
  } catch (e: any) {
    errorMsg.value = e.message
    ElMessage.error('JSON 格式错误')
  }
}

function sortJson() {
  try {
    const obj = JSON.parse(jsonText.value || 'null')
    formattedResult.value = JSON.stringify(sortObject(obj), null, getIndent())
    errorMsg.value = ''
  } catch (e: any) {
    errorMsg.value = e.message
    ElMessage.error('JSON 格式错误')
  }
}

function sortObject(obj: any): any {
  if (Array.isArray(obj)) return obj.map(sortObject)
  if (obj !== null && typeof obj === 'object') {
    return Object.keys(obj).sort().reduce((acc, key) => { acc[key] = sortObject(obj[key]); return acc }, {} as any)
  }
  return obj
}

function clearJson() {
  jsonText.value = ''
  formattedResult.value = ''
  errorMsg.value = ''
}

function copyJson() {
  if (!formattedResult.value) { ElMessage.warning('没有可复制的内容'); return }
  navigator.clipboard.writeText(formattedResult.value).then(() => ElMessage.success('已复制到剪贴板'))
}
</script>

<style scoped lang="scss">
.json-formatter-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  height: 100%;
}

.btn-icon-sm {
  margin-right: 4px;
  font-size: 14px;
  vertical-align: -2px;
}

/* ============ 工具栏 ============ */
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
}
.toolbar-left, .toolbar-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

/* ============ 双栏 ============ */
.json-panels {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
  min-height: 0;
}

.json-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}
.json-panel-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 0;
  min-height: 0;
}

/* ============ 面板头 ============ */
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
.panel-hd-right {
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

/* ============ 状态药丸 ============ */
.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 22px;
  padding: 0 10px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: var(--font-weight-semibold);

  &.status-ok    { background: var(--color-success-50); color: var(--color-success-700); }
  &.status-error { background: var(--color-danger-50);  color: var(--color-danger-600); }
}

/* ============ 输入框 ============ */
.json-input {
  flex: 1;
  display: flex;
}
.json-input :deep(.el-textarea__inner) {
  border: none;
  border-radius: 0;
  font-family: 'SF Mono', Menlo, Consolas, 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  height: 100% !important;
  padding: var(--space-3) var(--space-4);
}

/* ============ 输出框 ============ */
.json-output {
  margin: 0;
  padding: var(--space-3) var(--space-4);
  font-family: 'SF Mono', Menlo, Consolas, 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-all;
  overflow: auto;
  flex: 1;
  background: var(--bg-card);
}

.output-placeholder {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  color: var(--text-placeholder);
  font-size: 13px;
  padding: var(--space-6);
}
.placeholder-icon {
  font-size: 36px;
  color: var(--gray-300);
}
</style>
