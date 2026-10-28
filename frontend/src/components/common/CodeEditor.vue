<template>
  <div class="code-editor" :class="{ 'is-readonly': readonly, 'is-focused': isFocused, 'is-auto-height': autoHeight }">
    <div ref="editorContainer" class="editor-container"></div>
    <div v-if="showLanguageSelector" class="language-selector">
      <el-select
        :model-value="modelLanguage"
        size="small"
        @change="handleLanguageChange"
      >
        <el-option label="Python" value="python" />
        <el-option label="JavaScript" value="javascript" />
        <el-option label="JSON" value="json" />
        <el-option label="SQL" value="sql" />
        <el-option label="YAML" value="yaml" />
        <el-option label="HTML" value="html" />
        <el-option label="CSS" value="css" />
      </el-select>
    </div>
    <div v-if="showLineCount" class="line-count">
      {{ lineCount }} 行
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount, shallowRef } from 'vue'
import { EditorView, basicSetup } from 'codemirror'
import { EditorState } from '@codemirror/state'
import { keymap } from '@codemirror/view'
import { defaultKeymap, history, historyKeymap } from '@codemirror/commands'
import { bracketMatching } from '@codemirror/language'
import { closeBrackets, closeBracketsKeymap } from '@codemirror/autocomplete'
import { highlightSelectionMatches } from '@codemirror/search'
import { oneDark } from '@codemirror/theme-one-dark'
import { python } from '@codemirror/lang-python'
import { javascript } from '@codemirror/lang-javascript'
import { json } from '@codemirror/lang-json'
import { html } from '@codemirror/lang-html'
import { css } from '@codemirror/lang-css'
import { yaml } from '@codemirror/lang-yaml'
import { sql, MySQL } from '@codemirror/lang-sql'

// ==================== 类型定义 ====================

// 'text' = 纯文本(无语法高亮):langMap 无此键 → 无高亮扩展,得到等宽+行号的纯文本编辑器
// (适合 CSV/制表符粘贴等非代码内容复用本组件)
export type CodeLanguage = 'python' | 'javascript' | 'json' | 'html' | 'css' | 'yaml' | 'sql' | 'text'

export interface CodeEditorProps {
  modelValue: string
  language?: CodeLanguage
  theme?: 'light' | 'dark' | 'auto'
  readonly?: boolean
  lineNumbers?: boolean
  foldGutter?: boolean
  matchBrackets?: boolean
  closeBrackets?: boolean
  autocomplete?: boolean
  search?: boolean
  minHeight?: string
  maxHeight?: string
  /** 自适应高度：编辑器随内容撑开，不设 min/max，交给外层容器滚动（只读查看场景） */
  autoHeight?: boolean
  showLanguageSelector?: boolean
  showLineCount?: boolean
}

// ==================== Props & Emits ====================

interface Props {
  modelValue: string
  language?: CodeLanguage
  theme?: 'light' | 'dark' | 'auto'
  readonly?: boolean
  lineNumbers?: boolean
  foldGutter?: boolean
  matchBrackets?: boolean
  closeBrackets?: boolean
  autocomplete?: boolean
  search?: boolean
  minHeight?: string
  maxHeight?: string
  /** 自适应高度：编辑器随内容撑开，不设 min/max，交给外层容器滚动（只读查看场景） */
  autoHeight?: boolean
  showLanguageSelector?: boolean
  showLineCount?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  language: 'python',
  theme: 'auto',
  readonly: false,
  lineNumbers: true,
  foldGutter: true,
  matchBrackets: true,
  closeBrackets: true,
  autocomplete: true,
  search: true,
  minHeight: '200px',
  maxHeight: '500px',
  autoHeight: false,
  showLanguageSelector: false,
  showLineCount: false,
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'update:language', value: CodeLanguage): void
  (e: 'focus'): void
  (e: 'blur'): void
  (e: 'change', value: string): void
}>()

// ==================== 响应式数据 ====================

