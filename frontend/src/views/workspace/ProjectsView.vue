/**
 * 我的项目页面
 *
 * AI 智能测试平台 - 项目管理首页
 * 设计规范：design-system tokens + 通用组件
 */

<template>
  <AppGlowBg variant="soft" :orbs="false">
    <div class="projects-view">
      <!-- ====== Hero 欢迎区 ====== -->
      <div class="hero-section">
        <div class="hero-content">
          <div class="hero-text">
            <h1 class="hero-title">
              <span class="hero-wave">👋</span>
              欢迎回来，{{ userName }}
            </h1>
            <p class="hero-desc">
              管理你的测试项目，协同团队高效交付。开始你的测试之旅吧。
            </p>
            <div class="hero-actions">
              <el-button type="primary" size="large" :icon="Plus" @click="handleCreateProject">
                创建新项目
              </el-button>
              <el-button size="large" :icon="Refresh" @click="handleRefresh">
                刷新
              </el-button>
            </div>
          </div>
          <div class="hero-illustration">
            <img :src="illustAiAgent" alt="AI Agent" />
          </div>
        </div>
      </div>

      <!-- ====== 搜索筛选栏 ====== -->
      <div class="filter-bar">
        <div class="filter-left">
          <el-input
            v-model="searchForm.keyword"
            placeholder="搜索项目名称或描述..."
            clearable
            :prefix-icon="Search"
            style="width: 260px"
            @keyup.enter="handleSearch"
          />
          <el-select
            v-model="searchForm.status"
            placeholder="状态"
            clearable
            style="width: 120px"
          >
            <el-option label="活跃" value="active" />
            <el-option label="已归档" value="archived" />
          </el-select>
          <el-select
            v-model="searchForm.owner_id"
            placeholder="负责人"
            clearable
            style="width: 130px"
          >
            <el-option
              v-for="m in ownerOptions"
              :key="m.id"
              :label="m.real_name"
              :value="m.id"
            />
          </el-select>
        </div>
        <div class="filter-right">
          <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
          <el-button :icon="RefreshLeft" @click="handleReset">重置</el-button>
        </div>
      </div>

      <!-- ====== 项目卡片列表 ====== -->
      <div v-loading="projectStore.loading" class="projects-grid">
        <div
          v-for="project in projectStore.projects"
          :key="project.id"
          class="project-card"
        >
          <!-- 卡片顶部 -->
          <div class="card-top">
            <div class="card-head">
              <div
                class="project-avatar"
                :style="{ background: getAvatarBg(project.name) }"
              >
                <img
                  :src="getProjectIcon(project)"
                  :alt="project.name"
                  class="avatar-img"
                />
              </div>
              <div class="card-title-wrap">
                <div class="title-line">
                  <h3 class="project-name" :title="project.name">
                    {{ project.name }}
                  </h3>
                  <span
                    class="status-pill"
                    :class="`is-${project.status === 'active' ? 'active' : 'archived'}`"
                  >
                    {{ project.status === 'active' ? '活跃' : '已归档' }}
                  </span>
                </div>
                <p class="project-desc" :title="project.description">
                  {{ project.description || '暂无描述' }}
                </p>
              </div>
              <el-dropdown trigger="click" @command="(cmd: string) => handleCommand(cmd, project)">
                <i class="i-solar-dots-vertical-bold more-icon" />
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="open">打开项目</el-dropdown-item>
                    <el-dropdown-item command="edit">编辑</el-dropdown-item>
                    <el-dropdown-item command="archive" divided>
                      {{ project.status === 'active' ? '归档' : '恢复' }}
                    </el-dropdown-item>
                    <el-dropdown-item command="delete" divided>
                      <span style="color: var(--color-danger-500)">删除</span>
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>

            <!-- 信息行：负责人 -->
            <div class="meta-block">
              <div class="meta-block-item">
                <span class="meta-label">
                  <i class="i-solar-user-circle-bold" />
                  负责人
                </span>
                <div class="meta-owner">
                  <AppAvatar
                    v-if="project.owner"
                    :name="project.owner.real_name"
                    :size="22"
                  />
                  <span class="owner-name">{{ project.owner?.real_name || '未设置' }}</span>
                </div>
              </div>
            </div>

            <!-- 统计行：成员/模块/用例/缺陷 -->
            <div class="meta-grid">
              <div class="meta-grid-item">
                <span class="meta-label">
                  <i class="i-solar-users-group-rounded-bold" />
                  成员
                </span>
                <span class="meta-value">{{ project.member_count }} 人</span>
              </div>
              <div class="meta-grid-item">
                <span class="meta-label">
                  <i class="i-solar-box-bold" />
                  模块
                </span>
                <span class="meta-value">{{ project.module_count }}</span>
              </div>
              <div class="meta-grid-item">
                <span class="meta-label">
                  <i class="i-solar-document-text-bold" />
                  用例
                </span>
                <span class="meta-value">{{ project.case_count }}</span>
              </div>
              <div class="meta-grid-item">
                <span class="meta-label">
                  <i class="i-solar-bug-bold" />
                  缺陷
                </span>
                <span class="meta-value">{{ project.bug_count }}</span>
              </div>
            </div>
          </div>

          <!-- 卡片底部操作 -->
          <div class="card-bottom">
            <el-button
              type="primary"
              plain
              size="small"
              @click="handleProjectClick(project)"
            >
              打开项目
            </el-button>
            <el-button size="small" @click="handleEditProject(project)">
              编辑
            </el-button>
            <el-button
              size="small"
              @click="handleArchiveToggle(project)"
            >
              {{ project.status === 'active' ? '归档' : '恢复' }}
            </el-button>
            <el-button
              size="small"
              :icon="Delete"
              circle
              @click="handleDeleteProject(project)"
            />
          </div>
        </div>

        <!-- 空状态 -->
        <div v-if="!projectStore.loading && !projectStore.hasProjects" class="empty-state">
          <AppEmpty scene="data" description="还没有任何项目，开始创建你的第一个项目吧">
            <template #actions>
              <el-button type="primary" :icon="Plus" @click="handleCreateProject">
                创建项目
              </el-button>
            </template>
          </AppEmpty>
        </div>
      </div>

      <!-- 分页 -->
      <div v-if="projectStore.hasProjects" class="pagination-container">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="projectStore.total"
          :page-sizes="[12, 24, 48]"
          layout="total, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />
      </div>

      <!-- 创建/编辑项目对话框 -->
      <ProjectCreateDialog
        v-model="dialogVisible"
        :mode="dialogMode"
        :project="currentProject"
        @success="handleDialogSuccess"
      />
    </div>
  </AppGlowBg>
