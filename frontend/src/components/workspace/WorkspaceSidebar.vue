<template>
  <aside class="app-sidebar" :class="{ 'is-collapsed': collapsed }">
    <!-- 折叠触发器 -->
    <div class="sb-collapse-trigger" @click="toggleCollapse">
      <i v-if="collapsed" class="i-solar-alt-arrow-right-linear" />
      <i v-else class="i-solar-alt-arrow-left-linear" />
    </div>

    <!-- 菜单 -->
    <el-menu
      :default-active="activeMenu"
      :collapse="collapsed"
      :unique-opened="false"
      router
      class="sb-menu"
    >
      <!-- 项目概览 -->
      <el-menu-item :index="basePath + '/overview'">
        <i class="i-solar-home-2-bold-duotone sb-icon" />
        <template #title>项目概览</template>
      </el-menu-item>
  

      <!-- 数据报表 -->
      <el-sub-menu
        v-if="userStore.hasPermission('report:view')"
        index="reports"
      >
        <template #title>
          <i class="i-app-test-report sb-icon" />
          <span>数据报表</span>
        </template>
        <el-menu-item :index="basePath + '/reports/assets'">
          <span class="sb-child-dot" /><template #title>测试资产</template>
        </el-menu-item>
        <el-menu-item :index="basePath + '/reports'">
          <span class="sb-child-dot" /><template #title>执行汇总</template>
        </el-menu-item>
        <el-menu-item :index="basePath + '/reports/quality'">
          <span class="sb-child-dot" /><template #title>缺陷质量</template>
        </el-menu-item>
        <el-menu-item :index="basePath + '/reports/ai'">
          <span class="sb-child-dot" /><template #title>AI 提效</template>
        </el-menu-item>
      </el-sub-menu>

      <!-- AI 中心 -->
      <el-sub-menu
        v-if="userStore.hasAnyPermission('chat:use', 'agent_experience:view')"
        index="ai-center"
      >
        <template #title>
          <i class="i-solar-alarm-bold-duotone sb-icon" />
          <span>AI Agent中心</span>
        </template>
        <el-menu-item :index="basePath + '/ai/chat'">
          <span class="sb-child-dot" /><template #title>AI智能助手</template>
        </el-menu-item>
           <!-- Agent 经验库（跨域，独立权限 agent_experience:view） -->
      
      
        
      </el-sub-menu>

      <!-- 任务管理 -->
      <el-sub-menu
        v-if="userStore.hasAnyPermission('ai_task:view', 'scheduler:view', 'system:monitor')"
        index="task-management"
      >
        <template #title>
          <i class="i-solar-checklist-bold-duotone sb-icon" />
          <span>任务监控中心</span>
        </template>
         <el-menu-item
          v-if="userStore.hasPermission('system:monitor')"
          :index="basePath + '/celery-monitor'"
        >
          <span class="sb-child-dot" /><template #title>work节点监控</template>
        </el-menu-item>
         <el-menu-item :index="basePath + '/ai/task-center'">
          <span class="sb-child-dot" /><template #title>Agent任务监控</template>
        </el-menu-item>
       
       
        <el-menu-item :index="basePath + '/ai/exec-center'">
          <span class="sb-child-dot" /><template #title>用例执行监控</template>
        </el-menu-item>
        <el-menu-item :index="basePath + '/scheduled-jobs'">
          <span class="sb-child-dot" /><template #title>定时任务</template>
        </el-menu-item>
        
      </el-sub-menu>
      

      <!-- 项目配置 -->
      <el-sub-menu
        v-if="userStore.hasAnyPermission('member:view', 'module:view', 'environment:view')"
        index="settings"
      >
        <template #title>
          <i class="i-solar-settings-bold-duotone sb-icon" />
          <span>项目配置</span>
        </template>
        <el-menu-item :index="basePath + '/members'">
          <span class="sb-child-dot" /><template #title>成员管理</template>
        </el-menu-item>
        <el-menu-item :index="basePath + '/modules'">
          <span class="sb-child-dot" /><template #title>模块管理</template>
        </el-menu-item>
        <el-menu-item :index="basePath + '/environments'">
          <span class="sb-child-dot" /><template #title>环境管理</template>
        </el-menu-item>
        <el-menu-item :index="basePath + '/environments/databases'">
          <span class="sb-child-dot" /><template #title>数据库连接</template>
        </el-menu-item>
        <el-menu-item :index="basePath + '/environments/functions'">
          <span class="sb-child-dot" /><template #title>全局函数</template>
        </el-menu-item>
        
      </el-sub-menu>

      <!-- 项目知识库 -->
      <el-sub-menu
        v-if="userStore.hasAnyPermission('test_case:view', 'knowledge:view')"
        index="knowledge"
      >
        <template #title>
          <i class="i-app-knowledge sb-icon" />
          <span>项目知识库</span>
        </template>
        <el-menu-item :index="basePath + '/function-test/documents'">
          <span class="sb-child-dot" /><template #title>项目文档</template>
        </el-menu-item>
        <el-menu-item :index="basePath + '/knowledge/documents'">
          <span class="sb-child-dot" /><template #title>知识内容</template>
        </el-menu-item>
        <el-menu-item :index="basePath + '/knowledge/query'">
          <span class="sb-child-dot" /><template #title>知识检索</template>
        </el-menu-item>
        <el-menu-item :index="basePath + '/knowledge/graph'">
          <span class="sb-child-dot" /><template #title>知识图谱</template>
        </el-menu-item>
      </el-sub-menu>

      <!-- AI 造数中心（跨模块基础数据：压测数据集 / 文件数据集 / 测试数据集） -->
      <el-sub-menu
        v-if="userStore.hasPermission('test_data:view')"
        index="test-data-center"
      >
        <template #title>
          <i class="i-solar-cpu-bolt-bold sb-icon" />
          <span>AI 造数中心</span>
        </template>
        
        <el-menu-item :index="basePath + '/test-data'">
          <span class="sb-child-dot" /><template #title>文件数据集</template>
        </el-menu-item>
        <el-menu-item :index="basePath + '/test-data/datasets'">
          <span class="sb-child-dot" /><template #title>测试数据集</template>
        </el-menu-item>
      </el-sub-menu>

      <!-- 功能测试 -->
      <el-sub-menu
        v-if="userStore.hasPermission('test_case:view')"
        index="function-test"
      >
        <template #title>
          <i class="i-app-test-case sb-icon" />
          <span>功能测试</span>
        </template>
        <el-menu-item :index="basePath + '/function-test/requirements'">
          <span class="sb-child-dot" /><template #title>需求管理</template>
        </el-menu-item>
        <el-menu-item :index="basePath + '/function-test/cases'">
          <span class="sb-child-dot" /><template #title>用例管理</template>
        </el-menu-item>
      </el-sub-menu>

      <!-- Web 自动化 -->
      

   


      <!-- 接口测试 -->
      


      <!-- 性能测试（压测） -->
      

      <!-- App 自动化 -->
      <el-sub-menu
        v-if="userStore.hasAnyPermission('app_device:view', 'app_test:create')"
        index="app"
      >
        <template #title>
          <i class="i-app-mobile sb-icon" />
          <span>App 自动化</span>
        </template>
        <el-menu-item :index="basePath + '/app/devices'">
          <span class="sb-child-dot" /><template #title>设备管理</template>
        </el-menu-item>
        <el-menu-item :index="basePath + '/app/console'">
          <span class="sb-child-dot" /><template #title>智能操作台</template>
        </el-menu-item>
        <el-menu-item :index="basePath + '/app/cases'">
          <span class="sb-child-dot" /><template #title>测试用例</template>
        </el-menu-item>
        <el-menu-item :index="basePath + '/app/suites'">
          <span class="sb-child-dot" /><template #title>测试套件</template>
        </el-menu-item>
        <el-menu-item :index="basePath + '/app/executions'">
          <span class="sb-child-dot" /><template #title>执行记录</template>
        </el-menu-item>
      </el-sub-menu>
    
      <!-- 常用工具 -->
      <el-sub-menu index="tools">
        <template #title>
          <i class="i-solar-test-tube-bold-duotone sb-icon" />
          <span>常用工具</span>
        </template>
        <el-menu-item :index="basePath + '/tools/json-formatter'">
          <span class="sb-child-dot" /><template #title>JSON 格式化</template>
        </el-menu-item>
        <el-menu-item :index="basePath + '/tools/diff'">
          <span class="sb-child-dot" /><template #title>文本 Diff</template>
        </el-menu-item>
        <el-menu-item :index="basePath + '/tools/encoder'">
          <span class="sb-child-dot" /><template #title>编解码工具</template>
        </el-menu-item>
        <el-menu-item :index="basePath + '/tools/timestamp'">
          <span class="sb-child-dot" /><template #title>时间戳转换</template>
        </el-menu-item>
        <el-menu-item :index="basePath + '/tools/hash'">
          <span class="sb-child-dot" /><template #title>Hash 计算</template>
        </el-menu-item>
      </el-sub-menu>

      <!-- 缺陷管理 -->
      <el-menu-item
        v-if="userStore.hasPermission('bug:view')"
        :index="basePath + '/bugs'"
      >
        <i class="i-app-bug sb-icon" />
        <template #title>缺陷管理</template>
      </el-menu-item>
          </el-menu>
    <!-- 底部品牌区 -->
    <div class="sb-footer" v-if="!collapsed">
      <div class="sb-foot-row">
        <i class="i-solar-shield-check-bold-duotone foot-icon" />
        <div class="foot-text">
          <div class="foot-title">{{ currentProject?.name || 'AutoTest Platform' }}</div>
          <div class="foot-sub">v2.4.0</div>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useProjectWorkspaceStore } from '@/stores/projectWorkspace'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const workspaceStore = useProjectWorkspaceStore()
