<template>
  <el-dialog
    v-model="visible"
    :title="`表结构 · ${connName}`"
    width="860px"
    top="6vh"
    :close-on-click-modal="false"
  >
    <SchemaBrowser
      v-if="visible"
      :project-id="projectId"
      :conn-id="connId"
      :height="480"
    />
    <template #footer>
      <el-button type="primary" @click="visible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
/** 表结构弹窗（数据库连接页入口）：薄壳包 SchemaBrowser，浏览逻辑单一真源。 */
import { computed } from 'vue'
import SchemaBrowser from './SchemaBrowser.vue'

const props = defineProps<{
  modelValue: boolean
  projectId: number
  connId: number
  connName: string
}>()
const emit = defineEmits<{ 'update:modelValue': [v: boolean] }>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})
</script>