</template>

<script setup lang="ts">import { ref, reactive, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useProjectStore } from '@/stores/projects';
import { useProjectWorkspaceStore } from '@/stores/projectWorkspace';
import { useUserStore } from '@/stores/user';
import { ElMessageBox, ElMessage } from 'element-plus';
import { Plus, Search, Refresh, RefreshLeft, FolderOpened, Folder, Delete, } from '@element-plus/icons-vue';
import type { Project, ProjectStatus } from '@/api/projects';
import { AppGlowBg, AppAvatar, AppEmpty } from '@/components/common';
import ProjectCreateDialog from '@/components/project/ProjectCreateDialog.vue';
// 插画
import illustAiAgent from '@/assets/illustrations/ai-agent.svg';
// 项目图标
import illustProjectEcommerce from '@/assets/illustrations/project-ecommerce.svg';
import illustProjectApp from '@/assets/illustrations/project-app.svg';
import illustProjectApi from '@/assets/illustrations/project-api.svg';
import illustProjectWeb from '@/assets/illustrations/project-web.svg';
import illustProjectDefault from '@/assets/illustrations/project-default.svg';
import illustProjectAi from '@/assets/illustrations/project-ai.svg';
import illustProjectPerf from '@/assets/illustrations/project-perf.svg';
import illustProjectPay from '@/assets/illustrations/project-pay.svg';
const router = useRouter();
const projectStore = useProjectStore();
const userStore = useUserStore();
const userName = computed(() => userStore.userInfo?.real_name || userStore.userInfo?.username || '用户');
// ==================== 状态 ====================
const searchForm = reactive({
    keyword: '',
    status: '' as ProjectStatus | '',
    owner_id: undefined as number | undefined,
    dateRange: [] as string[],
});
const currentPage = ref(1);
const pageSize = ref(12);
const dialogVisible = ref(false);
const dialogMode = ref<'create' | 'edit'>('create');
const currentProject = ref<Project | null>(null);
// ==================== 计算属性 ====================
const ownerOptions = computed(() => {
    const map = new Map<number, {
        id: number;
        real_name: string;
    }>();
    projectStore.projects.forEach((p) => {
        if (p.owner) {
            map.set(p.owner.id, { id: p.owner.id, real_name: p.owner.real_name });
        }
    });
    return Array.from(map.values());
});
// ==================== 工具方法 ====================
function hashStr(s: string): number {
    let h = 0;
    for (let i = 0; i < s.length; i++) {
        h = (h << 5) - h + s.charCodeAt(i);
        h |= 0;
    }
    return Math.abs(h);
}
const avatarPalette = [
    'var(--brand-100)',
    'var(--color-info-50)',
    'var(--color-purple-50)',
    'var(--color-warning-50)',
    'var(--color-pink-50)',
    'var(--color-cyan-50)',
];
function getAvatarBg(name: string) {
    return avatarPalette[hashStr(name) % avatarPalette.length];
}
type ProjectKind = 'ecommerce' | 'app' | 'ai' | 'pay' | 'default';
const projectIconMap: Record<ProjectKind, string> = {
    ecommerce: illustProjectEcommerce,
    app: illustProjectApp,
    ai: illustProjectAi,
    pay: illustProjectPay,
    default: illustProjectDefault
};
const kindRules: Array<{
    kind: ProjectKind;
    keywords: string[];
}> = [
    { kind: 'pay', keywords: ['支付', 'pay', 'payment', 'wallet', '钱包', '收银', '交易'] },
    { kind: 'ecommerce', keywords: ['电商', '商城', 'shop', 'mall', '商品', '订单', '购物', '零售'] },
    { kind: 'ai', keywords: ['ai', '智能', 'agent', 'gpt', '大模型', 'llm', '知识库', '知识图谱'] },
    { kind: 'app', keywords: ['app', '移动', 'ios', 'android', '手机', '小程序'] },
];
function detectProjectKind(project: Project): ProjectKind {
    const text = `${project.name} ${project.code || ''} ${project.description || ''}`.toLowerCase();
    for (const rule of kindRules) {
        if (rule.keywords.some((kw) => text.includes(kw.toLowerCase()))) {
            return rule.kind;
        }
    }
    return 'default';
}
function getProjectIcon(project: Project): string {
    return projectIconMap[detectProjectKind(project)];
}
// ==================== 方法 ====================
const handleSearch = () => {
    currentPage.value = 1;
    const [start_date, end_date] = searchForm.dateRange || [];
    projectStore.fetchProjects({
        keyword: searchForm.keyword || undefined,
        status: (searchForm.status as ProjectStatus) || undefined,
        page: currentPage.value,
        page_size: pageSize.value,
        start_date,
        end_date,
    });
};
const handleReset = () => {
    searchForm.keyword = '';
    searchForm.status = '';
    searchForm.owner_id = undefined;
    searchForm.dateRange = [];
    currentPage.value = 1;
    projectStore.resetQueryParams();
    projectStore.fetchProjects({ page: 1, page_size: pageSize.value });
};
const handleRefresh = () => {
    projectStore.fetchProjects({ page: currentPage.value, page_size: pageSize.value });
};
const handleCreateProject = () => {
    dialogMode.value = 'create';
    currentProject.value = null;
    dialogVisible.value = true;
};
const handleEditProject = (project: Project) => {
    dialogMode.value = 'edit';
    currentProject.value = project;
    dialogVisible.value = true;
};
const handleProjectClick = (project: Project) => {
    const workspaceStore = useProjectWorkspaceStore();
    workspaceStore.setCurrentProject(project);
    router.push(`/project-workspace/${project.id}`);
};
const handleCommand = (cmd: string, project: Project) => {
    if (cmd === 'open')
        return handleProjectClick(project);
    if (cmd === 'edit') {
        dialogMode.value = 'edit';
        currentProject.value = project;
        dialogVisible.value = true;
        return;
    }
    if (cmd === 'archive')
        return handleArchiveToggle(project);
    if (cmd === 'delete')
        return handleDeleteProject(project);
};
const handleArchiveToggle = async (project: Project) => {
    try {
        if (project.status === 'active') {
            await ElMessageBox.confirm(`确定要归档项目「${project.name}」吗？归档后项目将变为只读状态。`, '归档确认', { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' });
            const success = await projectStore.archiveProject(project.id);
            if (success)
                ElMessage.success('归档成功');
        }
        else {
            await ElMessageBox.confirm(`确定要恢复项目「${project.name}」吗？`, '恢复确认', { confirmButtonText: '确定', cancelButtonText: '取消', type: 'info' });
            const success = await projectStore.restoreProject(project.id);
            if (success)
                ElMessage.success('恢复成功');
        }
    }
    catch {
        // 用户取消
    }
};
const handleDeleteProject = async (project: Project) => {
    try {
        await ElMessageBox.confirm(`确定要删除项目「${project.name}」吗？删除后将无法恢复。`, '删除确认', { confirmButtonText: '确定', cancelButtonText: '取消', type: 'error' });
        const success = await projectStore.deleteProject(project.id);
        if (success)
            ElMessage.success('删除成功');
    }
    catch {
        // 用户取消
    }
};
const handleSizeChange = (size: number) => {
    pageSize.value = size;
    currentPage.value = 1;
    projectStore.fetchProjects({ page: 1, page_size: size });
};
const handlePageChange = (page: number) => {
    currentPage.value = page;
    projectStore.fetchProjects({ page, page_size: pageSize.value });
};
const handleDialogSuccess = () => {
    dialogVisible.value = false;
    projectStore.fetchProjects();
};
// ==================== 生命周期 ====================
onMounted(() => {
    projectStore.fetchProjects({ page: 1, page_size: pageSize.value });
});
</script>

<style lang="scss" scoped>
.projects-view {
  padding: var(--space-6);
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  min-height: 100%;
}

/* ========== Hero 欢迎区 ========== */
.hero-section {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.hero-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-8) var(--space-8) var(--space-5);
  gap: var(--space-6);
}

.hero-text {
  flex: 1;
  min-width: 0;
}

.hero-title {
  font-size: var(--font-size-4xl);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  margin: 0 0 var(--space-3);
  line-height: var(--line-height-tight);
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.hero-wave {
  font-size: 32px;
}

.hero-desc {
  font-size: var(--font-size-base);
  color: var(--text-secondary);
  margin: 0 0 var(--space-6);
  line-height: var(--line-height-relaxed);
  max-width: 480px;
}

.hero-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.hero-illustration {
  flex-shrink: 0;
  width: 200px;
  height: 160px;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0.9;

  img {
    width: 100%;
    height: 100%;
    object-fit: contain;
  }
}

/* ========== 搜索筛选栏 ========== */
.filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-5);
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs);
}

