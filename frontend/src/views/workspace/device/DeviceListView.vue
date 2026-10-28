<script setup lang="ts">
/**
 * 设备管理 —— App 自动化设备/执行机列表
 *
 * 设备域为全局资源（非项目内），入口挂在项目工作空间 App 自动化下
 * （/project-workspace/:id/app/devices），页面展示全部设备。
 * 列出所有执行机（Agent）与其下设备，展示在线态（现算）、机型、当前占用者，
 * 「控制」按钮以弹框（DeviceControlDialog）形式投屏 + 操作，不再跳独立页。
 *
 * 契约：GET /app/agents、GET /app/devices（《APP自动化-P1接口契约.md》§6）。
 */
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import {
  appDeviceApi,
  type AppAgent,
  type AppDevice,
  type AgentOnlineState,
} from '@/api/appDevice'
import AppPageHeader from '@/components/common/AppPageHeader.vue'
import AppStatCard from '@/components/common/AppStatCard.vue'
import AppEmpty from '@/components/common/AppEmpty.vue'
import AppSectionCard from '@/components/common/AppSectionCard.vue'
import PhoneThumb from './PhoneThumb.vue'
import DeviceControlDialog from './DeviceControlDialog.vue'

const userStore = useUserStore()

const loading = ref(false)
const agents = ref<AppAgent[]>([])
const devices = ref<AppDevice[]>([])
const keyword = ref('')
/** 设备类型筛选：all / real（真机）/ emulator（模拟器） */
const typeFilter = ref<'all' | 'real' | 'emulator'>('all')
/** 连接状态筛选：all / online / offline */
const statusFilter = ref<'all' | 'online' | 'offline'>('all')
const viewMode = ref<'card' | 'table'>('card')
/** 分页（客户端，对已加载列表分页） */
const page = ref(1)
const pageSize = ref(12)

let timer: ReturnType<typeof setInterval> | null = null

/** 设备截图 objectURL 缓存：udid → url */
const shots = ref<Record<string, string>>({})
/** 上次拉取时刻：udid → ms（限频，截图 5min 才变，无需跟 10s 轮询同频） */
const shotLoadedAt: Record<string, number> = {}
const SHOT_REFRESH_MS = 60_000

const canControl = computed(() => userStore.hasPermission('app_device:control'))

// 投屏控制弹框
const controlVisible = ref(false)
const controlUdid = ref('')
const controlName = ref('')
const controlPlatform = ref<'android' | 'harmony' | 'ios'>('android')

// ==================== 数据加载 ====================

async function fetchAll(showLoading = true) {
  if (showLoading) loading.value = true
  try {
    const [agentRes, deviceRes] = await Promise.all([
      appDeviceApi.listAgents(),
      appDeviceApi.listDevices(),
    ])
    agents.value = agentRes ?? []
    devices.value = deviceRes ?? []
    void loadShots()
  } catch {
    // 拦截器已弹提示
  } finally {
    if (showLoading) loading.value = false
  }
}

/** 为在线设备拉截图（限频 + 拔线/离线释放旧 objectURL） */
async function loadShots() {
  const now = Date.now()
  const liveUdids = new Set(devices.value.filter((d) => d.online).map((d) => d.udid))
  // 释放离线/移除设备的旧图
  for (const udid of Object.keys(shots.value)) {
    if (!liveUdids.has(udid)) {
      URL.revokeObjectURL(shots.value[udid])
      delete shots.value[udid]
      delete shotLoadedAt[udid]
    }
  }
  for (const udid of liveUdids) {
    if (shots.value[udid] && now - (shotLoadedAt[udid] ?? 0) < SHOT_REFRESH_MS) continue
    shotLoadedAt[udid] = now
    const url = await appDeviceApi.fetchScreenshot(udid)
    if (url) {
      const old = shots.value[udid]
      shots.value[udid] = url
      if (old) URL.revokeObjectURL(old)
    }
  }
}

onMounted(() => {
  fetchAll()
  // 轮询刷新在线态/占用（10s，与心跳节奏对齐）
  timer = setInterval(() => fetchAll(false), 10_000)
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
  // 释放全部截图 objectURL，防内存泄漏
  for (const url of Object.values(shots.value)) URL.revokeObjectURL(url)
})

