<script setup lang="ts">
/**
 * App 用例步骤编辑器 —— 可视化块 / YAML 源码 双模式。
 *
 * 对外只暴露一个 yaml 字符串（v-model），保存路径与后端字段 yaml_content 不变。
 * - 可视化：多任务 + 每任务 flow 步骤卡（vuedraggable 拖拽排序 + 动作调色板 +
 *   逐步字段表单）。所见即所存，块↔YAML 经 appYamlCodec 双向转换（镜像 recover.ts）。
 * - 源码：CodeEditor(language=yaml)，YAML 为真相源与逃生口。
 * - 遇编辑器不支持的构造（aiAssert/额外 key…）→ 强制留源码模式并提示，绝不静默丢字段。
 *
 * echo 守卫：只有用户真编辑才 emit；外部 seed（打开弹窗）不回写，避免打开即“脏”/重排版。
 */
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import draggable from 'vuedraggable'
import CodeEditor from '@/components/common/CodeEditor.vue'
import AppEmpty from '@/components/common/AppEmpty.vue'
import {
  actionMeta,
  makeStep,
  makeTask,
  metasForPlatform,
  tasksToYaml,
  parseYamlToTasks,
  type AppTask,
  type AppActionKind,
} from '../appYamlCodec'

const props = withDefaults(
  defineProps<{ modelValue: string; readonly?: boolean; platform?: string }>(),
  { readonly: false, platform: undefined },
)
const emit = defineEmits<{ (e: 'update:modelValue', v: string): void }>()

type Mode = 'blocks' | 'source'
const mode = ref<Mode>('blocks')
const tasks = ref<AppTask[]>([])
const source = ref('')
const parseError = ref('')
// 最近一次自己 emit 的值：watch 到相等即认作回声，不重新 seed
const lastEmitted = ref<string | null>(null)

const metaOf = actionMeta
const DIRECTIONS = [
  { value: 'up', label: '上' },
  { value: 'down', label: '下' },
  { value: 'left', label: '左' },
  { value: 'right', label: '右' },
]

/** 动作按分组组织，供调色板 + 步骤下拉（按脚本平台过滤：android/harmony/ios 专属键互不串台） */
const groupedMetas = computed(() => {
  const metas = metasForPlatform(props.platform)
  const map = new Map<string, typeof metas>()
  for (const m of metas) {
    if (!map.has(m.group)) map.set(m.group, [])
    map.get(m.group)!.push(m)
  }
  return [...map.entries()].map(([group, items]) => ({ group, items }))
})

const totalSteps = computed(() => tasks.value.reduce((n, t) => n + t.flow.length, 0))

// ==================== seed（外部值 → 内部状态） ====================
function seed(y: string) {
  const res = parseYamlToTasks(y)
  source.value = y
  if (res.ok) {
    tasks.value = res.tasks
    parseError.value = ''
    mode.value = 'blocks'
  } else {
    parseError.value = res.reason
    mode.value = 'source'
  }
}

watch(
  () => props.modelValue,
  (v) => {
    if (v === lastEmitted.value) return // 自己 emit 的回声，忽略
    seed(v ?? '')
  },
  { immediate: true },
)

// ==================== 块编辑 → 回写 ====================
function emitBlocks() {
  const y = tasksToYaml(tasks.value)
  source.value = y
  lastEmitted.value = y
  emit('update:modelValue', y)
}

function onSourceInput(v: string) {
  source.value = v
  lastEmitted.value = v
  emit('update:modelValue', v)
}

// ==================== 模式切换 ====================
function switchMode(next: Mode | string | number | boolean | undefined) {
  const m = next as Mode
  if (m === mode.value) return
  if (m === 'blocks') {
    const res = parseYamlToTasks(source.value)
    if (!res.ok) {
      parseError.value = res.reason
      ElMessage.warning('当前 YAML 含可视化编辑器不支持的结构，请在源码模式编辑')
      return // 不切换，radio 依 :model-value 归位
    }
    tasks.value = res.tasks
    parseError.value = ''
    mode.value = 'blocks'
  } else {
    source.value = tasksToYaml(tasks.value) // 同步最新块到源码
    mode.value = 'source'
  }
}

// ==================== 块操作 ====================
function addStep(task: AppTask, action: AppActionKind) {
  task.flow.push(makeStep(action))
  emitBlocks()
}
function removeStep(task: AppTask, idx: number) {
  task.flow.splice(idx, 1)
  emitBlocks()
}
/** 改动作类型：换骨架但保留 _uid，尽量迁移 locate/value */
function changeAction(task: AppTask, idx: number, next: AppActionKind) {
  const old = task.flow[idx]
  const ns = makeStep(next)
  ns._uid = old._uid
  if (old.locate) ns.locate = old.locate
  if (old.value) ns.value = old.value
  task.flow[idx] = ns
  emitBlocks()
}
function addTask() {
  tasks.value.push(makeTask(`任务${tasks.value.length + 1}`))
  emitBlocks()
}
function removeTask(idx: number) {
  tasks.value.splice(idx, 1)
  emitBlocks()
}
</script>

