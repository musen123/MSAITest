<!--
  注册页面

  AI 智能测试平台 - 用户注册
  视觉与 LoginView 对齐：浅色现代企业级，左右两栏
-->
<script setup lang="ts">
import { reactive, ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock, Message, Phone, Picture, ChatLineRound } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { authApi } from '@/api/auth'
import type { RegisterRequest } from '@/types/auth'

import logoSvg from '@/assets/brand/logo.svg'
import featureCaseGenSvg from '@/assets/illustrations/feature-case-gen.svg'
import featureExecSvg from '@/assets/illustrations/feature-exec.svg'
import featureReportSvg from '@/assets/illustrations/feature-report.svg'
import featureWorkflowSvg from '@/assets/illustrations/feature-workflow.svg'
import heroSvg from '@/assets/illustrations/login-hero.svg'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

// 表单引用
const registerFormRef = ref()

// 表单数据
const registerForm = reactive<RegisterRequest & { confirm_password: string }>({
  username: '',
  password: '',
  email: '',
  phone: '',
  real_name: '',
  captcha_code: '',
  captcha_key: '',
  confirm_password: '',
})

// 加载状态
const submitting = ref(false)

// 验证码
const captchaImage = ref('')
const captchaLoading = ref(false)

// 密码强度
const passwordStrength = ref<'weak' | 'medium' | 'strong' | ''>('')

// 协议勾选
const agreed = ref(false)

// ============ 品牌区特性数据（与登录页呼应，主题为注册场景） ============
const features = [
  { icon: featureCaseGenSvg, title: 'AI 智能用例', desc: '需求即用例' },
  { icon: featureExecSvg, title: '一键自动化', desc: '告别重复劳动' },
  { icon: featureReportSvg, title: '可视化报告', desc: '缺陷一目了然' },
  { icon: featureWorkflowSvg, title: '业务流编排', desc: '场景灵活组合' },
]

// 表单验证规则
const formRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 4, max: 20, message: '用户名为 4-20 个字符', trigger: 'blur' },
    {
      pattern: /^[a-zA-Z0-9_]+$/,
      message: '用户名只能包含字母、数字、下划线',
      trigger: 'blur',
    },
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, max: 20, message: '密码为 8-20 个字符', trigger: 'blur' },
    {
      pattern: /^(?=.*[A-Za-z])(?=.*\d).+$/,
      message: '密码必须包含字母和数字',
      trigger: 'blur',
    },
  ],
  confirm_password: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_rule: any, value: string, callback: any) => {
        if (value !== registerForm.password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
  phone: [
    {
      pattern: /^1[3-9]\d{9}$/,
      message: '请输入正确的手机号',
      trigger: 'blur',
    },
  ],
  captcha_code: [
    { required: true, message: '请输入验证码', trigger: 'blur' },
    { len: 4, message: '验证码为 4 位', trigger: 'blur' },
  ],
}

// 提交按钮禁用条件
const submitDisabled = computed(() => !agreed.value || submitting.value)

/**
 * 获取验证码
 */
const fetchCaptcha = async () => {
  captchaLoading.value = true
  try {
    const res = await authApi.getCaptcha()
    if (res.code === 200) {
      captchaImage.value = res.data.captcha_image
      registerForm.captcha_key = res.data.captcha_key
    }
  } catch (error) {
    console.error('获取验证码失败:', error)
  } finally {
    captchaLoading.value = false
  }
}

/**
 * 刷新验证码
 */
const refreshCaptcha = () => {
  registerForm.captcha_code = ''
  fetchCaptcha()
}

/**
 * 检查密码强度
 */
const checkPasswordStrength = () => {
  const password = registerForm.password
  if (!password) {
    passwordStrength.value = ''
    return
  }

  let strength = 0
  if (password.length >= 8) strength++
  if (password.length >= 12) strength++
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) strength++
  if (/\d/.test(password)) strength++
  if (/[^a-zA-Z0-9]/.test(password)) strength++

  if (strength <= 2) passwordStrength.value = 'weak'
  else if (strength <= 3) passwordStrength.value = 'medium'
  else passwordStrength.value = 'strong'
}

// 密码强度描述
const strengthLabel = computed(() => {
  if (passwordStrength.value === 'weak') return '弱'
  if (passwordStrength.value === 'medium') return '中'
  if (passwordStrength.value === 'strong') return '强'
  return ''
})

