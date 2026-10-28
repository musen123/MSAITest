<!--
  登录页面

  AI 智能测试平台 - 用户登录
  设计稿：左品牌区（4 特性 + 3D 插画）+ 右登录卡（账号密码登录 + 第三方登录）
  设计 Token：src/styles/tokens.scss
-->
<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import type { LoginRequest } from '@/types/auth'

import logoSvg from '@/assets/brand/logo.svg'
import featureCaseGenSvg from '@/assets/illustrations/feature-case-gen.svg'
import featureExecSvg from '@/assets/illustrations/feature-exec.svg'
import featureReportSvg from '@/assets/illustrations/feature-report.svg'
import featureWorkflowSvg from '@/assets/illustrations/feature-workflow.svg'
import heroSvg from '@/assets/illustrations/login-hero.svg'
import xunleiSvg from '@/assets/brand/thirdparty-xunlei.svg'
import githubSvg from '@/assets/brand/thirdparty-github.svg'
import wechatSvg from '@/assets/brand/thirdparty-wechat.svg'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

// 表单引用
const loginFormRef = ref()

// 表单数据
const loginForm = reactive<LoginRequest & { remember_me: boolean }>({
  account: '',
  password: '',
  captcha_code: '',
  captcha_key: '',
  remember_me: false,
})

const loading = ref(false)