.filter-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.filter-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

/* ========== 项目卡片网格 ========== */
.projects-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--space-5);
  min-height: 300px;
}

/* ========== 项目卡片 ========== */
.project-card {
  display: flex;
  flex-direction: column;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  transition: var(--transition-base);
  overflow: hidden;

  &:hover {
    transform: translateY(-3px);
    box-shadow: var(--shadow-hover);
    border-color: var(--brand-300);
  }
}

.card-top {
  padding: var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  flex: 1;
  min-height: 220px;
}

.card-head {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
}

.project-avatar {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  overflow: hidden;
  padding: 4px;
}
.avatar-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}

.card-title-wrap {
  flex: 1;
  min-width: 0;
}
.title-line {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: 4px;
}
.project-name {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin: 0;
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.project-desc {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  min-height: 42px;
}

.more-icon {
  font-size: 20px;
  color: var(--text-placeholder);
  cursor: pointer;
  padding: 4px;
  border-radius: var(--radius-sm);
  transition: var(--transition-fast);
  flex-shrink: 0;
  &:hover {
    color: var(--text-primary);
    background: var(--bg-hover);
  }
}

/* 状态徽章 */
.status-pill {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: var(--radius-xs);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  flex-shrink: 0;

  &.is-active   { background: var(--color-success-50); color: var(--color-success-600); }
  &.is-archived { background: var(--gray-100);          color: var(--gray-600); }
}

/* 负责人行 */
.meta-block {
  padding: var(--space-3) 0;
  border-top: 1px solid var(--border-light);
  border-bottom: 1px solid var(--border-light);
}
.meta-block-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
}
.meta-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--text-secondary);

  i {
    font-size: 16px;
  }
}
.meta-owner {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}
.owner-name {
  font-size: var(--font-size-sm);
  color: var(--text-primary);
  font-weight: var(--font-weight-medium);
}

/* 统计行 */
.meta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2) var(--space-3);
}
.meta-grid-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
}
.meta-value {
  color: var(--text-primary);
  font-weight: var(--font-weight-medium);
}

/* 卡片底部 */
.card-bottom {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-5);
  border-top: 1px solid var(--border-light);
  background: var(--gray-50);
}

/* 空状态 */
.empty-state {
  grid-column: 1 / -1;
  background: var(--bg-card);
  border: 1px dashed var(--border-base);
  border-radius: var(--radius-lg);
  padding: var(--space-8);
}

/* 分页 */
.pagination-container {
  display: flex;
  justify-content: center;
  padding: var(--space-4) 0 0;
}

/* ========== 响应式 ========== */
@media (max-width: 900px) {
  .projects-view {
    padding: var(--space-4);
  }
  .hero-illustration {
    display: none;
  }
  .hero-content {
    padding: var(--space-6) var(--space-5) var(--space-4);
  }
  .filter-bar {
    flex-direction: column;
    align-items: stretch;
  }
  .filter-left,
  .filter-right {
    width: 100%;
  }
  .projects-grid {
    grid-template-columns: 1fr;
  }
}
</style>