/**
 * 注册处理
 */
const handleRegister = async () => {
  if (!registerFormRef.value) return

  try {
    await registerFormRef.value.validate()
  } catch {
    return
  }

  if (!agreed.value) {
    ElMessage.warning('请先阅读并同意用户协议与隐私政策')
    return
  }

  submitting.value = true
  try {
    const success = await userStore.register({
      username: registerForm.username,
      password: registerForm.password,
      email: registerForm.email,
      phone: registerForm.phone || undefined,
      real_name: registerForm.real_name || undefined,
      captcha_code: registerForm.captcha_code,
      captcha_key: registerForm.captcha_key,
    })

    if (success) {
      if (userStore.isLoggedIn) {
        // 后端注册即返回登录态
        ElMessage.success('注册成功')
        const redirect = (route.query.redirect as string) || '/welcome'
        router.push(redirect)
      } else {
        // 注册成功后静默自动登录，全程只弹一条提示
        const loginSuccess = await userStore.login(
          {
            account: registerForm.username,
            password: registerForm.password,
            captcha_code: '',
            captcha_key: '',
            remember_me: false,
          },
          { silent: true },
        )

        if (loginSuccess) {
          ElMessage.success('注册成功')
          router.push('/welcome')
        } else {
          ElMessage.success('注册成功，请登录')
          router.push('/login')
        }
      }
    } else {
      refreshCaptcha()
    }
  } catch (error) {
    console.error('注册失败:', error)
    refreshCaptcha()
  } finally {
    submitting.value = false
  }
}

/**
 * 跳转到登录页
 */
const goToLogin = () => {
  router.push('/login')
}

onMounted(() => {
  fetchCaptcha()
})
</script>