// ==================== 派生数据 ====================

const agentNameMap = computed(() => {
  const m = new Map<number, string>()
  agents.value.forEach((a) => m.set(a.id, a.name))
  return m
})

const filteredDevices = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return devices.value.filter((d) => {
    if (statusFilter.value === 'online' && !d.online) return false
    if (statusFilter.value === 'offline' && d.online) return false
    if (typeFilter.value === 'emulator' && !isEmulator(d)) return false
    if (typeFilter.value === 'real' && isEmulator(d)) return false
    if (!kw) return true
    const hay = [
      d.model,
      d.brand,
      d.serial,
      d.udid,
      d.agent_name ?? agentNameMap.value.get(d.agent_id),
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
    return hay.includes(kw)
  })
})

/** 当前页设备（客户端分页） */
const pagedDevices = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredDevices.value.slice(start, start + pageSize.value)
})

// 筛选/搜索变化时回到第 1 页
watch([keyword, typeFilter, statusFilter], () => {
  page.value = 1
})

/** 顶部统计（全部/在线/离线/真机/模拟器 + 分平台安卓/iOS/鸿蒙） */
const stats = computed(() => {
  const all = devices.value
  const total = all.length
  const online = all.filter((d) => d.online).length
  const real = all.filter((d) => !isEmulator(d)).length
  return {
    total,
    online,
    offline: total - online,
    real,
    emulator: total - real,
    // 平台归属：安卓含未标 platform 的历史设备（adb 通道默认 android）
    android: all.filter((d) => d.platform !== 'harmony' && d.platform !== 'ios').length,
    ios: all.filter((d) => d.platform === 'ios').length,
    harmony: all.filter((d) => d.platform === 'harmony').length,
  }
})

// ==================== 展示辅助 ====================

const agentStateMeta: Record<AgentOnlineState, { label: string; type: string }> = {
  online: { label: '在线', type: 'success' },
  stale: { label: '延迟', type: 'warning' },
  offline: { label: '离线', type: 'info' },
}

function agentOf(d: AppDevice) {
  return d.agent_name ?? agentNameMap.value.get(d.agent_id) ?? `#${d.agent_id}`
}

function deviceTitle(d: AppDevice) {
  return d.model || d.serial || d.udid
}

function lockLabel(d: AppDevice): string {
  if (!d.lock) return ''
  return d.lock.owner_name || `用户 #${d.lock.owner_user_id}`
}

/** 是否是当前登录用户占用（同用户可直接进去接管标签页） */
function lockedBySelf(d: AppDevice): boolean {
  return !!d.lock && d.lock.owner_user_id === userStore.userId
}

// ==================== 操作 ====================

function goControl(d: AppDevice) {
  if (!d.online) {
    ElMessage.warning('设备当前不在线')
    return
  }
  controlUdid.value = d.udid
  controlName.value = deviceTitle(d)
  controlPlatform.value = isHarmony(d) ? 'harmony' : isIos(d) ? 'ios' : 'android'
  controlVisible.value = true
}

function handleRefresh() {
  fetchAll()
}

/** 模拟器判定：serial=emulator-* 或机型含 sdk_gphone/emulator */
function isEmulator(d: AppDevice): boolean {
  const s = (d.serial || '').toLowerCase()
  const m = (d.model || '').toLowerCase()
  return s.startsWith('emulator-') || m.includes('sdk_gphone') || m.includes('emulator')
}

/** 鸿蒙 NEXT 设备（hdc 通道） */
function isHarmony(d: AppDevice): boolean {
  return d.platform === 'harmony'
}

/** iOS 设备（libimobiledevice 通道；投屏走 WDA MJPEG，I3 已接） */
function isIos(d: AppDevice): boolean {
  return d.platform === 'ios'
}

/** 平板（宽屏设备）：缩略图/投屏容器用宽外形。model 含 pad/tablet 命中；
 *  iOS 目前仅接 iPad，model 缺失时按 iOS 兜底（后续接 iPhone 需按 model 细分）。 */
