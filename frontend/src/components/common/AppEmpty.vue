<template>
  <div class="app-empty">
    <div class="empty-illustration" :class="`is-${scene}`">
      <slot name="illustration">
        <img :src="illustrationSrc" :alt="scene" class="empty-svg" />
      </slot>
    </div>
    <h3 class="empty-title">
      <slot name="title">{{ title || defaultTitle }}</slot>
    </h3>
    <p v-if="description || $slots.description" class="empty-desc">
      <slot name="description">{{ description }}</slot>
    </p>
    <div v-if="$slots.actions" class="empty-actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * AppEmpty - 场景化空状态（统一引用 assets/illustrations 资产）
 *
 * 用法：
 *   <AppEmpty scene="data" description="还没有任何测试用例">
 *     <template #actions>
 *       <el-button type="primary">+ 新建用例</el-button>
 *     </template>
 *   </AppEmpty>
 *
 * 也可以传入自定义图：
 *   <AppEmpty :illustration="myCustomSvg" />
 */
import { computed } from 'vue'
import emptyData from '@/assets/illustrations/empty-data.svg'
import emptySearch from '@/assets/illustrations/empty-search.svg'
import error404 from '@/assets/illustrations/error-404.svg'
import errorNetwork from '@/assets/illustrations/error-network.svg'
import errorPermission from '@/assets/illustrations/error-permission.svg'
import welcome from '@/assets/illustrations/welcome.svg'
import aiThinking from '@/assets/illustrations/ai-thinking.svg'
import successDone from '@/assets/illustrations/success-done.svg'
import running from '@/assets/illustrations/running.svg'
import bugFix from '@/assets/illustrations/bug-fix.svg'
import noNotification from '@/assets/illustrations/no-notification.svg'
import report from '@/assets/illustrations/report.svg'
import maintenance from '@/assets/illustrations/maintenance.svg'
import team from '@/assets/illustrations/team.svg'
import aiCaseGen from '@/assets/illustrations/ai-case-gen.svg'
import aiKnowledge from '@/assets/illustrations/ai-knowledge.svg'
import aiChat from '@/assets/illustrations/ai-chat.svg'
import aiAgent from '@/assets/illustrations/ai-agent.svg'
import testApi from '@/assets/illustrations/test-api.svg'
import testWeb from '@/assets/illustrations/test-web.svg'
import testApp from '@/assets/illustrations/test-app.svg'
import testPerformance from '@/assets/illustrations/test-performance.svg'

type Scene =
  | 'data'
  | 'search'
  | 'network'
  | 'permission'
  | 'notFound'
  | 'welcome'
  | 'ai'
  | 'success'
  | 'running'
  | 'bug'
  | 'noNotification'
  | 'report'
  | 'maintenance'
  | 'team'
  | 'aiCaseGen'
  | 'aiKnowledge'
  | 'aiChat'
  | 'aiAgent'
  | 'testApi'
  | 'testWeb'
  | 'testApp'
  | 'testPerformance'

const props = withDefaults(
  defineProps<{
    scene?: Scene
    title?: string
    description?: string
    /** 自定义插画（覆盖 scene） */
    illustration?: string
  }>(),
  {
    scene: 'data',
  },
)

const sceneTitles: Record<Scene, string> = {
  data: '暂无数据',
  search: '未找到匹配结果',
  network: '网络连接失败',
  permission: '无访问权限',
  notFound: '页面不存在',
  welcome: '开始你的第一步',
  ai: 'AI 正在思考...',
  success: '任务完成',
  running: '测试执行中',
  bug: '修复缺陷中',
  noNotification: '暂无通知',
  report: '报告已生成',
  maintenance: '系统维护中',
  team: '邀请团队成员',
  aiCaseGen: 'AI 用例生成中',
  aiKnowledge: '知识图谱',
  aiChat: 'AI 智能助手',
  aiAgent: '多 Agent 协作',
  testApi: '接口测试',
  testWeb: 'Web 自动化',
  testApp: 'App 自动化',
  testPerformance: '性能测试',
}

const sceneIllustrations: Record<Scene, string> = {
  data: emptyData,
  search: emptySearch,
  network: errorNetwork,
  permission: errorPermission,
  notFound: error404,
  welcome,
  ai: aiThinking,
  success: successDone,
  running,
  bug: bugFix,
  noNotification,
  report,
  maintenance,
  team,
  aiCaseGen,
  aiKnowledge,
  aiChat,
  aiAgent,
  testApi,
  testWeb,
  testApp,
  testPerformance,
}

const defaultTitle = computed(() => sceneTitles[props.scene])
const illustrationSrc = computed(
  () => props.illustration || sceneIllustrations[props.scene],
)
</script>

<style scoped lang="scss">
.app-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-12) var(--space-6);
  text-align: center;
}

.empty-illustration {
  width: 240px;
  height: 180px;
  margin-bottom: var(--space-4);
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-svg {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}

.empty-title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin: 0 0 var(--space-2);
}

.empty-desc {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin: 0 0 var(--space-5);
  max-width: 360px;
  line-height: var(--line-height-relaxed);
}

.empty-actions {
  display: flex;
  gap: var(--space-3);
}
</style>