const userStore = useUserStore()

const currentProject = computed(() => workspaceStore.currentProject)
const collapsed = computed(() => workspaceStore.sidebarCollapsed)

const basePath = computed(() => {
  const id = route.params.id as string
  return `/project-workspace/${id}`
})

const activeMenu = computed(() => route.path)

const toggleCollapse = () => {
  workspaceStore.toggleSidebar()
}
</script>

<style scoped lang="scss">
.app-sidebar {
  width: var(--layout-sidebar-w);
  height: 100%;
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border-base);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: width var(--duration-normal) var(--ease-out);
  position: relative;

  &.is-collapsed {
    width: var(--layout-sidebar-collapse);
  }
}

/* 折叠触发器 */
.sb-collapse-trigger {
  position: absolute;
  top: 16px;
  right: -10px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--bg-card);
  border: 1px solid var(--border-base);
  box-shadow: var(--shadow-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--text-secondary);
  z-index: 2;
  transition: var(--transition-fast);

  i { font-size: 12px; }

  &:hover {
    background: var(--brand-500);
    border-color: var(--brand-500);
    color: #FFFFFF;
  }
}

.sb-menu {
  flex: 1;
  border: none !important;
  background: transparent !important;
  padding: var(--space-3) 0;
  overflow-y: auto;
  overflow-x: hidden;

  &::-webkit-scrollbar { width: 4px; }
  &::-webkit-scrollbar-thumb {
    background: var(--gray-300);
    border-radius: 2px;
  }
}

