<template>
  <div class="ts-page">
    <!-- 页头 -->
    <AppPageHeader
      icon="i-solar-clock-circle-bold"
      :illustration="illustTools"
      title="时间戳转换"
      description="时间戳 ↔ 日期时间互转，实时显示当前时间"
      :breadcrumbs="['工具箱', '时间戳转换']"
    />

    <!-- 当前时间 -->
    <div class="now-grid">
      <div class="now-card now-brand">
        <div class="now-icon">
          <i class="i-solar-clock-circle-bold" />
        </div>
        <div class="now-info">
          <div class="now-label">当前时间戳（秒）</div>
          <div class="now-value">{{ currentTs }}</div>
          <div class="now-human">{{ currentHuman }}</div>
        </div>
        <el-button text class="copy-btn" @click="copy(String(currentTs))">
          <i class="i-solar-copy-bold" />
          复制
        </el-button>
      </div>

      <div class="now-card now-info">
        <div class="now-icon">
          <i class="i-solar-stopwatch-bold" />
        </div>
        <div class="now-info">
          <div class="now-label">当前时间戳（毫秒）</div>
          <div class="now-value">{{ currentTsMs }}</div>
          <div class="now-human">{{ currentHuman }}</div>
        </div>
        <el-button text class="copy-btn" @click="copy(String(currentTsMs))">
          <i class="i-solar-copy-bold" />
          复制
        </el-button>
      </div>
    </div>

    <!-- 转换 -->
    <div class="conv-grid">
      <AppSectionCard class="conv-card" content-class="conv-body">
        <template #header>
          <div class="conv-title">
            <div class="conv-arrow arrow-down">
              <i class="i-solar-alt-arrow-down-bold" />
            </div>
            <span class="conv-text">时间戳 → 日期时间</span>
          </div>
        </template>
        <div class="conv-row">
          <el-input
            v-model="tsInput"
            placeholder="输入时间戳（秒或毫秒）"
            clearable
            @keyup.enter="ts2date"
            class="conv-input"
          >
            <template #prefix>
              <i class="i-solar-clock-circle-linear prefix-icon" />
            </template>
          </el-input>
          <el-button type="primary" @click="ts2date">
            <i class="i-solar-refresh-circle-bold btn-icon-sm" />
            转换
          </el-button>
        </div>
        <div class="conv-row" v-if="dateOutput">
          <el-input v-model="dateOutput" readonly placeholder="转换结果" class="conv-input">
            <template #prefix>
              <i class="i-solar-calendar-mark-linear prefix-icon" />
            </template>
          </el-input>
          <el-button @click="copy(dateOutput)">
            <i class="i-solar-copy-bold btn-icon-sm" />
            复制
          </el-button>
        </div>
      </AppSectionCard>

      <AppSectionCard class="conv-card" content-class="conv-body">
        <template #header>
          <div class="conv-title">
            <div class="conv-arrow arrow-up">
              <i class="i-solar-alt-arrow-up-bold" />
            </div>
            <span class="conv-text">日期时间 → 时间戳</span>
          </div>
        </template>
        <div class="conv-row">
          <el-date-picker
            v-model="dateInput"
            type="datetime"
            placeholder="选择日期时间"
            class="conv-input"
          />
          <el-button type="primary" @click="date2ts">
            <i class="i-solar-refresh-circle-bold btn-icon-sm" />
            转换
          </el-button>
        </div>
        <div class="conv-row" v-if="tsOutput">
          <el-input v-model="tsOutput" readonly placeholder="结果（秒）" class="conv-input">
            <template #prefix>
              <i class="i-solar-hashtag-square-linear prefix-icon" />
            </template>
          </el-input>
          <el-button @click="copy(tsOutput)">
            <i class="i-solar-copy-bold btn-icon-sm" />
            复制
          </el-button>
        </div>
      </AppSectionCard>
    </div>

    <!-- 快捷时间 -->
    <AppSectionCard title="快捷时间" class="quick-card">
      <div class="quick-grid">
        <div
          v-for="q in quickList"
          :key="q.label"
          class="quick-item"
          @click="applyQuick(q.ts)"
        >
          <div class="q-icon">
            <i class="i-solar-clock-circle-bold" />
          </div>
          <div class="q-info">
            <div class="q-label">{{ q.label }}</div>
            <div class="q-ts">{{ q.ts }}</div>
          </div>
        </div>
      </div>
    </AppSectionCard>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { AppPageHeader, AppSectionCard } from '@/components/common'
import illustTools from '@/assets/illustrations/tools.svg'

const currentTs = ref(0)
const currentTsMs = ref(0)
const currentHuman = ref('')
let timer: number | null = null

const tsInput = ref('')
const dateOutput = ref('')
const dateInput = ref<Date | null>(null)
const tsOutput = ref('')

function tick() {
  const now = Date.now()
  currentTs.value = Math.floor(now / 1000)
  currentTsMs.value = now
  currentHuman.value = new Date(now).toLocaleString('zh-CN')
}