<template>
  <div class="step-editor">
    <div class="se-toolbar">
      <el-radio-group :model-value="mode" size="small" @change="switchMode">
        <el-radio-button value="blocks">
          <i class="i-solar-widget-2-linear se-tabi" />可视化
        </el-radio-button>
        <el-radio-button value="source">
          <i class="i-solar-code-linear se-tabi" />YAML 源码
        </el-radio-button>
      </el-radio-group>
      <span v-if="mode === 'blocks'" class="se-meta">
        {{ tasks.length }} 任务 · {{ totalSteps }} 步 · 拖动
        <i class="i-solar-hamburger-menu-linear se-dragi" /> 排序
      </span>
    </div>

    <!-- 可视化块 -->
    <div v-if="mode === 'blocks'" class="se-blocks">
      <div v-for="(task, ti) in tasks" :key="task._uid" class="task-card">
        <div class="task-head">
          <i class="i-solar-checklist-minimalistic-linear task-icon" />
          <el-input
            v-model="task.name"
            size="small"
            class="task-name"
            placeholder="任务名"
            :disabled="readonly"
            @input="emitBlocks"
          />
          <span class="task-count">{{ task.flow.length }} 步</span>
          <el-button
            v-if="!readonly && tasks.length > 1"
            text
            size="small"
            class="task-del"
            @click="removeTask(ti)"
          >
            <i class="i-solar-trash-bin-trash-linear" />
          </el-button>
        </div>

        <draggable
          v-model="task.flow"
          :group="{ name: 'app-flow' }"
          item-key="_uid"
          handle=".drag-handle"
          :animation="160"
          ghost-class="step-ghost"
          :disabled="readonly"
          class="flow-list"
          @change="emitBlocks"
        >
          <template #item="{ element: step, index }">
            <div class="step-row">
              <i v-if="!readonly" class="i-solar-hamburger-menu-linear drag-handle" />
              <span class="step-idx">{{ index + 1 }}</span>
              <el-select
                :model-value="step.action"
                size="small"
                class="step-action"
                :disabled="readonly"
                @change="(v: AppActionKind) => changeAction(task, index, v)"
              >
                <el-option-group v-for="g in groupedMetas" :key="g.group" :label="g.group">
                  <el-option
                    v-for="m in g.items"
                    :key="m.action"
                    :label="m.label"
                    :value="m.action"
                  />
                </el-option-group>
              </el-select>

              <!-- 字段区：按 form 渲染 -->
              <el-input
                v-if="metaOf(step.action).form === 'locate'"
                v-model="step.locate"
                size="small"
                placeholder="定位描述，如：屏幕上的搜索按钮"
                :disabled="readonly"
                @input="emitBlocks"
              />
              <template v-else-if="metaOf(step.action).form === 'input'">
                <el-input
                  v-model="step.locate"
                  size="small"
                  class="f-locate"
                  placeholder="定位：输入框"
                  :disabled="readonly"
                  @input="emitBlocks"
                />
                <el-input
                  v-model="step.value"
                  size="small"
                  class="f-value"
                  placeholder="输入值"
                  :disabled="readonly"
                  @input="emitBlocks"
                />
              </template>
              <template v-else-if="metaOf(step.action).form === 'swipe'">
                <el-select
                  v-model="step.params.direction"
                  size="small"
                  class="f-dir"
                  :disabled="readonly"
                  @change="emitBlocks"
                >
                  <el-option v-for="d in DIRECTIONS" :key="d.value" :label="d.label" :value="d.value" />
                </el-select>
                <el-input-number
                  v-model="step.params.distance"
                  :min="1"
                  :step="100"
                  size="small"
                  controls-position="right"
                  class="f-num"
                  :disabled="readonly"
                  @change="emitBlocks"
                />
                <span class="f-unit">px</span>
              </template>
              <el-input
                v-else-if="metaOf(step.action).form === 'keyname'"
                v-model="step.params.keyName"
                size="small"
                placeholder="按键名，如 Enter / Backspace"
                :disabled="readonly"
                @input="emitBlocks"
              />
              <template v-else-if="metaOf(step.action).form === 'sleep'">
                <el-input-number
                  v-model="step.params.timeMs"
                  :min="0"
                  :step="100"
                  size="small"
                  controls-position="right"
                  class="f-num"
                  :disabled="readonly"
                  @change="emitBlocks"
                />
                <span class="f-unit">毫秒</span>
              </template>
              <el-input
                v-else-if="metaOf(step.action).form === 'launch'"
                v-model="step.value"
                size="small"
                placeholder="应用包名 / URI，如 com.android.settings"
                :disabled="readonly"
                @input="emitBlocks"
              />
              <span v-else class="f-none">{{ metaOf(step.action).hint }}</span>

              <el-button
                v-if="!readonly"
                text
                size="small"
                class="step-del"
                @click="removeStep(task, index)"
              >
                <i class="i-solar-close-circle-linear" />
              </el-button>
            </div>
          </template>
        </draggable>

        <div v-if="!task.flow.length" class="flow-empty">还没有步骤，点下方「添加步骤」</div>

        <div v-if="!readonly" class="flow-add">
          <el-popover :width="340" trigger="click" placement="bottom-start" :teleported="true">
            <template #reference>
              <el-button size="small" text type="primary">
                <i class="i-solar-add-circle-linear btn-i" />添加步骤
              </el-button>
            </template>
            <div class="palette">
              <div v-for="g in groupedMetas" :key="g.group" class="pal-group">
                <div class="pal-title">{{ g.group }}</div>
                <div class="pal-items">
                  <el-button
                    v-for="m in g.items"
                    :key="m.action"
                    size="small"
                    class="pal-btn"
                    :title="m.hint"
                    @click="addStep(task, m.action)"
                  >
                    {{ m.label }}
                  </el-button>
                </div>
              </div>
            </div>
          </el-popover>
        </div>
      </div>

      <div v-if="!readonly" class="task-add">
        <el-button size="small" @click="addTask">
          <i class="i-solar-add-square-linear btn-i" />添加任务
        </el-button>
      </div>

      <AppEmpty
        v-if="!tasks.length"
        scene="data"
        description="空用例。点「添加任务」开始，或切到 YAML 源码粘贴。"
      />
    </div>

    <!-- YAML 源码 -->
    <div v-else class="se-source">
      <el-alert
        v-if="parseError"
        :title="`可视化不支持：${parseError}`"
        type="warning"
        :closable="false"
        show-icon
        class="se-alert"
      />
      <CodeEditor
        :model-value="source"
        language="yaml"
        :readonly="readonly"
        min-height="280px"
        max-height="440px"
        @update:model-value="onSourceInput"
      />
    </div>
  </div>