// 表单验证规则
const formRules = {
  account: [
    { required: true, message: '请输入用户名 / 邮箱 / 手机号', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 个字符', trigger: 'blur' },
    { max: 20, message: '密码最多 20 个字符', trigger: 'blur' },
  ],
}

/**
 * 账号密码登录
 */
const handleSubmit = async () => {
  // 表单校验
  if (!loginFormRef.value) return
  try {
    await loginFormRef.value.validate()
  } catch {
    return // 校验失败，el-form 已自动展示错误
  }

  try {
    loading.value = true
    const success = await userStore.login({
      account: loginForm.account,
      password: loginForm.password,
      remember_me: loginForm.remember_me,
    })

    if (success) {
      const redirect = route.query.redirect as string
      if (redirect) {
        router.push(redirect)
      } else {
        // 每次登录都先展示欢迎页
        router.push('/welcome')
      }
    }
  } catch (error) {
    console.error('登录失败:', error)
  } finally {
    loading.value = false
  }
}

/**
 * 跳转到注册页
 */
const goToRegister = () => {
  router.push('/register')
}

/**
 * 第三方登录（占位）
 */
const handleThirdPartyLogin = (provider: string) => {
  ElMessage.info(`${provider} 登录功能暂时未开放！`)
}

// ==================== 静态数据 ====================

const features = [
  { icon: featureCaseGenSvg, title: '智能生成用例', desc: 'AI 自动化生成测试用例' },
  { icon: featureExecSvg,    title: '自动化执行',   desc: '支持多环境并行执行' },
  { icon: featureReportSvg,  title: '智能分析报告', desc: 'AI 深度分析测试结果' },
  { icon: featureWorkflowSvg,title: '可视化工作流', desc: '拖拽式编排测试流程' },
]

const thirdParties = [
  { icon: wechatSvg,  label: '微信' },
]
</script>

<template>
  <div class="login-page">
    <!-- 浅色背景（设计稿风格） -->
    <div class="bg-gradient" />
    <div class="bg-blob bg-blob-1" />
    <div class="bg-blob bg-blob-2" />

    <div class="login-shell">
      <!-- ==================== 左侧：品牌区 ==================== -->
      <section class="brand-section">
        <!-- 顶部 Logo + 标签 + 语言 -->
        <header class="brand-header">
          <div class="brand-logo">
            <img :src="logoSvg" alt="Logo" class="logo-icon" />
            <span class="logo-text">MSAITest</span>
            <span class="logo-badge">AI 测试平台</span>
          </div>
         
        </header>

        <!-- 文案区 -->
        <div class="brand-hero">
          <h1 class="hero-title">
            智能测试，<span class="hero-highlight">提效每一刻</span>
          </h1>
          <p class="hero-subtitle">AI 驱动的测试平台，让测试更智能高效</p>
        </div>

        <!-- 4 列特性 -->
        <div class="feature-row">
          <div v-for="f in features" :key="f.title" class="feature-cell">
            <img :src="f.icon" :alt="f.title" class="feature-icon" />
            <h4 class="feature-title">{{ f.title }}</h4>
            <p class="feature-desc">{{ f.desc }}</p>
          </div>
        </div>

        <!-- 主插画（设计系统 login-hero.svg） -->
        <div class="hero-illustration">
          <img :src="heroSvg" alt="平台插画" />
        </div>
      </section>

      <!-- ==================== 右侧：登录卡 ==================== -->
      <section class="auth-section">
        <div class="auth-card">
          <header class="auth-header">
            <h2 class="auth-title">欢迎登录</h2>
            <p class="auth-subtitle">登录您的 MSAITest Platform 账户</p>
          </header>

          <el-form
            ref="loginFormRef"
            :model="loginForm"
            :rules="formRules"
            class="auth-form"
            hide-required-asterisk
            @submit.prevent="handleSubmit"
          >
            <el-form-item prop="account">
              <el-input
                v-model="loginForm.account"
                size="large"
                clearable
                placeholder="请输入用户名 / 邮箱 / 手机号"
                :prefix-icon="User"
              />
            </el-form-item>

            <el-form-item prop="password">
              <el-input
                v-model="loginForm.password"
                type="password"
                size="large"
                show-password
                clearable
                placeholder="请输入密码"
                :prefix-icon="Lock"
                @keyup.enter="handleSubmit"
              />
            </el-form-item>

            <!-- 记住我 + 忘记密码 -->
            <div class="form-options">
              <el-checkbox v-model="loginForm.remember_me">记住我</el-checkbox>
              <el-link type="primary" :underline="false" class="link-brand">
                忘记密码？
              </el-link>
            </div>

            <!-- 主登录按钮 -->
            <el-button
              type="primary"
              size="large"
              :loading="loading"
              class="auth-submit"
              native-type="submit"
              @click="handleSubmit"
            >
              {{ loading ? '登录中...' : '登 录' }}
            </el-button>
          </el-form>

          <!-- 其他登录方式 -->
          <div class="divider">
            <span class="divider-line" />
            <span class="divider-text">其他登录方式</span>
            <span class="divider-line" />
          </div>

          <div class="third-party-row">
            <button
              v-for="tp in thirdParties"
              :key="tp.label"
              class="tp-btn"
              :title="tp.label"
              @click="handleThirdPartyLogin(tp.label)"
            >
              <img :src="tp.icon" :alt="tp.label" class="tp-icon" />
            </button>
          </div>

          <!-- 注册引导 -->
          <div class="auth-footer">
            还没有账户？
            <el-link type="primary" :underline="false" class="link-brand" @click="goToRegister">
              立即注册
            </el-link>
          </div>

        </div>
      </section>
    </div>

    <!-- ==================== 页面底部 ==================== -->
    <footer class="page-footer">
      <span>© 2026 MuSen AI AutoTest Platform. All rights reserved.</span>
      <span class="footer-sep">·</span>
      <el-link :underline="false" class="footer-link">隐私政策</el-link>
      <el-link :underline="false" class="footer-link">服务条款</el-link>
    </footer>
  </div>
</template>

<style scoped lang="scss">
// ==================== 页面容器 ====================
.login-page {
  position: relative;
  width: 100%;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-page, #F8FAFC);
  overflow: hidden;
  isolation: isolate;
}

.bg-gradient {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    135deg,
    var(--brand-glow-faint) 0%,
    transparent 50%,
    rgba(59, 130, 246, 0.04) 100%
  );
  z-index: 0;
}

.bg-blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.55;
  z-index: 0;
  pointer-events: none;
}
.bg-blob-1 {
  width: 480px; height: 480px;
  background: var(--brand-100);
  top: -120px; left: -120px;
}
.bg-blob-2 {
  width: 380px; height: 380px;
  background: rgba(59, 130, 246, 0.10);
  bottom: -100px; right: 20%;
}

