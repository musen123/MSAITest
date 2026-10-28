/**
 * 主题状态管理
 *
 * AI 智能测试平台 - 主题切换
 * 管理亮色/暗色模式切换
 */

import { ref, watch } from 'vue'
import { defineStore } from 'pinia'

export type ThemeMode = 'light' | 'dark'

export const useThemeStore = defineStore(
  'theme',
  () => {
    /**
     * 当前主题模式
     */
    const themeMode = ref<ThemeMode>('light')

    /**
     * 是否为暗色模式
     */
    const isDark = ref(false)

    /**
     * 初始化主题
     */
    const initTheme = () => {
      // 从 localStorage 读取保存的主题
      const savedTheme = localStorage.getItem('ai-test-platform-theme') as ThemeMode | null

      if (savedTheme) {
        themeMode.value = savedTheme
      } else {
        // 检测系统主题偏好
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
        themeMode.value = prefersDark ? 'dark' : 'light'
      }

      applyTheme()
    }

    /**
     * 应用主题到 DOM
     */
    const applyTheme = () => {
      const root = document.documentElement

      if (themeMode.value === 'dark') {
        root.setAttribute('data-theme', 'dark')
        isDark.value = true
      } else {
        root.setAttribute('data-theme', 'light')
        isDark.value = false
      }

      // 保存到 localStorage
      localStorage.setItem('ai-test-platform-theme', themeMode.value)
    }

    /**
     * 切换主题
     */
    const toggleTheme = () => {
      themeMode.value = themeMode.value === 'light' ? 'dark' : 'light'
      applyTheme()
    }

    /**
     * 设置主题模式
     */
    const setTheme = (mode: ThemeMode) => {
      themeMode.value = mode
      applyTheme()
    }

    /**
     * 监听系统主题变化
     */
    const watchSystemTheme = () => {
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')

      const handleChange = (e: MediaQueryListEvent) => {
        // 只有在用户没有手动设置主题时才跟随系统
        const savedTheme = localStorage.getItem('ai-test-platform-theme')
        if (!savedTheme) {
          themeMode.value = e.matches ? 'dark' : 'light'
          applyTheme()
        }
      }

      // 使用新API监听（如果支持）
      if (mediaQuery.addEventListener) {
        mediaQuery.addEventListener('change', handleChange)
      } else {
        // 兼容旧API
        mediaQuery.addListener(handleChange)
      }
    }

    // 监听主题变化
    watch(themeMode, () => {
      applyTheme()
    })

    return {
      themeMode,
      isDark,
      initTheme,
      toggleTheme,
      setTheme,
      watchSystemTheme,
    }
  },
  {
    persist: {
      key: 'ai-test-platform-theme',
      storage: localStorage,
    },
  }
)
