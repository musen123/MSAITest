/**
 * 全局自定义指令统一安装入口
 */
import type { App } from 'vue'
import { permission } from './permission'

export function setupDirectives(app: App): void {
  app.directive('permission', permission)
}

export { permission }
