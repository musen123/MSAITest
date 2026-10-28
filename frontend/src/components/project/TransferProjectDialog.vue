<template>
  <el-dialog
    v-model="visible"
    width="500px"
    :close-on-click-modal="false"
    class="app-dialog transfer-project-dialog"
    @close="handleClose"
  >
    <template #header>
      <div class="dialog-header">
        <h3 class="dialog-title">转让项目</h3>
        <p class="dialog-desc">将项目负责人权限转让给其他成员，操作不可撤销</p>
      </div>
    </template>

    <el-form
      ref="formRef"
      :model="formData"
      :rules="formRules"
      label-position="top"
      @submit.prevent="handleSubmit"
    >
      <el-form-item label="转让给" prop="toUserId" required>
        <el-select
          v-model="formData.toUserId"
          placeholder="选择接收人"
          class="full-width"
          filterable
        >
          <el-option
            v-for="member in availableMembers"
            :key="member.user!.id"
            :label="member.user!.real_name || member.user!.username"
            :value="member.user!.id"
          >
            <div class="member-option">
              <el-avatar :src="member.user!.avatar" :size="24" class="member-avatar">
                {{ member.user!.real_name?.charAt(0) || member.user!.username?.charAt(0) }}
              </el-avatar>
              <div class="member-detail">
                <span class="member-name">{{ member.user!.real_name || member.user!.username }}</span>
                <span class="member-username">@{{ member.user!.username }}</span>
              </div>
              <span v-if="member.user!.roles?.length" class="member-roles">
                {{ member.user!.roles.map((r) => r.name).join(' / ') }}
              </span>
            </div>
          </el-option>
        </el-select>
        <div class="form-tip">转让后您将降为项目成员，对方成为项目负责人，操作不可撤销；右侧标注成员的系统角色</div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="danger" :loading="submitting" @click="handleSubmit">
        <i class="i-solar-shield-keyhole-bold mr-1" />
        确认转让
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { projectApi } from '@/api/projects'
import type { ProjectMember, TransferProjectRequest } from '@/api/projects'

interface Props {
  modelValue: boolean
  projectId: number
  members: ProjectMember[]
  currentUserId: number
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: false,
  members: () => [],
})

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'success': []
}>()

const formRef = ref<FormInstance | null>(null)
const submitting = ref(false)

const formData = ref<{ toUserId: number | null }>({ toUserId: null })

const formRules: FormRules = {
  toUserId: [{ required: true, message: '请选择接收人', trigger: 'change' }],
}

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

const availableMembers = computed(() => {
  return props.members.filter((m) => m.user && m.user.id !== props.currentUserId)
})

const resetForm = () => {
  formData.value = { toUserId: null }
  formRef.value?.clearValidate()
}

const handleSubmit = async () => {
  if (!formRef.value || !formData.value.toUserId) return

  try { await formRef.value.validate() } catch { return }

  try {
    const targetMember = props.members.find((m) => m.user?.id === formData.value.toUserId)
    const targetName = targetMember?.user?.real_name || targetMember?.user?.username
    await ElMessageBox.confirm(
      `确定要将项目转让给「${targetName}」吗？转让后您将失去项目负责人权限，此操作不可撤销！`,
      '转让确认',
      {
        confirmButtonText: '确定转让',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger',
      },
    )
  } catch { return }

  submitting.value = true
  try {
    const data: TransferProjectRequest = { to_user_id: formData.value.toUserId }
    const response = await projectApi.transferProject(props.projectId, data)
    if (response.code === 200) {
      ElMessage.success('项目转让成功')
      emit('success')
      handleClose()
    } else {
      ElMessage.error(response.message || '转让失败')
    }
  } catch (error) {
    console.error('转让项目失败:', error)
  } finally {
    submitting.value = false
  }
}

const handleClose = () => { visible.value = false }

watch(
  () => props.modelValue,
  (val) => {
    if (val) {
      resetForm()
      nextTick(() => formRef.value?.clearValidate())
    }
  },
)
</script>

<style scoped lang="scss">
.transfer-project-dialog {
  :deep(.el-form-item) { margin-bottom: var(--space-5); }
}

.full-width { width: 100%; }

.member-option {
  display: flex;
  align-items: center;
  width: 100%;
}

.member-avatar { margin-right: 8px; }

.member-detail {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.member-name {
  font-size: 14px;
  color: var(--text-primary);
}

.member-username {
  font-size: 12px;
  color: var(--text-secondary);
}

.member-roles {
  margin-left: auto;
  padding-left: 8px;
  font-size: 12px;
  color: var(--text-placeholder);
  white-space: nowrap;
}

.form-tip {
  font-size: 12px;
  color: var(--text-placeholder);
  margin-top: 4px;
}
</style>