<template>
  <div class="report-page" v-loading="loading">
    <AppPageHeader title="测试资产" description="功能用例、App 自动化与需求覆盖情况" icon="i-app-test-case">
      <template #actions><el-radio-group v-model="days" size="small"><el-radio-button :value="7">近 7 天</el-radio-button><el-radio-button :value="30">近 30 天</el-radio-button></el-radio-group></template>
    </AppPageHeader>
    <div class="asset-cards">
      <AppStatCardMini label="功能用例" :value="data?.cards.case_total.by_type.functional ?? 0" icon="i-app-test-case" color="brand" />
      <AppStatCardMini label="App 用例" :value="data?.cards.case_total.by_type.app ?? 0" icon="i-app-mobile" color="info" />
      <AppStatCardMini label="App 套件" :value="data?.cards.suites.value ?? 0" icon="i-app-test-suite" color="purple" />
      <AppStatCardMini label="需求" :value="data?.cards.requirements.value ?? 0" icon="i-solar-document-text-bold" color="warning" />
      <AppStatCardMini label="知识库文档" :value="data?.cards.kb_documents.value ?? 0" icon="i-app-knowledge" color="brand" />
      <AppStatCardMini label="AI 生成用例" :value="data?.cards.ai_cases.value ?? 0" icon="i-app-ai-agent" color="purple" />
    </div>
    <div class="asset-grid">
      <AppSectionCard title="需求覆盖率"><el-progress :percentage="data?.coverage.requirement.rate ?? 0" /><p>{{ data?.coverage.requirement.covered ?? 0 }} / {{ data?.coverage.requirement.total ?? 0 }} 条需求已有用例</p></AppSectionCard>
      <AppSectionCard title="功能用例评审率"><el-progress :percentage="data?.coverage.review.rate ?? 0" color="#8b5cf6" /><p>{{ data?.coverage.review.reviewed ?? 0 }} / {{ data?.coverage.review.total ?? 0 }} 条用例已评审</p></AppSectionCard>
    </div>
    <AppSectionCard title="新增用例趋势"><v-chart :option="growthOption" class="growth-chart" autoresize /></AppSectionCard>
  </div>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useProjectWorkspaceStore } from '@/stores/projectWorkspace'
import { AppPageHeader, AppSectionCard, AppStatCardMini } from '@/components/common'
import { reportCenterApi, type AssetsReportData } from '@/api/report-center'
import { ElMessage } from 'element-plus'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])
const workspace = useProjectWorkspaceStore()
const projectId = computed(() => workspace.currentProject?.id || 0)
const days = ref(30), loading = ref(false)
const data = ref<AssetsReportData | null>(null)
let version = 0
watch([projectId, days], async ([id, window]) => {
  const current = ++version
  data.value = null
  if (!id) return
  loading.value = true
  try { const result = await reportCenterApi.assets(id, window); if (current === version) data.value = result.data }
  catch { if (current === version) ElMessage.error('测试资产加载失败') }
  finally { if (current === version) loading.value = false }
}, { immediate: true })
const growthOption = computed(() => ({
  tooltip: { trigger: 'axis' }, legend: { data: ['功能用例', 'App 用例'] },
  grid: { left: 48, right: 24, top: 40, bottom: 30 },
  xAxis: { type: 'category', data: data.value?.growth_trend.map(item => item.date) ?? [] },
  yAxis: { type: 'value', minInterval: 1 },
  series: [
    { name: '功能用例', type: 'line', smooth: true, data: data.value?.growth_trend.map(item => item.functional) ?? [] },
    { name: 'App 用例', type: 'line', smooth: true, data: data.value?.growth_trend.map(item => item.app) ?? [] },
  ],
}))
</script>
<style scoped>
.report-page { display: flex; flex-direction: column; gap: 20px; }
.asset-cards { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
.asset-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; }
.asset-grid p { color: var(--text-secondary); margin-top: 16px; }
.growth-chart { height: 320px; }
@media (max-width: 800px) { .asset-cards, .asset-grid { grid-template-columns: 1fr; } }
</style>