.login-shell {
  flex: 1;
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 0;
  width: 100%;
  max-width: 1440px;
  margin: 0 auto;
  padding: 0 var(--space-10);
  z-index: 1;
}

// ==================== 左侧品牌区 ====================
.brand-section {
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  padding: var(--space-10) var(--space-12) var(--space-6);
  gap: var(--space-8);
}

// 顶部
.brand-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.brand-logo {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.logo-icon {
  width: 36px; height: 36px;
  filter: drop-shadow(0 4px 12px rgba(34, 197, 94, 0.25));
}
.logo-text {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.3px;
}
.logo-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  font-size: 12px;
  font-weight: 500;
  color: var(--brand-700);
  background: var(--brand-50);
  border: 1px solid var(--brand-200);
  border-radius: var(--radius-full);
}

.lang-trigger {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: 14px;
  color: var(--text-secondary);
  cursor: pointer;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  transition: background var(--transition-base);
  &:hover { background: var(--gray-100); }
}

// 文案
.brand-hero {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  margin-top: var(--space-4);
}
.hero-title {
  font-size: 40px;
  font-weight: 700;
  line-height: 1.25;
  color: var(--text-primary);
  letter-spacing: -1px;
  margin: 0;
}
.hero-highlight {
  color: var(--brand-500);
  position: relative;
  &::after {
    content: '';
    position: absolute;
    left: 0; right: 0; bottom: -4px;
    height: 6px;
    background: var(--brand-100);
    border-radius: var(--radius-xs);
    z-index: -1;
  }
}
.hero-subtitle {
  font-size: 16px;
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.6;
}

.hero-course-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-top: 22px;
  padding: 12px 26px;
  border-radius: 999px;
  background: linear-gradient(135deg, #34d399, #10b981);
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  text-decoration: none;
  box-shadow: 0 8px 24px rgba(16, 185, 129, 0.32);
  transition: transform 0.18s ease, box-shadow 0.18s ease;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 12px 32px rgba(16, 185, 129, 0.45);
  }
}

// 4 列特性
.feature-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-4);
}
.feature-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-2);
}
.feature-icon {
  width: 32px; height: 32px;
  border-radius: var(--radius-md);
}
.feature-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}
.feature-desc {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.5;
}

// 3D 插画
.hero-illustration {
  display: flex;
  justify-content: center;
  align-items: center;
  margin-top: var(--space-4);
  img {
    width: 100%;
    max-width: 600px;
    height: auto;
  }
}

// ==================== 右侧登录卡 ====================
.auth-section {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-10) 0;
}

.auth-card {
  width: 100%;
  max-width: 420px;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-xl);
  padding: var(--space-10);
  box-shadow:
    0 4px 6px -1px rgba(15, 23, 42, 0.04),
    0 10px 30px -5px rgba(15, 23, 42, 0.08),
    0 25px 50px -12px rgba(15, 23, 42, 0.10);
  animation: cardIn 0.45s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes cardIn {
  from { opacity: 0; transform: translateY(12px); }
  to   { opacity: 1; transform: translateY(0); }
}

.auth-header {
  margin-bottom: var(--space-6);
}
.auth-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 var(--space-2);
  letter-spacing: -0.5px;
}
.auth-subtitle {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0;
}