</template>

<style scoped lang="scss">
.step-editor {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.se-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.se-tabi {
  margin-right: 4px;
  vertical-align: -2px;
}
.se-meta {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  display: inline-flex;
  align-items: center;
  gap: 3px;
}
.se-dragi {
  vertical-align: -2px;
}

/* ---- 可视化块 ---- */
.se-blocks {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 460px;
  overflow-y: auto;
  padding-right: 2px;
}
.task-card {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-hover);
  padding: 10px 12px;
}
.task-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.task-icon {
  font-size: 16px;
  color: var(--brand-500);
}
.task-name {
  max-width: 260px;
}
.task-count {
  font-size: var(--font-size-xs);
  color: var(--text-placeholder);
}
.task-del {
  margin-left: auto;
  color: var(--color-danger-500);
}

.flow-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.step-row {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  padding: 6px 8px;
}
.drag-handle {
  cursor: grab;
  color: var(--text-placeholder);
  font-size: 15px;
  flex: none;
}
.drag-handle:active {
  cursor: grabbing;
}
.step-idx {
  flex: none;
  width: 20px;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-full);
  background: var(--brand-50);
  color: var(--brand-600);
  font-size: 11px;
  font-weight: var(--font-weight-semibold);
}
.step-action {
  flex: none;
  width: 116px;
}
.step-row :deep(.el-input),
.step-row .f-locate {
  flex: 1;
  min-width: 0;
}
.f-value {
  flex: 1;
  min-width: 0;
}
.f-dir {
  flex: none;
  width: 84px;
}
.f-num {
  flex: none;
  width: 120px;
}
.f-unit {
  flex: none;
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
}
.f-none {
  flex: 1;
  font-size: var(--font-size-sm);
  color: var(--text-placeholder);
}
.step-del {
  flex: none;
  color: var(--text-placeholder);
}
.step-del:hover {
  color: var(--color-danger-500);
}
.step-ghost {
  opacity: 0.5;
  background: var(--brand-50);
}

.flow-empty {
  font-size: var(--font-size-sm);
  color: var(--text-placeholder);
  padding: 8px 2px;
}
.flow-add {
  margin-top: 8px;
}
.btn-i {
  margin-right: 3px;
}
.task-add {
  margin-top: 2px;
}

/* ---- 调色板 ---- */
.palette {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.pal-group {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.pal-title {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  font-weight: var(--font-weight-medium);
}
.pal-items {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.pal-btn {
  margin: 0 !important;
}

/* ---- 源码 ---- */
.se-source {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.se-alert {
  padding: 6px 10px;
}
</style>