.sb-icon {
  font-size: 18px;
  margin-right: 10px;
  flex-shrink: 0;
  vertical-align: -3px;
}

.sb-child-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--gray-300);
  margin-right: 10px;
  margin-left: 4px;
  flex-shrink: 0;
  transition: background var(--duration-fast);
}

/* Menu 样式 */
:deep(.el-menu) {
  background: transparent !important;
}

:deep(.el-menu-item),
:deep(.el-sub-menu__title) {
  height: 40px;
  line-height: 40px;
  margin: 2px var(--space-2);
  padding-left: var(--space-3) !important;
  padding-right: var(--space-3) !important;
  border-radius: var(--radius-md);
  color: var(--text-regular);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  transition: var(--transition-fast);

  &:hover {
    background: var(--bg-hover) !important;
    color: var(--text-primary);
  }
}

/* 激活态：浅绿底 + 主色字 + 3px 左侧主色竖条 */
:deep(.el-menu-item.is-active) {
  background: var(--brand-50) !important;
  color: var(--brand-700) !important;
  font-weight: var(--font-weight-semibold);
  position: relative;

  &::before {
    content: '';
    position: absolute;
    left: -8px;
    top: 8px;
    bottom: 8px;
    width: 3px;
    border-radius: 0 2px 2px 0;
    background: var(--brand-500);
  }

  .sb-icon { color: var(--brand-600); }
  .sb-child-dot { background: var(--brand-500); }
}

/* 子菜单 */
:deep(.el-sub-menu) {
  .el-sub-menu__title {
    color: var(--text-regular);
  }

  &.is-active > .el-sub-menu__title {
    color: var(--brand-700);
    .sb-icon { color: var(--brand-600); }
  }

  &.is-opened > .el-sub-menu__title {
    color: var(--text-primary);
  }

  .el-menu-item {
    height: 36px;
    line-height: 36px;
    font-size: var(--font-size-sm);
    padding-left: var(--space-8) !important;
  }
}

/* 折叠态 */
.app-sidebar.is-collapsed {
  :deep(.el-menu-item),
  :deep(.el-sub-menu__title) {
    padding-left: 0 !important;
    padding-right: 0 !important;
    justify-content: center;

    .sb-icon { margin-right: 0; }
  }
}

/* 底部 */
.sb-footer {
  padding: var(--space-3) var(--space-4);
  border-top: 1px solid var(--border-light);
  flex-shrink: 0;
}

.sb-foot-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2);
  border-radius: var(--radius-md);
  background: var(--bg-hover);
}

.foot-icon {
  font-size: 22px;
  color: var(--brand-500);
  flex-shrink: 0;
}

.foot-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.foot-title {
  font-size: 12px;
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.foot-sub {
  font-size: 11px;
  font-family: var(--font-mono);
  color: var(--text-secondary);
}
</style>
