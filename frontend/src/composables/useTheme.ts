import { ref, watch } from 'vue'

export type Theme = 'dark' | 'light'

const STORAGE_KEY = 'app-theme'

/** 全局单例：在模块加载时即初始化，保证首屏不闪烁 */
const themeRef = ref<Theme>('dark')

const applyTheme = (t: Theme) => {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  // 我们自己的主题变量
  root.setAttribute('data-theme', t)
  // Element Plus 暗黑模式开关：html.dark
  root.classList.toggle('dark', t === 'dark')
}

// IIFE 同步初始化（在浏览器环境下）
;(() => {
  if (typeof window === 'undefined') return
  const saved = localStorage.getItem(STORAGE_KEY) as Theme | null
  const initial: Theme = saved === 'light' || saved === 'dark' ? saved : 'dark'
  themeRef.value = initial
  applyTheme(initial)
})()

/** 在 main.ts 里调用一次，确保 DOM 就绪后 data-theme 也设置好 */
export const initTheme = () => {
  applyTheme(themeRef.value)
}

/** 在组件里使用：返回响应式 theme + toggle */
export const useTheme = () => {
  const toggle = () => {
    themeRef.value = themeRef.value === 'dark' ? 'light' : 'dark'
  }

  watch(themeRef, (val) => {
    applyTheme(val)
    localStorage.setItem(STORAGE_KEY, val)
  })

  return {
    theme: themeRef,
    toggle,
    setTheme: (t: Theme) => { themeRef.value = t },
  }
}