const editorContainer = ref<HTMLElement>()
const editorView = shallowRef<EditorView>()
const isFocused = ref(false)
const lineCount = ref(0)
const systemTheme = ref<'light' | 'dark'>('light')
let themeObserver: MutationObserver | null = null
// 容器尺寸变化时让 CodeMirror 重新测量(修复:在初始隐藏/折叠容器内挂载时宽度测错、
// 展开后不回流的问题 —— 折叠面板/弹框 resize 等场景都靠它自愈)
let resizeObserver: ResizeObserver | null = null

// 内部使用的语言状态（用于语言选择器）
const modelLanguage = computed({
  get: () => props.language,
  set: (value: CodeLanguage) => emit('update:language', value),
})

// ==================== 计算属性 ====================

const resolvedTheme = computed<'light' | 'dark'>(() => {
  return props.theme === 'auto' ? systemTheme.value : props.theme
})

const editorTheme = computed(() => {
  const extensions = []
  if (resolvedTheme.value === 'dark') {
    extensions.push(oneDark)
  }
  return extensions
})

// ==================== 语言支持 ====================

const languageExtensions = computed(() => {
  const langMap = {
    python,
    javascript,
    json,
    html,
    css,
    yaml,
    sql: () => sql({ dialect: MySQL }),
  }
  return langMap[props.language] ? [langMap[props.language]()] : []
})

// ==================== 编辑器扩展配置 ====================

const getExtensions = () => {
  const extensions = [
    // 基础配置
    basicSetup,

    // 历史记录
    history(),

    // 键盘映射
    keymap.of([
      ...defaultKeymap,
      ...historyKeymap,
      ...closeBracketsKeymap,
    ]),

    // 括号匹配
    ...(props.matchBrackets ? [bracketMatching()] : []),

    // 自动闭合括号
    ...(props.closeBrackets ? [closeBrackets()] : []),

    // 高亮选中匹配
    highlightSelectionMatches(),

    // 语言支持
    ...languageExtensions.value,

    // 主题
    ...editorTheme.value,

    // 只读模式
    EditorView.editable.of(!props.readonly),

    // 行号
    ...(props.lineNumbers ? [] : []), // basicSetup 已包含行号

    // 事件监听
    EditorView.updateListener.of((update) => {
      if (update.docChanged) {
        const value = update.state.doc.toString()
        emit('update:modelValue', value)
        emit('change', value)
        lineCount.value = update.state.doc.lines
      }
      if (update.focusChanged) {
        isFocused.value = update.view.hasFocus
        if (update.view.hasFocus) {
          emit('focus')
        } else {
          emit('blur')
        }
      }
    }),
  ]

  return extensions
}

// ==================== 编辑器初始化 ====================

const initEditor = () => {
  if (!editorContainer.value) return

  // 创建编辑器状态
  const state = EditorState.create({
    doc: props.modelValue,
    extensions: getExtensions(),
  })

  // 创建编辑器视图
  editorView.value = new EditorView({
    state,
    parent: editorContainer.value,
  })

  // 容器尺寸变化(含 0→可见)时重新测量,避免折叠/隐藏中挂载导致的宽度测错不回流
  resizeObserver = new ResizeObserver(() => {
    editorView.value?.requestMeasure()
  })
  resizeObserver.observe(editorContainer.value)

  // 初始化行数
  lineCount.value = state.doc.lines
}

// ==================== 编辑器更新 ====================

const updateEditorContent = (content: string) => {
  if (!editorView.value) return

  const transaction = editorView.value.state.update({
    changes: {
      from: 0,
      to: editorView.value.state.doc.length,
      insert: content,
    },
  })

  editorView.value.dispatch(transaction)
}

const updateEditorExtensions = () => {
  if (!editorView.value) return

  const extensions = getExtensions()

  // 重建编辑器以应用新的扩展
  const state = EditorState.create({
    doc: editorView.value.state.doc.toString(),
    extensions,
  })

  editorView.value.setState(state)
}

// ==================== 事件处理 ====================