<template>
  <div class="register-page">
    <!-- 背景渐变 -->
    <div class="bg-gradient" />
    <div class="bg-blob bg-blob-1" />
    <div class="bg-blob bg-blob-2" />

    <div class="register-shell">
      <!-- ==================== 左侧品牌区 ==================== -->
      <section class="brand-section">
        <div class="brand-header">
          <div class="brand-logo">
            <img :src="logoSvg" alt="logo" class="logo-icon" />
            <span class="logo-text">AI 智能测试平台</span>
            <span class="logo-badge">v2.4.0</span>
          </div>
        </div>

        <div class="brand-hero">
          <h1 class="hero-title">
            开启
            <span class="hero-highlight">智能测试</span>
            新体验
          </h1>
          <p class="hero-subtitle">
            10 大核心模块覆盖测试全流程，从用例生成到报告分析，让 AI 成为你的测试伙伴
          </p>
        </div>

        <!-- 4 列特性 -->
        <div class="feature-row">
          <div v-for="(f, idx) in features" :key="idx" class="feature-cell">
            <img :src="f.icon" :alt="f.title" class="feature-icon" />
            <h4 class="feature-title">{{ f.title }}</h4>
            <p class="feature-desc">{{ f.desc }}</p>
          </div>
        </div>

        <!-- 主插画 -->
        <div class="hero-illustration">
          <img :src="heroSvg" alt="平台插画" />
        </div>
      </section>

      <!-- ==================== 右侧：注册卡 ==================== -->
      <section class="auth-section">
        <div class="auth-card">
          <header class="auth-header">
            <h2 class="auth-title">创建账号</h2>
            <p class="auth-subtitle">填写信息，立即开启智能测试之旅</p>
          </header>

          <el-form
            ref="registerFormRef"
            :model="registerForm"
            :rules="formRules"
            class="auth-form"
            hide-required-asterisk
            @submit.prevent="handleRegister"
          >
            <el-form-item prop="username">
              <el-input
                v-model="registerForm.username"
                size="large"
                clearable
                placeholder="请输入用户名（4-20 位字母/数字/下划线）"
                :prefix-icon="User"
              />
            </el-form-item>

            <el-form-item prop="email">
              <el-input
                v-model="registerForm.email"
                size="large"
                clearable
                placeholder="请输入邮箱"
                :prefix-icon="Message"
              />
            </el-form-item>

            <el-form-item prop="password">
              <el-input
                v-model="registerForm.password"
                type="password"
                size="large"
                show-password
                clearable
                placeholder="请输入密码（8-20 位，含字母和数字）"
                :prefix-icon="Lock"
                @input="checkPasswordStrength"
              />
            </el-form-item>

            <!-- 密码强度 -->
            <div v-if="registerForm.password" class="password-strength">
              <span class="strength-label">密码强度：</span>
              <div class="strength-bar">
                <div
                  class="strength-fill"
                  :class="passwordStrength"
                  :style="{
                    width:
                      passwordStrength === 'weak'
                        ? '33%'
                        : passwordStrength === 'medium'
                          ? '66%'
                          : '100%',
                  }"
                />
              </div>
              <span class="strength-text" :class="passwordStrength">{{ strengthLabel }}</span>
            </div>

            <el-form-item prop="confirm_password">
              <el-input
                v-model="registerForm.confirm_password"
                type="password"
                size="large"
                show-password
                clearable
                placeholder="请再次输入密码"
                :prefix-icon="Lock"
              />
            </el-form-item>

            <el-form-item prop="phone">
              <el-input
                v-model="registerForm.phone"
                size="large"
                clearable
                placeholder="请输入手机号（可选）"
                :prefix-icon="Phone"
                maxlength="11"
              />
            </el-form-item>

            <el-form-item prop="real_name">
              <el-input
                v-model="registerForm.real_name"
                size="large"
                clearable
                placeholder="请输入真实姓名（可选）"
                :prefix-icon="ChatLineRound"
              />
            </el-form-item>

            <el-form-item prop="captcha_code">
              <div class="captcha-row">
                <el-input
                  v-model="registerForm.captcha_code"
                  size="large"
                  clearable
                  maxlength="4"
                  placeholder="请输入图形验证码"
                  :prefix-icon="Picture"
                  class="captcha-input"
                />
                <div
                  class="captcha-image-wrapper"
                  :class="{ loading: captchaLoading }"
                  @click="refreshCaptcha"
                >
                  <img
                    v-if="captchaImage"
                    :src="captchaImage"
                    alt="验证码"
                    class="captcha-image"
                  />
                  <span v-else class="captcha-placeholder">点击刷新</span>
                </div>
              </div>
            </el-form-item>

            <!-- 协议勾选 -->
            <div class="agreement-row">
              <el-checkbox v-model="agreed">
                我已阅读并同意
                <el-link type="primary" :underline="false" class="link-brand">《用户协议》</el-link>
                与
                <el-link type="primary" :underline="false" class="link-brand">《隐私政策》</el-link>
              </el-checkbox>
            </div>

            <el-button
              type="primary"
              size="large"
              :loading="submitting"
              :disabled="submitDisabled"
              class="auth-submit"
              native-type="submit"
              @click="handleRegister"
            >
              {{ submitting ? '注册中...' : '注 册' }}
            </el-button>
          </el-form>

          <!-- 已有账号 -->
          <div class="auth-footer">
            已有账号？
            <el-link type="primary" :underline="false" class="link-brand" @click="goToLogin">
              立即登录
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
.register-page {
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
  width: 480px;
  height: 480px;
  background: var(--brand-100);
  top: -120px;
  left: -120px;
}
.bg-blob-2 {
  width: 380px;
  height: 380px;
  background: rgba(59, 130, 246, 0.10);
  bottom: -100px;
  right: 20%;
}

.register-shell {
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
  width: 36px;
  height: 36px;
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
    left: 0;
    right: 0;
    bottom: -4px;
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
  width: 36px;
  height: 36px;
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

// ==================== 右侧注册卡 ====================
.auth-section {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-10) 0;
}

.auth-card {
  width: 100%;
  max-width: 460px;
  max-height: calc(100vh - var(--space-12));
  overflow-y: auto;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-xl);
  padding: var(--space-8);
  box-shadow:
    0 4px 6px -1px rgba(15, 23, 42, 0.04),
    0 10px 30px -5px rgba(15, 23, 42, 0.08),
    0 25px 50px -12px rgba(15, 23, 42, 0.10);
  animation: cardIn 0.45s cubic-bezier(0.16, 1, 0.3, 1);

  &::-webkit-scrollbar {
    width: 6px;
  }
  &::-webkit-scrollbar-track {
    background: transparent;
  }
  &::-webkit-scrollbar-thumb {
    background: var(--gray-200);
    border-radius: 3px;
    &:hover {
      background: var(--gray-300);
    }
  }
}