// ==================== 表单 ====================
.auth-form {
  :deep(.el-form-item) { margin-bottom: var(--space-4); }
  :deep(.el-input__wrapper) {
    border-radius: var(--radius-md);
    padding: 4px 12px;
    box-shadow: 0 0 0 1px var(--border-color) inset;
    transition: all var(--transition-base);
    &:hover { box-shadow: 0 0 0 1px var(--brand-300) inset; }
    &.is-focus { box-shadow: 0 0 0 1px var(--brand-500) inset, 0 0 0 3px var(--brand-glow-soft); }
  }
  :deep(.el-input__inner) {
    height: 38px;
    font-size: 14px;
    color: var(--text-primary);
    &::placeholder { color: var(--text-placeholder); }
  }
  :deep(.el-input__prefix .el-icon) {
    color: var(--text-placeholder);
  }

  // 修复浏览器自动填充时的黄底（WebKit 私有伪类）
  // 用 inset box-shadow 覆盖浏览器内置 background
  :deep(.el-input__inner:-webkit-autofill),
  :deep(.el-input__inner:-webkit-autofill:hover),
  :deep(.el-input__inner:-webkit-autofill:focus),
  :deep(.el-input__inner:-internal-autofill-selected) {
    -webkit-box-shadow: 0 0 0 1000px var(--bg-card) inset !important;
    -webkit-text-fill-color: var(--text-primary) !important;
    caret-color: var(--text-primary);
    transition: background-color 5000s ease-in-out 0s;
  }
}

// ==================== 表单选项 ====================
.form-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-5);
  :deep(.el-checkbox__label) { color: var(--text-secondary); font-size: 13px; }
  :deep(.el-checkbox__input.is-checked .el-checkbox__inner) {
    background: var(--brand-500);
    border-color: var(--brand-500);
  }
  :deep(.el-checkbox__input.is-checked + .el-checkbox__label) { color: var(--text-primary); }
}

.link-brand {
  color: var(--brand-600) !important;
  font-size: 13px;
  font-weight: 500;
  &:hover { color: var(--brand-700) !important; }
}

// ==================== 主登录按钮 ====================
.auth-submit {
  width: 100%;
  height: 44px;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 4px;
  border-radius: var(--radius-md);
  background: var(--brand-500);
  border-color: var(--brand-500);
  box-shadow: 0 6px 16px -4px var(--brand-glow-strong);
  transition: all var(--transition-base);
  &:hover:not(:disabled) {
    background: var(--brand-600);
    border-color: var(--brand-600);
    transform: translateY(-1px);
    box-shadow: 0 8px 20px -4px var(--brand-glow-strong);
  }
  &:active:not(:disabled) { transform: translateY(0); }
}

// ==================== 分隔线 ====================
.divider {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin: var(--space-6) 0;
}
.divider-line {
  flex: 1;
  height: 1px;
  background: var(--border-light);
}
.divider-text {
  font-size: 12px;
  color: var(--text-placeholder);
}

// ==================== 第三方登录 ====================
.third-party-row {
  display: flex;
  justify-content: center;
  gap: var(--space-5);
  margin-bottom: var(--space-6);
}
.tp-btn {
  width: 44px; height: 44px;
  border-radius: 50%;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all var(--transition-base);
  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 12px -2px rgba(15, 23, 42, 0.10);
    border-color: var(--brand-300);
  }
}
.tp-icon {
  width: 24px; height: 24px;
  border-radius: 50%;
}

// ==================== 注册引导 ====================
.auth-footer {
  text-align: center;
  font-size: 13px;
  color: var(--text-secondary);
  padding-top: var(--space-4);
  border-top: 1px solid var(--border-light);
}

// ==================== 页面底部 ====================
.page-footer {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  padding: var(--space-5) var(--space-6);
  font-size: 12px;
  color: var(--text-placeholder);
}
.footer-sep { color: var(--text-disabled); }
.footer-link {
  color: var(--text-secondary) !important;
  font-size: 12px !important;
  &:hover { color: var(--brand-600) !important; }
}

// ==================== 响应式 ====================
@media (max-width: 1100px) {
  .login-shell { grid-template-columns: 1fr; padding: 0 var(--space-6); }
  .brand-section { padding: var(--space-6); }
  .hero-title { font-size: 32px; }
  .hero-illustration { display: none; }
  .feature-row { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 768px) {
  .auth-card { padding: var(--space-6); }
  .hero-title { font-size: 28px; }
  .lang-switch { display: none; }
}
@media (max-width: 480px) {
  .feature-row { grid-template-columns: 1fr; }
  .third-party-row { gap: var(--space-3); }
}
</style>