const handleLanguageChange = (value: CodeLanguage) => {
  emit('update:language', value)
}

// ==================== 监听器 ====================

// 监听 modelValue 变化
watch(
  () => props.modelValue,
  (newValue) => {
    if (!editorView.value) return
    const currentValue = editorView.value.state.doc.toString()
    if (newValue !== currentValue) {
      updateEditorContent(newValue)
    }
  },
)

// 监听主题变化
watch(
  resolvedTheme,
  () => {
    updateEditorExtensions()
  },
)

// 监听语言变化
watch(
  () => props.language,
  () => {
    updateEditorExtensions()
  },
)

// 监听只读模式变化
watch(
  () => props.readonly,
  () => {
    updateEditorExtensions()
  },
)

// ==================== 生命周期 ====================

const syncSystemTheme = () => {
  const theme = document.documentElement.getAttribute('data-theme')
  systemTheme.value = theme === 'dark' ? 'dark' : 'light'
}

onMounted(() => {
  syncSystemTheme()
  themeObserver = new MutationObserver(syncSystemTheme)
  themeObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme'],
  })
  initEditor()
})

onBeforeUnmount(() => {
  themeObserver?.disconnect()
  resizeObserver?.disconnect()
  if (editorView.value) {
    editorView.value.destroy()
  }
})

// ==================== 暴露的方法 ====================

defineExpose({
  focus: () => {
    editorView.value?.focus()
  },
  blur: () => {
    editorView.value?.contentDOM?.blur()
  },
  getSelection: () => {
    if (!editorView.value) return ''
    const selection = editorView.value.state.selection.main
    return editorView.value.state.sliceDoc(selection.from, selection.to)
  },
  setSelection: (from: number, to: number) => {
    if (!editorView.value) return
    const transaction = editorView.value.state.update({
      selection: { anchor: from, head: to },
    })
    editorView.value.dispatch(transaction)
  },
  insert: (text: string) => {
    if (!editorView.value) return
    const transaction = editorView.value.state.update({
      changes: {
        from: editorView.value.state.selection.main.from,
        to: editorView.value.state.selection.main.to,
        insert: text,
      },
    })
    editorView.value.dispatch(transaction)
  },
})
</script>

<style scoped lang="scss">
// ========================================
// 容器样式
// ========================================

.code-editor {
  position: relative;
  width: 100%;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--bg-card);
  transition: var(--transition-base);

  &:hover {
    border-color: var(--border-base);
  }

  &.is-focused {
    border-color: var(--brand-500);
    box-shadow: 0 0 0 3px var(--brand-glow-soft);
  }

  &.is-readonly {
    background: var(--bg-hover);
    opacity: 0.8;

    .editor-container {
      cursor: not-allowed;
    }
  }

  // 自适应高度：撑到内容真实高度，取消 min/max 高度上限与内部滚动，
  // 由外层容器（弹窗 .cv-cards 等）统一滚动，避免嵌套滚动与内容截断。
  // 关键=CodeMirror 官方 auto-height 配方（.cm-editor height:auto），
  // editor-container 保持 overflow:auto（绝不用 visible，否则内容会溢出卡片被 .code-editor
  // 的 overflow:hidden 裁掉）。
  // 覆盖须嵌在 .editor-container 内：与下方基础规则 `.editor-container .cm-editor
  // .cm-content{min-height}` 同优先级，靠多一层 .editor-container 提高特异性稳压过它，
  // 否则源码顺序在后的基础规则会赢，min-height 卡在 200px 短内容留大片空白。
  &.is-auto-height {
    .editor-container {
      min-height: 0;
      max-height: none;

      :deep(.cm-editor) {
        height: auto;
      }
      :deep(.cm-content) {
        min-height: 0;
      }
    }
  }
}

// ========================================
// 编辑器容器
// ========================================