@keyframes cardIn {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.auth-header {
  margin-bottom: var(--space-5);
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
  :deep(.el-form-item) {
    margin-bottom: var(--space-4);
  }
  :deep(.el-input__wrapper) {
    border-radius: var(--radius-md);
    padding: 4px 12px;
    box-shadow: 0 0 0 1px var(--border-color) inset;
    transition: all var(--transition-base);
    &:hover {
      box-shadow: 0 0 0 1px var(--brand-300) inset;
    }
    &.is-focus {
      box-shadow: 0 0 0 1px var(--brand-500) inset, 0 0 0 3px var(--brand-glow-soft);
    }
  }
  :deep(.el-input__inner) {
    height: 38px;
    font-size: 14px;
    color: var(--text-primary);
    &::placeholder {
      color: var(--text-placeholder);
    }
  }
  :deep(.el-input__prefix .el-icon) {
    color: var(--text-placeholder);
  }

  // 修复浏览器自动填充时的黄底
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

// ==================== 密码强度 ====================
.password-strength {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin: calc(var(--space-2) * -1) 0 var(--space-3);
  font-size: 12px;
}
.strength-label {
  color: var(--text-secondary);
  white-space: nowrap;
}
.strength-bar {
  flex: 1;
  height: 4px;
  background: var(--gray-100);
  border-radius: var(--radius-full);
  overflow: hidden;
}
.strength-fill {
  height: 100%;
  border-radius: var(--radius-full);
  transition: all 0.3s;

  &.weak {
    background: var(--el-color-danger);
  }
  &.medium {
    background: var(--el-color-warning);
  }
  &.strong {
    background: var(--el-color-success);
  }
}
.strength-text {
  font-weight: 600;
  min-width: 16px;
  text-align: right;

  &.weak {
    color: var(--el-color-danger);
  }
  &.medium {
    color: var(--el-color-warning);
  }
  &.strong {
    color: var(--el-color-success);
  }
}

// ==================== 验证码 ====================
.captcha-row {
  display: flex;
  gap: var(--space-2);
  width: 100%;
}
.captcha-input {
  flex: 1;
}
.captcha-image-wrapper {
  flex-shrink: 0;
  width: 110px;
  height: 40px;
  border-radius: var(--radius-md);
  overflow: hidden;
  border: 1px solid var(--border-color);
  cursor: pointer;
  transition: all var(--transition-base);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--gray-50);

  &:hover {
    border-color: var(--brand-300);
    box-shadow: 0 0 0 3px var(--brand-glow-soft);
  }
}
.captcha-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.captcha-placeholder {
  font-size: 12px;
  color: var(--text-placeholder);
}

// ==================== 协议 ====================
.agreement-row {
  margin-bottom: var(--space-5);
  :deep(.el-checkbox__label) {
    color: var(--text-secondary);
    font-size: 12px;
    line-height: 1.5;
  }
  :deep(.el-checkbox__input.is-checked .el-checkbox__inner) {
    background: var(--brand-500);
    border-color: var(--brand-500);
  }
}

.link-brand {
  color: var(--brand-600) !important;
  font-size: 12px;
  font-weight: 500;
  &:hover {
    color: var(--brand-700) !important;
  }
}

// ==================== 主注册按钮 ====================
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
  &:active:not(:disabled) {
    transform: translateY(0);
  }
}

// ==================== 底部 ====================
.auth-footer {
  text-align: center;
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: var(--space-5);
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
.footer-sep {
  color: var(--text-disabled);
}
.footer-link {
  color: var(--text-secondary) !important;
  font-size: 12px !important;
  &:hover {
    color: var(--brand-600) !important;
  }
}

// ==================== 响应式 ====================
@media (max-width: 1100px) {
  .register-shell {
    grid-template-columns: 1fr;
    padding: 0 var(--space-6);
  }
  .brand-section {
    padding: var(--space-6);
  }
  .hero-title {
    font-size: 32px;
  }
  .hero-illustration {
    display: none;
  }
  .feature-row {
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (max-width: 768px) {
  .auth-card {
    padding: var(--space-6);
  }
  .hero-title {
    font-size: 28px;
  }
}
@media (max-width: 480px) {
  .feature-row {
    grid-template-columns: 1fr;
  }
}
</style>