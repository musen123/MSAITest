<template>
  <el-dialog
    v-model="visible"
    width="600px"
    :close-on-click-modal="false"
    class="app-dialog add-member-dialog"
    @close="handleClose"
  >
    <template #header>
      <div class="dialog-header">
        <h3 class="dialog-title">添加成员</h3>
        <p class="dialog-desc">搜索用户并为其分配项目角色</p>
      </div>
    </template>

    <el-form
      ref="formRef"
      :model="formData"
      :rules="formRules"
      label-position="top"
      @submit.prevent="handleSubmit"
    >
      <el-form-item label="搜索用户">
        <el-input
          v-model="searchKeyword"
          placeholder="输入用户名或姓名搜索"
          clearable
          @input="handleSearchUsers"
        >
          <template #prefix>
            <i class="i-solar-magnifer-linear" />
          </template>
          <template #append>
            <el-button @click="handleSearchUsers">
              <i class="i-solar-magnifer-linear mr-1" /> 搜索
            </el-button>
          </template>
        </el-input>
      </el-form-item>

      <el-form-item label="选择成员" prop="userIds" required>
        <div class="member-selector">
          <!-- 用户列表 -->
          <div v-loading="loadingUsers" class="user-list">
            <el-checkbox-group v-model="formData.userIds">
              <div
                v-for="user in availableUsers"
                :key="user.id"
                class="user-item"
              >
                <el-checkbox :label="user.id" :disabled="isExistingMember(user.id)">
                  <div class="user-info">
                    <el-avatar :src="user.avatar" :size="32">
                      {{ user.real_name?.charAt(0) || user.username?.charAt(0) }}
                    </el-avatar>
                    <div class="user-detail">
                      <div class="user-name">{{ user.real_name || user.username }}</div>
                      <div class="user-username">@{{ user.username }}</div>
                    </div>
                    <el-tag v-if="isExistingMember(user.id)" size="small" type="info">
                      已添加
                    </el-tag>
                  </div>
                </el-checkbox>
              </div>
            </el-checkbox-group>

            <el-empty
              v-if="!loadingUsers && availableUsers.length === 0"
              description="未找到用户"
              :image-size="60"
            />
          </div>

          <!-- 已选成员 -->
          <div v-if="selectedUsers.length > 0" class="selected-users">
            <div class="selected-header">
              <span>已选择 {{ selectedUsers.length }} 人</span>
              <el-button link type="danger" size="small" @click="handleClearSelection">
                清空
              </el-button>
            </div>
            <div class="selected-list">
              <el-tag
                v-for="user in selectedUsers"
                :key="user.id"
                closable
                @close="handleRemoveUser(user.id)"
              >
                {{ user.real_name || user.username }}
              </el-tag>
            </div>
          </div>
        </div>
      </el-form-item>

      <el-form-item label="项目角色">
        <div class="form-tip">
          新成员默认以「项目成员」加入；实际操作权限由其<strong>系统角色</strong>决定（在「用户管理」中分配），项目负责人通过「转让」功能变更。
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button
        type="primary"
        :loading="submitting"
        :disabled="formData.userIds.length === 0"
        @click="handleSubmit"
      >
        <i class="i-solar-user-plus-bold mr-1" />
        添加 ({{ formData.userIds.length }})
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { projectApi } from '@/api/projects'
import { userApi } from '@/api/user'
import type { ProjectMember, ProjectRole, AddMemberRequest } from '@/api/projects'
import type { UserListItem } from '@/types/user'

interface Props {
  modelValue: boolean
  projectId: number
  existingMembers?: ProjectMember[]
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: false,
  existingMembers: () => [],
})

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'success': []
}>()

const formRef = ref<FormInstance | null>(null)
const searchKeyword = ref('')
const loadingUsers = ref(false)
const availableUsers = ref<UserListItem[]>([])
const submitting = ref(false)

