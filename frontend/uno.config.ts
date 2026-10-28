/**
 * UnoCSS 配置
 *
 * 主要用途：通过 presetIcons 让 <i class="i-xxx-yyy" /> 形式的图标直接渲染
 * 不引入 Tailwind / 其他原子类，避免与 Element Plus 冲突
 */
import { defineConfig, presetIcons } from 'unocss'
import { readFileSync, readdirSync, existsSync } from 'node:fs'
import { basename, join } from 'node:path'
import { fileURLToPath } from 'node:url'

// =====================================================
// 自定义业务图标集合 - 启动时一次性读入内存
// =====================================================
const APP_ICONS_DIR = fileURLToPath(new URL('./src/assets/app-icons', import.meta.url))

const appIconMap: Record<string, string> = {}
if (existsSync(APP_ICONS_DIR)) {
  for (const file of readdirSync(APP_ICONS_DIR)) {
    if (!file.endsWith('.svg')) continue
    const name = basename(file, '.svg')
    const svg = readFileSync(join(APP_ICONS_DIR, file), 'utf-8')
    // 把根 <svg> 上的 fill="none" 去掉，强制使用 currentColor
    // 这样 mask 渲染时颜色由父元素 color 控制
    const normalized = svg
      .replace(/\sfill="none"/g, '')
      .replace(/<svg(\s+[^>]*)?>/, (_m, attrs: string | undefined) => {
        const cleanedAttrs = (attrs || '').replace(/\sfill="[^"]*"/g, '')
        return `<svg${cleanedAttrs} fill="currentColor">`
      })
    appIconMap[name] = normalized
  }
  // eslint-disable-next-line no-console
  console.log(`[uno-icons] Loaded ${Object.keys(appIconMap).length} app icons:`, Object.keys(appIconMap).join(', '))
} else {
  // eslint-disable-next-line no-console
  console.warn(`[uno-icons] App icons dir not found: ${APP_ICONS_DIR}`)
}

// safelist - 强制为所有 app 图标生成 CSS（防止 UnoCSS 静态扫描漏掉）
const APP_SAFELIST = Object.keys(appIconMap).map((n) => `i-app-${n}`)

export default defineConfig({
  presets: [
    presetIcons({
      scale: 1,
      extraProperties: {
        display: 'inline-block',
        'vertical-align': 'middle',
      },
      collections: {
        // 自定义 app 集合 - 返回 raw SVG 字符串，UnoCSS 自动处理为 mask
        // 签名：(name: string) => string | undefined
        app: (iconName: string) => appIconMap[iconName],
      },
      // 关键：自定义集合默认不在 fetch 模式下，这里给个空 customizations 让它跟内置一致
      customizations: {
        transform(svg) {
          return svg
        },
      },
    }),
  ],

  safelist: [
    ...APP_SAFELIST,
    // 侧栏 + 顶栏中用到的 Solar 图标
    'i-solar-home-2-bold-duotone',
    'i-solar-settings-bold-duotone',
    'i-solar-magic-stick-3-bold-duotone',
    'i-solar-users-group-rounded-bold-duotone',
    'i-solar-shield-user-bold-duotone',
    'i-solar-key-square-2-bold-duotone',
    'i-solar-clipboard-list-bold-duotone',
    'i-solar-user-circle-bold-duotone',
    'i-solar-folder-with-files-bold-duotone',
    'i-solar-shield-check-bold-duotone',
    'i-solar-test-tube-bold-duotone',
    'i-solar-widget-5-bold-duotone',
    // Dashboard 用的图标
    'i-solar-check-circle-bold',
    'i-solar-close-circle-bold',
    'i-solar-stars-bold',
    'i-solar-add-circle-bold',
    'i-solar-pen-bold',
    'i-solar-clock-circle-bold',
    'i-svg-spinners-ring-resize',
    // ApiCasesView
    'i-solar-trash-bin-trash-bold',
    'i-solar-trash-bin-trash-linear',
    'i-solar-magnifer-bold',
    'i-solar-refresh-linear',
    'i-solar-eye-linear',
    'i-solar-play-circle-bold',
    'i-solar-folder-bold',
    'i-solar-magic-stick-3-bold',
    // ApiDefinitionsView
    'i-solar-pause-circle-bold',
    'i-solar-pen-linear',
    'i-solar-pen-bold',
    'i-solar-list-bold',
    // 顶栏图标
    'i-solar-magnifer-linear',
    'i-solar-question-circle-linear',
    'i-solar-sun-linear',
    'i-solar-moon-linear',
    'i-solar-bell-linear',
    'i-solar-alt-arrow-left-linear',
    'i-solar-alt-arrow-right-linear',
    'i-solar-alt-arrow-down-linear',
    'i-solar-user-linear',
    'i-solar-user-bold',
    'i-solar-lock-linear',
    'i-solar-logout-2-linear',
    // 环境管理页 StatCard 图标
    'i-solar-server-bold',
    'i-solar-code-bold',
    'i-solar-monitor-bold',
    'i-solar-star-bold',
    // 环境管理页其他图标
    'i-solar-widget-2-bold',
    'i-solar-copy-linear',
    'i-solar-menu-dots-bold',
    'i-solar-add-circle-linear',
    'i-solar-upload-linear',
    'i-solar-download-linear',
    'i-solar-link-linear',
    'i-solar-settings-linear',
    'i-solar-document-text-linear',
    'i-solar-key-bold',
    'i-solar-lock-keyhole-bold',
    'i-solar-arrow-left-linear',
    'i-solar-info-circle-linear',
    'i-solar-danger-triangle-bold',
    'i-solar-check-circle-linear',
    'i-solar-maximize-square-3-linear',
    'i-solar-minimize-square-3-linear',
    'i-solar-alt-arrow-down-bold',
    'i-solar-question-circle-linear',
    'i-solar-server-2-linear',
    // OperationLogsView StatCard
    'i-solar-notebook-bold',
    'i-solar-user-speak-bold',
    'i-solar-cursor-bold',
    'i-solar-shield-warning-bold',
    // DatabasesView StatCard
    'i-solar-link-circle-bold',
    'i-solar-link-broken-bold',
    'i-solar-database-bold',
    'i-solar-database-linear',
    'i-solar-key-linear',
    'i-solar-refresh-linear',
    // DatabaseFormDialog
    'i-solar-close-circle-bold',
    'i-solar-clock-circle-linear',
    'i-solar-document-text-linear',
    'i-solar-monitor-linear',
    'i-solar-folder-open-linear',
    'i-solar-user-linear',
    'i-solar-lock-keyhole-linear',
    'i-solar-question-circle-linear',
  ],

  // 让 UnoCSS 扫描 vue / ts / tsx 文件
  content: {
    pipeline: {
      include: [
        /\.(vue|svelte|[jt]sx?|html|astro)($|\?)/,
        'src/**/*.{vue,js,ts,jsx,tsx,html}',
      ],
    },
  },
})
