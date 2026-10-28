/**
 * Vite 配置文件
 *
 * AI 智能测试平台 - 前端构建配置
 */

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import UnoCSS from 'unocss/vite'
import Icons from 'unplugin-icons/vite'
import IconsResolver from 'unplugin-icons/resolver'
import { FileSystemIconLoader } from 'unplugin-icons/loaders'
import Components from 'unplugin-vue-components/vite'
import { fileURLToPath, URL } from 'node:url'

// https://vite.dev/config/
export default defineConfig({
  // TinyH264 软解包内用 new Worker(new URL('./worker.js', import.meta.url)) 拉
  // 解码 worker——被 optimizeDeps 预打包成单文件后该相对 URL 解析到
  // .vite/deps/worker.js（不存在），worker 永不就绪 → 非 https 投屏黑屏且零报错。
  // 排除预打包让 Vite 走源码路径正确处理依赖内 worker；但它的三个 CJS 依赖
  // （yuv-buffer/yuv-canvas/tinyh264 无 ESM 导出）失去预打包的 CJS→ESM 转换
  // 会炸 default import——用嵌套 include 语法单独把它们打回去。
  optimizeDeps: {
    exclude: ['@yume-chan/scrcpy-decoder-tinyh264'],
    include: [
      '@yume-chan/scrcpy-decoder-tinyh264 > yuv-buffer',
      '@yume-chan/scrcpy-decoder-tinyh264 > yuv-canvas',
      '@yume-chan/scrcpy-decoder-tinyh264 > tinyh264',
    ],
  },
  plugins: [
    vue(),

    // ===== 图标 CSS 类系统：UnoCSS presetIcons =====
    // 让 <i class="i-solar-bug-bold" /> 形式的图标自动生成 CSS 类并渲染
    // 配置详见根目录 uno.config.ts
    UnoCSS(),

    // ===== 图标 Vue 组件系统：unplugin-icons =====
    // 同时支持 <i-solar-bug-bold /> 形式的 Vue 组件用法（在 props 里传入图标场景）
    Icons({
      compiler: 'vue3',
      autoInstall: false,
      scale: 1,
      defaultClass: 'app-icon',
      customCollections: {
        // 自定义业务图标库（FileSystemIconLoader 扫描 src/assets/app-icons/*.svg）
        // 用法：<i class="i-app-test-case" /> 对应文件 src/assets/app-icons/test-case.svg
        'app': FileSystemIconLoader(
          fileURLToPath(new URL('./src/assets/app-icons', import.meta.url)),
          (svg) => svg.replace(/^<svg /, '<svg fill="currentColor" '),
        ),
      },
    }),
    Components({
      // 仅用于自动解析 <i-xxx-yyy /> 形式的图标，不扫描业务组件目录
      dirs: [],
      dts: 'src/types/components.d.ts',
      resolvers: [
        IconsResolver({
          prefix: 'i',
          // solar/ph/tabler/lucide/svg-spinners 来自 @iconify/json
          // app 来自本地 src/assets/app-icons (自定义业务图标)
          enabledCollections: ['solar', 'ph', 'tabler', 'lucide', 'svg-spinners', 'mdi', 'app'],
          customCollections: ['app'],
        }),
      ],
    }),
  ],

  // 路径别名配置
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },

  // 开发服务器配置
  server: {
    port: 80,
    host: '0.0.0.0',
    open: true,
    // 代理配置
    proxy: {
      // AppGateway(:8889 单 worker)——浏览器投屏控制 WS。本地无 nginx 分流，
      // 按路径把 .../control/ws 手动分到网关；其余 /api 仍到业务后端 8888。
      '^/api/v1/app/devices/[^/]+/control/ws': {
        target: 'ws://127.0.0.1:8889',
        changeOrigin: true,
        ws: true,
      },
      '/api': {
        target: 'http://127.0.0.1:8888',
        changeOrigin: true,
        // 智能助手 WebSocket（/api/v1/projects/*/chat/ws/*）需要代理 WS 升级
        ws: true,
      },
      '/uploads': {
        target: 'http://127.0.0.1:8888',
        changeOrigin: true,
      },
    },
  },

  // 构建配置
  build: {
    target: 'esnext',
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,
    // 代码分割
    rollupOptions: {
      output: {
        // 手动分包
        manualChunks: {
          'vue-vendor': ['vue', 'vue-router', 'pinia'],
          'element-plus': ['element-plus'],
          'echarts': ['echarts', 'vue-echarts'],
          'editor': ['codemirror', 'vue-codemirror'],
        },
      },
    },
    minify: 'esbuild',
  },

  // CSS 配置
  css: {
    preprocessorOptions: {
      scss: {
        additionalData: `@use "@/styles/variables.scss" as *;`,
      },
    },
  },
})