.editor-container {
  min-height: v-bind('props.minHeight');
  max-height: v-bind('props.maxHeight');
  overflow: auto;
  font-size: 13px;
  font-family: 'SF Mono', 'Monaco', 'Consolas', 'Liberation Mono', 'Courier New', monospace;
  line-height: 1.6;

  // 自定义滚动条
  &::-webkit-scrollbar {
    width: 10px;
    height: 10px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }

  &::-webkit-scrollbar-thumb {
    background: var(--border-strong);
    border-radius: 5px;

    &:hover {
      background: var(--text-placeholder);
    }
  }

  // CodeMirror 样式覆盖：背景随当前 data-theme 走项目 token
  :deep(.cm-editor) {
    height: 100%;
    background: var(--bg-card);
    color: var(--text-primary);

    .cm-scroller {
      font-family: inherit;
      background: var(--bg-card);
    }

    .cm-content {
      padding: 12px 0;
      min-height: v-bind('props.minHeight');
      caret-color: var(--brand-500);
    }

    .cm-line {
      padding: 0 12px;
    }

    .cm-gutters {
      background: var(--bg-hover);
      border-right: 1px solid var(--border-light);
      color: var(--text-placeholder);
    }

    .cm-activeLine,
    .cm-activeLineGutter {
      background: var(--bg-hover) !important;
    }

    .cm-activeLineGutter {
      color: var(--text-primary);
    }

    .cm-cursor {
      border-left: 2px solid var(--brand-500);
    }

    .cm-selectionBackground {
      background: var(--brand-glow-strong) !important;
    }

    .cm-matchingBracket {
      background: var(--brand-glow-soft);
      color: var(--text-primary);
      font-weight: bold;
    }

    .cm-nonmatchingBracket {
      background: color-mix(in srgb, var(--color-danger-500) 18%, transparent);
      color: var(--color-danger-600);
    }

    .cm-gutterElement.cm-activeLineGutter {
      color: var(--brand-500);
    }

    .cm-searchMatch {
      background: color-mix(in srgb, var(--color-warning-500) 24%, transparent);
      border-bottom: 1px solid color-mix(in srgb, var(--color-warning-500) 50%, transparent);
    }

    .cm-searchMatch-selected {
      background: color-mix(in srgb, var(--color-warning-500) 36%, transparent);
      border-bottom: 1px solid var(--color-warning-500);
    }
  }

  :deep(.cm-editor.cm-focused) {
    outline: none;
  }

  // oneDark 只提供语法高亮，背景仍强制跟随系统 token
  :deep(.cm-editor.cm-themes-one-dark) {
    background: var(--bg-card);

    .cm-scroller,
    .cm-content {
      background: var(--bg-card);
    }

    .cm-gutters {
      background: var(--bg-hover);
      border-right-color: var(--border-light);
      color: var(--text-secondary);
    }

    .cm-activeLine,
    .cm-activeLineGutter {
      background: var(--bg-hover) !important;
    }

    .cm-activeLineGutter {
      color: var(--text-primary);
    }

    .cm-cursor {
      border-left-color: var(--brand-500);
    }

    .cm-selectionBackground {
      background: var(--brand-glow-strong) !important;
    }
  }
}

// ========================================
// 语言选择器
// ========================================

.language-selector {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 10;

  :deep(.el-select) {
    width: 120px;
  }

  :deep(.el-input__wrapper) {
    background: color-mix(in srgb, var(--bg-card) 92%, transparent) !important;
    backdrop-filter: blur(10px);
    box-shadow: var(--shadow-sm);
  }
}

// ========================================
// 行数显示
// ========================================

.line-count {
  position: absolute;
  bottom: 8px;
  right: 8px;
  padding: 4px 8px;
  background: color-mix(in srgb, var(--text-primary) 70%, transparent);
  color: var(--text-inverse);
  font-size: 12px;
  border-radius: var(--radius-xs);
  pointer-events: none;
}

// ========================================
// 响应式设计
// ========================================

@media (max-width: 768px) {
  .editor-container {
    font-size: 12px;
  }

  .language-selector {
    :deep(.el-select) {
      width: 100px;
    }
  }
}
</style>
