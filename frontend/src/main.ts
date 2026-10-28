/**
 * 应用入口文件
 *
 * AI 智能测试平台 - 前端应用入口
 */

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'
import ElementPlus from 'element-plus'
import 'virtual:uno.css' // ⚡ UnoCSS - 仅生成图标 CSS（i-solar-* / i-app-* / 等）
import '@/styles/element-plus.scss'
import '@/styles/tokens.scss'
import '@/styles/element-overrides.scss'
import '@/styles/workspace.scss'
import '@/styles/dialog.scss'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'

import App from './App.vue'
import router from './router'
import { setupDirectives } from '@/directives'
import '@/styles/index.scss'

// 创建应用实例
const app = createApp(App)

// 创建 Pinia 状态管理，添加持久化插件
const pinia = createPinia()
pinia.use(piniaPluginPersistedstate)

// 使用插件（需要先创建 pinia 才能初始化主题）
app.use(pinia)
app.use(router)
app.use(ElementPlus, {
  locale: zhCn,
})

// 注册全局自定义指令（v-permission 等）
setupDirectives(app)

// 初始化主题
import { useThemeStore } from '@/stores/theme'
const themeStore = useThemeStore()
themeStore.initTheme()
themeStore.watchSystemTheme()

// 注册 Element Plus 图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// 挂载应用
app.mount('#app')