function isTablet(d: AppDevice): boolean {
  const m = (d.model || '').toLowerCase()
  if (/pad|tablet/.test(m)) return true
  return isIos(d) && !/iphone|ipod/.test(m)
}

/** 系统标签：HarmonyOS 6.1.0 / iOS 18.7.9 / Android 15（android_version 字段承载多平台版本号） */
function osLabel(d: AppDevice): string {
  const os = isHarmony(d) ? 'HarmonyOS' : isIos(d) ? 'iOS' : 'Android'
  return `${os} ${d.android_version || '?'}`
}

/** 类型标签：鸿蒙真机 / iOS真机 / 真机 / 模拟器 */
function typeLabel(d: AppDevice): string {
  const base = isEmulator(d) ? '模拟器' : '真机'
  return isHarmony(d) ? `鸿蒙${base}` : isIos(d) ? `iOS${base}` : base
}

/** 导出当前筛选结果为 CSV */
function exportCsv() {
  const rows = filteredDevices.value
  if (!rows.length) {
    ElMessage.warning('没有可导出的设备')
    return
  }
  const head = ['机型', '类型', '执行机', '序列号', 'UDID', '分辨率', '系统版本', '连接', '在线', '占用者']
  const esc = (v: string) => `"${String(v ?? '').replace(/"/g, '""')}"`
  const lines = rows.map((d) =>
    [
      deviceTitle(d),
      typeLabel(d),
      agentOf(d),
      d.serial,
      d.udid,
      d.resolution || '',
      d.android_version ? osLabel(d) : '',
      d.connection,
      d.online ? '在线' : '离线',
      d.lock ? lockLabel(d) : '',
    ]
      .map(esc)
      .join(','),
  )
  const csv = '﻿' + [head.map(esc).join(','), ...lines].join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `设备列表_${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(a.href)
  ElMessage.success(`已导出 ${rows.length} 台设备`)
}
</script>

<template>
  <div class="device-list-view">
    <AppPageHeader
      title="设备管理"
      description="管理 App 自动化执行机与真机/模拟器设备，投屏实时控制"
      icon="i-solar-smartphone-2-bold-duotone"
    />

    <!-- 工具栏：搜索 + 类型/状态筛选 + 视图切换 -->
    <div class="toolbar">
      <el-input
        v-model="keyword"
        placeholder="搜索机型 / 序列号 / 执行机"
        clearable
        class="tb-search"
      >
        <template #prefix>
          <i class="i-solar-magnifer-linear" />
        </template>
      </el-input>
      <el-select v-model="typeFilter" class="tb-select" placeholder="设备类型">
        <el-option label="全部类型" value="all" />
        <el-option label="真机" value="real" />
        <el-option label="模拟器" value="emulator" />
      </el-select>
      <el-select v-model="statusFilter" class="tb-select" placeholder="连接状态">
        <el-option label="全部状态" value="all" />
        <el-option label="在线" value="online" />
        <el-option label="离线" value="offline" />
      </el-select>
      <div class="tb-spacer" />
      <el-radio-group v-model="viewMode" size="default">
        <el-radio-button label="card">
          <i class="i-solar-widget-5-bold" />
        </el-radio-button>
        <el-radio-button label="table">
          <i class="i-solar-list-bold" />
        </el-radio-button>
      </el-radio-group>
    </div>

    <!-- 统计卡片 -->
    <div class="stat-row">
      <AppStatCard label="全部设备" :value="stats.total" value-suffix=" 台" color="brand" icon-name="i-solar-smartphone-2-bold" />
      <AppStatCard label="在线设备" :value="stats.online" value-suffix=" 台" color="success" icon-name="i-solar-plug-circle-bold" />
      <AppStatCard label="离线设备" :value="stats.offline" value-suffix=" 台" color="warning" icon-name="i-solar-plug-circle-broken" />
      <AppStatCard label="真机设备" :value="stats.real" value-suffix=" 台" color="info" icon-name="i-solar-smartphone-bold" />
      <AppStatCard label="模拟器设备" :value="stats.emulator" value-suffix=" 台" color="brand" icon-name="i-solar-monitor-smartphone-bold" />
      <AppStatCard label="安卓设备" :value="stats.android" value-suffix=" 台" color="success" icon-name="i-solar-smartphone-2-bold" />
      <AppStatCard label="iOS 设备" :value="stats.ios" value-suffix=" 台" color="info" icon-name="i-solar-smartphone-bold" />
      <AppStatCard label="鸿蒙设备" :value="stats.harmony" value-suffix=" 台" color="warning" icon-name="i-solar-smartphone-2-bold" />
    </div>

    <!-- 列表分区头 -->
    <div class="list-head">
      <div class="lh-title">设备列表 <span class="lh-count">({{ filteredDevices.length }})</span></div>
      <div class="lh-actions">
        <el-button size="small" @click="handleRefresh">
          <i class="i-solar-refresh-bold btn-icon" />
          刷新
        </el-button>
        <el-button size="small" @click="exportCsv">
          <i class="i-solar-download-minimalistic-bold btn-icon" />
          导出设备
        </el-button>
      </div>
    </div>

    <!-- 空态 -->
    <AppEmpty
      v-if="!loading && filteredDevices.length === 0"
      scene="data"
      title="暂无设备"
      description="请先在宿主机部署 Agent（执行机）并连接 adb 设备"
    />

    <!-- 卡片视图：横向布局（手机在左，信息在右，底部三键操作栏） -->
    <div v-else-if="viewMode === 'card'" v-loading="loading" class="device-grid">
      <div
        v-for="d in pagedDevices"
        :key="d.udid"
        class="device-card"
        :class="{ 'is-offline': !d.online, 'is-tablet': isTablet(d) }"
      >
        <!-- 状态徽标：卡片右上角，独立于标题 -->
        <span class="card-status" :class="d.online ? 'is-on' : 'is-off'">
          <span class="status-dot" />
          {{ d.online ? '在线' : '离线' }}
        </span>

        <!-- 卡身：手机缩略图 + 右侧信息 -->
        <div class="ci-body">
          <!-- 缩略图统一高度 ≈270px:手机 128×(194/92)、平板 202×(200/150) 等高,平板更宽 -->
          <PhoneThumb
            :width="isTablet(d) ? 202 : 128"
            :shot="shots[d.udid] || null"
            :tablet="isTablet(d)"
          />

          <div class="ci-main">
            <!-- 标题：机型名（状态已移到卡片右上角） -->
            <div class="ci-head">
              <span class="ci-title" :title="deviceTitle(d)">{{ deviceTitle(d) }}</span>
            </div>

            <!-- 设备规格组：类型 / 系统 / 分辨率（单行对齐） -->
            <div class="ci-kv">
              <div class="kv-row">
                <span class="kv-k">类型</span>
                <span class="kv-v kv-type" :class="isEmulator(d) ? 'is-emu' : 'is-real'">
                  {{ typeLabel(d) }}
                </span>
              </div>
              <div class="kv-row">
                <span class="kv-k">系统</span>
                <span class="kv-v">{{ osLabel(d) }}</span>
              </div>
              <div class="kv-row">
                <span class="kv-k">分辨率</span>
                <span class="kv-v mono">{{ d.resolution || '—' }}</span>
              </div>
            </div>

            <!-- 接入信息组：执行机 / 序列号 / 连接（分割线隔开） -->
            <div class="ci-kv ci-kv--divided">
              <div class="kv-row">
                <span class="kv-k">执行机</span>
                <span class="kv-v" :title="agentOf(d)">{{ agentOf(d) }}</span>
              </div>
              <div class="kv-row">
                <span class="kv-k">序列号</span>
                <span class="kv-v mono" :title="d.serial">{{ d.serial }}</span>
              </div>
              <div class="kv-row">
                <span class="kv-k">连接</span>
                <span class="kv-v mono">{{ d.connection }}</span>
              </div>
            </div>

            <!-- 占用提示 -->
            <div v-if="d.lock" class="ci-lock" :class="{ 'is-self': lockedBySelf(d) }">
              <i class="i-solar-lock-keyhole-bold" />
              <span>{{ lockedBySelf(d) ? '你正在占用' : `${lockLabel(d)} 占用中` }}</span>
            </div>

            <!-- 控制按钮：右下角（左侧整列留给手机缩略图） -->
            <div class="ci-control">
              <button
                class="control-btn"
                :disabled="!canControl || !d.online || (!!d.lock && !lockedBySelf(d))"
                @click="goControl(d)"
              >
                <i class="i-solar-play-circle-bold" />
                <span>{{ lockedBySelf(d) ? '继续' : '控制' }}</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 表格视图 -->
    <AppSectionCard v-else>
      <el-table v-loading="loading" :data="pagedDevices" class="device-table">
        <el-table-column label="设备" min-width="200">
          <template #default="{ row }">
            <div class="cell-device">
              <i class="i-solar-smartphone-2-bold cell-icon" />
              <div>
                <div class="cell-model">{{ deviceTitle(row) }}</div>
                <div class="cell-sub mono">{{ row.serial }}</div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="执行机" min-width="140">
          <template #default="{ row }">{{ agentOf(row) }}</template>
        </el-table-column>
        <el-table-column label="系统" min-width="120">
          <template #default="{ row }">
            {{ row.brand || '—' }} / {{ osLabel(row) }}
          </template>
        </el-table-column>
        <el-table-column label="分辨率" min-width="110">
          <template #default="{ row }">{{ row.resolution || '—' }}</template>
        </el-table-column>
        <el-table-column label="在线" width="90">
          <template #default="{ row }">
            <el-tag :type="row.online ? 'success' : 'info'" size="small" effect="light">
              {{ row.online ? '在线' : '离线' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="占用" min-width="130">
          <template #default="{ row }">
            <span v-if="!row.lock" class="text-muted">空闲</span>
            <el-tag v-else :type="lockedBySelf(row) ? 'success' : 'warning'" size="small">
              {{ lockedBySelf(row) ? '你' : lockLabel(row) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="canControl"
              type="primary"
              size="small"
              text
              :disabled="!row.online || (!!row.lock && !lockedBySelf(row))"
              @click="goControl(row)"
            >
              {{ lockedBySelf(row) ? '继续' : '控制' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </AppSectionCard>

    <!-- 分页 -->
    <div v-if="filteredDevices.length > pageSize" class="pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="filteredDevices.length"
        :page-sizes="[12, 24, 48, 96]"
        layout="total, sizes, prev, pager, next"
        background
      />
    </div>

    <!-- 投屏控制弹框（替代原独立详情页） -->
    <DeviceControlDialog
      v-model:visible="controlVisible"
      :udid="controlUdid"
      :device-name="controlName"
      :platform="controlPlatform"
      @released="fetchAll(false)"
    />
  </div>
</template>

<style scoped lang="scss">
.device-list-view {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.btn-icon {
  margin-right: 4px;
}

/* 工具栏 */
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;

  .tb-search {
    max-width: 300px;
  }
  .tb-select {
    width: 140px;
  }
  .tb-spacer {
    flex: 1;
  }
}

/* 统计卡（8 张：全部/在线/离线/真机/模拟器 + 安卓/iOS/鸿蒙，
   auto-fit 自适应——宽屏一行铺满，窄屏按最小宽换行） */
.stat-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 14px;
}

/* 列表分区头 */
.list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 2px;

  .lh-title {
    font-size: var(--font-size-lg);
    font-weight: var(--font-weight-semibold);
    color: var(--text-primary);
  }
  .lh-count {
    color: var(--text-secondary);
    font-weight: var(--font-weight-regular);
  }
  .lh-actions {
    display: flex;
    gap: 8px;
  }
}

/* 分页 */
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 4px;
}

.device-grid {
  /* flex-wrap 而非 grid：平板卡要占 1.3 列(442px),grid span 只能整数。
     手机卡固定 340px 紧凑不拉宽,窄容器下 max-width 兜底单列 */
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 16px;
  min-height: 120px;
}

/* ── 卡片：横向布局（名称+状态 / 手机+信息 / 三键底栏） ── */
.device-card {
  position: relative;
  width: 340px;
  max-width: 100%; /* 窄容器兜底:不撑破单列 */
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: 14px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-card);
  transition: box-shadow 0.2s, transform 0.2s, border-color 0.2s;

  &:hover {
    box-shadow: var(--shadow-md);
    transform: translateY(-2px);
    border-color: var(--border-base);
  }

  &.is-offline {
    opacity: 0.72;
    filter: grayscale(0.35);
  }

  /* 平板卡：缩略图与手机等高但更宽（3:4），卡片占 ~1.3 列容纳 */
  &.is-tablet {
    width: 442px;
    /* 窄视口回退：平板缩略图限宽（max-width 可压过内联 width），
       信息列保得住;高度随比例矮些可接受 */
    @media (max-width: 899.98px) {
      :deep(.phone-thumb) {
        max-width: 150px;
      }
    }
  }
}

/* 卡身：手机缩略图 + 右侧信息 */
.ci-body {
  display: flex;
  gap: 12px;
  padding: 0 0 14px;
}

.ci-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* 名称：状态徽标已移到卡片右上角，标题独占一行；预留右侧空间避开徽标 */
.ci-head {
  padding-right: 52px;

  .ci-title {
    display: block;
    min-width: 0;
    font-size: var(--font-size-md, 15px);
    font-weight: var(--font-weight-semibold);
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}

/* 状态徽标：卡片右上角，与标题分离的独立胶囊 */
.card-status {
  position: absolute;
  top: 14px;
  right: 14px;
  z-index: 1;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 9px;
  border-radius: 999px;
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  line-height: 1.35;
  background: var(--bg-page, #f4f6f8);
  border: 1px solid var(--border-light);

  .status-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
  }
  &.is-on {
    color: var(--brand-600);
    .status-dot {
      background: var(--color-success-500, #22c55e);
      box-shadow: 0 0 5px var(--color-success-500, #22c55e);
    }
  }
  &.is-off {
    color: var(--text-secondary);
    .status-dot {
      background: var(--gray-400);
    }
  }
}

/* kv 组：统一单行对齐；--divided 组与上组用细分割线隔开 */
.ci-kv {
  display: flex;
  flex-direction: column;
  gap: 6px;

  &.ci-kv--divided {
    padding-top: 10px;
    border-top: 1px solid var(--border-light);
  }
}

.kv-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: var(--font-size-sm);

  .kv-k {
    flex-shrink: 0;
    width: 48px;
    color: var(--text-secondary);
  }
  .kv-v {
    flex: 1;
    min-width: 0;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  /* 类型值着色：模拟器蓝 / 真机绿，一眼可扫 */
  .kv-type {
    font-weight: var(--font-weight-medium);
    &.is-real {
      color: var(--brand-600);
    }
    &.is-emu {
      color: var(--color-info-600, #2563eb);
    }
  }
}

.mono {
  font-family: var(--font-mono);
}

.ci-lock {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 4px 8px;
  border-radius: 7px;
  font-size: var(--font-size-xs);
  background: var(--warning-50, #fff7ed);
  color: var(--warning-600, #d97706);

  &.is-self {
    background: var(--brand-50);
    color: var(--brand-600);
  }
}

/* 控制按钮：右下角，左侧整列留给手机缩略图 */
.ci-control {
  margin-top: auto;
  padding-top: 10px;
  display: flex;
  justify-content: flex-end;
}

.control-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 7px 18px;
  border: none;
  border-radius: 8px;
  background: var(--brand-500, #16a34a);
  color: #fff;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition: background 0.15s, opacity 0.15s;

  i {
    font-size: 16px;
  }

  &:hover:not(:disabled) {
    background: var(--brand-600, #15803d);
  }
  &:disabled {
    background: var(--gray-200, #e5e7eb);
    color: var(--text-placeholder);
    cursor: not-allowed;
  }
}

.text-muted {
  color: var(--text-placeholder);
}

.cell-device {
  display: flex;
  align-items: center;
  gap: 10px;

  .cell-icon {
    font-size: 20px;
    color: var(--brand-500);
  }
  .cell-model {
    font-weight: var(--font-weight-medium);
    color: var(--text-primary);
  }
  .cell-sub {
    font-size: var(--font-size-xs);
    color: var(--text-secondary);
  }
}
</style>