function copy(t: string) { navigator.clipboard.writeText(t).then(() => ElMessage.success('已复制')) }

function ts2date() {
  const v = Number(tsInput.value)
  if (!v) return
  const ms = v > 1e12 ? v : v * 1000
  dateOutput.value = new Date(ms).toLocaleString('zh-CN')
}

function date2ts() {
  if (!dateInput.value) return
  tsOutput.value = String(Math.floor(dateInput.value.getTime() / 1000))
}

function applyQuick(ts: number) {
  tsInput.value = String(ts)
  ts2date()
}

const quickList = [
  { label: '今天 00:00', ts: Math.floor(new Date(new Date().setHours(0,0,0,0)).getTime() / 1000) },
  { label: '明天 00:00', ts: Math.floor(new Date(new Date().setHours(0,0,0,0)).getTime() / 1000) + 86400 },
  { label: '本周一', ts: (() => { const d = new Date(); d.setDate(d.getDate() - ((d.getDay() + 6) % 7)); d.setHours(0,0,0,0); return Math.floor(d.getTime() / 1000) })() },
  { label: '本月1日', ts: (() => { const d = new Date(); d.setDate(1); d.setHours(0,0,0,0); return Math.floor(d.getTime() / 1000) })() },
  { label: '今年1月1日', ts: (() => { const d = new Date(); d.setMonth(0, 1); d.setHours(0,0,0,0); return Math.floor(d.getTime() / 1000) })() },
  { label: '1小时后', ts: Math.floor(Date.now() / 1000) + 3600 },
  { label: '24小时后', ts: Math.floor(Date.now() / 1000) + 86400 },
  { label: '7天后', ts: Math.floor(Date.now() / 1000) + 604800 },
]

onMounted(() => { tick(); timer = window.setInterval(tick, 1000) })
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<style scoped lang="scss">
.ts-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.btn-icon-sm {
  margin-right: 4px;
  font-size: 14px;
  vertical-align: -2px;
}

/* ============ 当前时间卡片 ============ */
.now-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
}
.now-card {
  position: relative;
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-5) var(--space-6);
  border-radius: var(--radius-lg);
  color: #fff;
  overflow: hidden;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);

  &.now-brand {
    background: linear-gradient(135deg, var(--brand-500) 0%, var(--brand-600) 100%);
  }
  &.now-info {
    background: linear-gradient(135deg, var(--color-info-500, #3B82F6) 0%, var(--color-info-600, #2563EB) 100%);
  }
}
.now-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.18);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  color: #fff;
  flex-shrink: 0;
}
.now-info {
  flex: 1;
  min-width: 0;
}
.now-label {
  font-size: 12px;
  opacity: 0.85;
  margin-bottom: 4px;
}
.now-value {
  font-size: 22px;
  font-weight: var(--font-weight-bold);
  font-family: 'SF Mono', Menlo, Consolas, 'Courier New', monospace;
  letter-spacing: 1px;
  margin-bottom: 2px;
}
.now-human {
  font-size: 12px;
  opacity: 0.75;
}
.copy-btn {
  color: rgba(255, 255, 255, 0.9) !important;
  font-size: 13px;
  display: inline-flex;
  align-items: center;
  gap: 4px;

  &:hover {
    color: #fff !important;
    background: rgba(255, 255, 255, 0.15) !important;
  }
  i { font-size: 14px; }
}

/* ============ 转换区 ============ */
.conv-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
}

.conv-card {
  display: flex;
  flex-direction: column;
}
.conv-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding-top: var(--space-3);
}

.conv-title {
  display: flex;
  align-items: center;
  gap: 8px;
}
.conv-arrow {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  flex-shrink: 0;

  &.arrow-down { background: var(--color-success-50); color: var(--color-success-700); }
  &.arrow-up   { background: var(--color-warning-50); color: var(--color-warning-700); }
}
.conv-text {
  font-size: 14px;
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}

.conv-row {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}
.conv-input {
  flex: 1;
}
.prefix-icon {
  font-size: 16px;
  color: var(--text-secondary);
}

/* ============ 快捷时间 ============ */
.quick-card {
  display: flex;
  flex-direction: column;
}
.quick-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: var(--space-2);
}
.quick-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: 10px var(--space-3);
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.18s ease;

  &:hover {
    border-color: var(--brand-300);
    background: var(--color-brand-50);
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(0, 185, 107, 0.08);

    .q-icon { background: var(--brand-500); color: #fff; }
  }
}
.q-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  background: var(--color-brand-50);
  color: var(--brand-500);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  flex-shrink: 0;
  transition: all 0.18s ease;
}
.q-info {
  flex: 1;
  min-width: 0;
}
.q-label {
  font-size: 13px;
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
  margin-bottom: 2px;
}
.q-ts {
  font-size: 11px;
  font-family: 'SF Mono', Menlo, Consolas, 'Courier New', monospace;
  color: var(--text-secondary);
}
</style>
