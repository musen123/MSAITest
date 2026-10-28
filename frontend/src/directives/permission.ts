/**
 * v-permission 权限指令
 *
 * 与后端 `require_permission` 同口径的前端「软」门控。
 * ⚠ 这只是 UX 层：真正的访问控制在后端，前端隐藏按钮 ≠ 安全边界。
 *
 * 用法：
 *   v-permission="'scheduler:create'"            无该权限 → 移除元素
 *   v-permission="['scheduler:edit', '...']"     满足其一即可（OR）
 *   v-permission.every="['a', 'b']"              需同时具备（AND）
 *   v-permission.disable="'scheduler:execute'"   无权限不移除，改为禁用（灰化 + 拦截交互）
 *
 * 适用边界：
 *   ✅ 按钮、链接、操作项等「叶子交互元素」—— 用本指令（移除/禁用）。
 *   ⚠ el-menu-item / el-tab-pane 等需被父组件实例收集的结构性元素请改用 v-if，
 *      指令直接操作 DOM 会绕过 Vue 组件树，导致父组件登记与真实 DOM 不一致。
 */
import type { Directive, DirectiveBinding } from 'vue'
import { useUserStore } from '@/stores/user'

type PermValue = string | string[]

/**
 * 判断当前用户是否满足指令声明的权限。
 * super_admin 在后端被授予全部权限点，其 permissions 已含所有码，无需特判。
 */
function allowed(value: PermValue, every: boolean): boolean {
  const codes = (Array.isArray(value) ? value : [value]).filter(Boolean)
  if (codes.length === 0) return true
  const userStore = useUserStore()
  return every
    ? userStore.hasAllPermissions(...codes)
    : userStore.hasAnyPermission(...codes)
}

// —— .disable 修饰符：禁用而非移除 ——
// Element Plus 组件的 disabled 是 prop（非 DOM attribute），setAttribute 不生效，
// 故用「捕获阶段吞掉交互事件 + 视觉灰化」实现通用禁用，兼容原生与 EP 组件。
const BLOCK_EVENTS = ['click', 'mousedown', 'keydown'] as const

function blocker(e: Event): void {
  e.stopImmediatePropagation()
  e.preventDefault()
}

interface PermEl extends HTMLElement {
  __permDisabled__?: boolean
}

function disableEl(el: PermEl): void {
  if (el.__permDisabled__) return
  el.__permDisabled__ = true
  el.style.opacity = '0.5'
  el.style.cursor = 'not-allowed'
  el.setAttribute('aria-disabled', 'true')
  BLOCK_EVENTS.forEach((ev) => el.addEventListener(ev, blocker, true))
}

function enableEl(el: PermEl): void {
  if (!el.__permDisabled__) return
  el.__permDisabled__ = false
  el.style.opacity = ''
  el.style.cursor = ''
  el.removeAttribute('aria-disabled')
  BLOCK_EVENTS.forEach((ev) => el.removeEventListener(ev, blocker, true))
}

function apply(el: PermEl, binding: DirectiveBinding<PermValue>): void {
  const { value, modifiers } = binding
  // 空值不做任何限制（便于 v-permission="someRef" 动态绑定时的初始空态）
  if (value === undefined || value === null || value === '') return

  const ok = allowed(value, !!modifiers.every)

  if (modifiers.disable) {
    if (ok) enableEl(el)
    else disableEl(el)
    return
  }

  // 默认：无权限则从 DOM 移除（权限在本平台登录后不变，无需恢复逻辑）
  if (!ok) el.parentNode?.removeChild(el)
}

export const permission: Directive<PermEl, PermValue> = {
  mounted: apply,
  updated: apply,
  unmounted: enableEl,
}
