<template>
  <div class="ws-layout">
    
    <!-- 顶栏 -->
    <TopBar />

    <!-- 主体 -->
    <div class="ws-body">
      <SideBar
        :collapsed="workspaceStore.menuCollapsed"
        @toggle="workspaceStore.toggleMenu"
      />
      <main class="ws-main" :class="{ 'is-collapsed': workspaceStore.menuCollapsed }">
        <div class="ws-content">
          <router-view />
        </div>
      </main>
    </div>

    <!-- 账号仅默认「普通用户」角色(未设岗位角色,仅查看权限)时的引导弹框,引导联系管理员设置角色 -->
    <el-dialog
      v-model="showActivateDialog"
      title="账号待开通"
      width="420px"
      align-center
      append-to-body
      :close-on-click-modal="false"
      class="activate-dialog"
    >
      <div class="activate-body">
        <div class="activate-icon"><i class="i-solar-lock-keyhole-minimalistic-bold" /></div>
        <p class="activate-title">您的账号未设置角色</p>
        <p class="activate-desc">目前仅有查看权限，请联系管理员设置岗位角色以获取相关操作权限。可添加管理员微信：</p>
        <div class="activate-wechat">
          <i class="i-solar-chat-round-line-bold wechat-ic" />
          <span class="wechat-id">python771</span>
          <button type="button" class="wechat-copy" @click="copyWechat">
            <i class="i-solar-copy-linear" />复制
          </button>
        </div>
      </div>
      <template #footer>
        <el-button type="primary" @click="showActivateDialog = false">我知道了</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useWorkspaceStore } from '@/stores/workspace'
import { useUserStore } from '@/stores/user'
import TopBar from '@/components/layout/TopBar.vue'
import SideBar from '@/components/layout/SideBar.vue'

const workspaceStore = useWorkspaceStore()
const userStore = useUserStore()

// 账号未开通体验权限:角色为「普通用户 user」(自助注册默认角色)时弹框引导加管理员微信开通。
// super_admin / admin / tester 等角色不触发。
const showActivateDialog = ref(false)

// 页面刷新或直接访问时，userInfo 未持久化，需重新获取
onMounted(async () => {
  if (userStore.isLoggedIn && !userStore.userInfo) {
    await userStore.fetchUserInfo()
  }
  if (userStore.isLoggedIn && userStore.hasRole('user')) {
    showActivateDialog.value = true
  }
})

async function copyWechat() {
  try {
    await navigator.clipboard.writeText('python771')
    ElMessage.success('微信号已复制')
  } catch {
    ElMessage.warning('复制失败，请手动复制：python771')
  }
}

const watermarkCount = computed(() => {
  const rows = Math.ceil(window.innerHeight / 200) + 1
  const cols = Math.ceil(window.innerWidth / 300) + 1
  return rows * cols
})

const getWatermarkStyle = (index: number) => {
  const cols = Math.ceil(window.innerWidth / 300) + 1
  const row = Math.floor((index - 1) / cols)
  const col = (index - 1) % cols
  return {
    left: `${col * 300}px`,
    top: `${row * 200}px`,
  }
}
</script>

<style lang="scss" scoped>
/* 账号待开通引导弹框 */
.activate-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 4px 8px 8px;
}
.activate-icon {
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--brand-50);
  color: var(--brand-500);
  font-size: 30px;
  margin-bottom: 14px;
}
.activate-title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin: 0 0 6px;
}
.activate-desc {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin: 0 0 16px;
}
.activate-wechat {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: var(--bg-page);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);

  .wechat-ic { font-size: 20px; color: #07c160; } /* 微信绿,固定语义色 */
  .wechat-id {
    font-size: var(--font-size-lg);
    font-weight: var(--font-weight-semibold);
    color: var(--text-primary);
    letter-spacing: 0.5px;
    font-variant-numeric: tabular-nums;
  }
  .wechat-copy {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    margin-left: 4px;
    padding: 4px 10px;
    border: 1px solid var(--brand-200);
    background: var(--brand-50);
    color: var(--brand-600);
    border-radius: var(--radius-sm);
    font-size: var(--font-size-xs);
    cursor: pointer;
    transition: var(--transition-fast);

    &:hover { background: var(--brand-100); }
  }
}

.ws-layout {
  width: 100%;
  height: 100vh;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
  background: var(--bg-page);
}

/* 主体 */
.ws-body {
  flex: 1;
  display: flex;
  min-height: 0;
  position: relative;
  z-index: 1;
}

.ws-main {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  overflow-x: hidden;
  /* 极淡的主色径向辉光背景 - 高级感来源之一 */

  transition: background-color 0.3s;
}

.ws-content {

  min-height: 100%;
}

/* 滚动条 */
.ws-main::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
.ws-main::-webkit-scrollbar-thumb {
  background: var(--gray-300);
  border-radius: 3px;
  &:hover { background: var(--gray-400); }
}

/* 水印 */
.ws-watermark {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  overflow: hidden;
}
.ws-watermark-item {
  position: absolute;
  width: 200px;
  height: 100px;
  display: flex;
  align-items: center;
  justify-content: center;
  transform: rotate(-20deg);
  opacity: 0.06;
}
.ws-watermark-text {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  white-space: nowrap;
}

[data-theme='dark'] .ws-watermark-item {
  opacity: 0.04;
}
</style>