const formData = ref<{
  userIds: number[]
  projectRole: ProjectRole
}>({
  userIds: [],
  projectRole: 'project_member',
})

const formRules: FormRules = {
  userIds: [
    { required: true, message: '请选择要添加的成员', trigger: 'change' },
    { type: 'array', min: 1, message: '至少选择一个成员', trigger: 'change' },
  ],
  projectRole: [{ required: true, message: '请选择项目角色', trigger: 'change' }],
}

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

const existingMemberIds = computed(() => {
  return new Set(props.existingMembers.map((m) => m.user?.id).filter(Boolean))
})

const selectedUsers = computed(() => {
  return availableUsers.value.filter((u) => formData.value.userIds.includes(u.id))
})

const isExistingMember = (userId: number) => existingMemberIds.value.has(userId)

const handleSearchUsers = async () => {
  if (!searchKeyword.value || searchKeyword.value.trim().length === 0) {
    availableUsers.value = []
    return
  }

  loadingUsers.value = true
  try {
    const response = await userApi.getList({
      keyword: searchKeyword.value.trim(),
      status: 'active',
      page: 1,
      page_size: 20,
    })
    if (response.code === 200) {
      availableUsers.value = response.data.items
    }
  } catch (error) {
    console.error('搜索用户失败:', error)
  } finally {
    loadingUsers.value = false
  }
}

const handleClearSelection = () => { formData.value.userIds = [] }

const handleRemoveUser = (userId: number) => {
  const index = formData.value.userIds.indexOf(userId)
  if (index > -1) formData.value.userIds.splice(index, 1)
}

const resetForm = () => {
  formData.value = { userIds: [], projectRole: 'project_member' }
  searchKeyword.value = ''
  availableUsers.value = []
  formRef.value?.clearValidate()
}

const handleSubmit = async () => {
  if (!formRef.value) return

  try { await formRef.value.validate() } catch { return }

  submitting.value = true
  try {
    const data: AddMemberRequest = {
      user_ids: formData.value.userIds,
      project_role: formData.value.projectRole,
    }
    const response = await projectApi.addProjectMembers(props.projectId, data)
    if (response.code === 200) {
      ElMessage.success(`成功添加 ${response.data.added_count} 位成员`)
      emit('success')
      handleClose()
    }
  } catch (error) {
    console.error('添加成员失败:', error)
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

watch(
  () => formData.value.userIds,
  (newUserIds) => {
    const filtered = newUserIds.filter((id) => !isExistingMember(id))
    if (filtered.length !== newUserIds.length) formData.value.userIds = filtered
  },
  { deep: true },
)
</script>

<style scoped lang="scss">
.add-member-dialog {
  :deep(.el-form-item) { margin-bottom: var(--space-5); }
}

.full-width { width: 100%; }

.member-selector {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  width: 100%;
}

.user-list {
  max-height: 300px;
  overflow-y: auto;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  padding: 8px;

  &::-webkit-scrollbar { width: 6px; }
  &::-webkit-scrollbar-thumb {
    background: var(--gray-300);
    border-radius: 3px;
    &:hover { background: var(--gray-400); }
  }
}

.user-item {
  padding: 8px;
  border-radius: var(--radius-sm);
  transition: background-color 0.2s;

  &:hover { background: var(--gray-50); }

  :deep(.el-checkbox) {
    width: 100%;
    display: flex;
    align-items: center;

    .el-checkbox__label {
      flex: 1;
      padding-left: 8px;
    }
  }
}

.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
}

.user-detail { flex: 1; min-width: 0; }

.user-name {
  font-size: 14px;
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
}

.user-username {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}

.selected-users {
  padding: 12px;
  background: var(--gray-50);
  border-radius: var(--radius-md);
}

.selected-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 13px;
  color: var(--text-secondary);
}

.selected-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;

  :deep(.el-tag) { margin: 0; }
}

.form-tip {
  font-size: 12px;
  color: var(--text-placeholder);
  margin-top: 4px;
}
</style>