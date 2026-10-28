<template>
  <el-dialog
    v-model="visible"
    title="需求审核"
    width="520px"
    :close-on-click-modal="false"
    @open="handleOpen"
  >
    <div class="review-dialog">
      <!-- 需求信息条 -->
      <div v-if="requirement" class="req-target">
        <div class="req-icon">
          <i class="i-solar-clipboard-list-bold" />
        </div>
        <div class="req-info">
          <div class="req-code">
            {{ requirement.code || `#${requirement.id}` }}
          </div>
          <div class="req-title">{{ requirement.title }}</div>
        </div>
      </div>

      <!-- 审核结果（卡片二选） -->
      <div class="section-label">审核结果</div>
      <div class="action-options">
        <div
          class="action-option is-approve"
          :class="{ active: action === 'approve' }"
          @click="action = 'approve'"
        >
          <div class="action-icon">
            <i class="i-solar-check-circle-bold" />
          </div>
          <div class="action-info">
            <div class="action-title">通过</div>
            <div class="action-desc">评审通过，需求进入「已审核」状态</div>
          </div>
          <i
            class="i-solar-check-circle-bold action-check"
            :class="{ visible: action === 'approve' }"
          />
        </div>
        <div
          class="action-option is-reject"
          :class="{ active: action === 'reject' }"
          @click="action = 'reject'"
        >
          <div class="action-icon">
            <i class="i-solar-close-circle-bold" />
          </div>
          <div class="action-info">
            <div class="action-title">驳回</div>
            <div class="action-desc">退回修改，调整后需重新提交审核</div>
          </div>
          <i
            class="i-solar-check-circle-bold action-check"
            :class="{ visible: action === 'reject' }"
          />
        </div>
      </div>

      <!-- 审核意见 -->
      <div class="section-label">
        审核意见
        <span v-if="action === 'approve'" class="optional">可选</span>
      </div>
      <el-input
        v-model="comment"
        type="textarea"
        :rows="3"
        maxlength="500"
        show-word-limit
        :placeholder="action === 'approve'
          ? '补充说明（可选）...'
          : '请说明驳回原因，帮助提交人修改...'"
      />
    </div>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button
        :type="action === 'approve' ? 'primary' : 'danger'"
        :loading="submitting"
        @click="handleSubmit"
      >
        确认{{ action === 'approve' ? '通过' : '驳回' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
/**
 * 需求审核弹框（需求列表页 / 需求详情页共用）
 *
 * 卡片式通过/驳回二选 + 审核意见；提交成功后 emit('reviewed')
 * 由父组件刷新数据。
 */
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { funcRequirementApi } from '@/api/funcTest'
import type { FuncRequirement } from '@/types/func-test'

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    projectId: number
    requirement: FuncRequirement | null
    /** 打开时的默认动作（入口按钮区分通过/驳回） */
    initialAction?: 'approve' | 'reject'
  }>(),
  { initialAction: 'approve' },
)

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
  reviewed: []
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const action = ref<'approve' | 'reject'>('approve')
const comment = ref('')
const submitting = ref(false)

function handleOpen() {
  action.value = props.initialAction
  comment.value = ''
}

async function handleSubmit() {
  if (!props.requirement) return
  submitting.value = true
  try {
    await funcRequirementApi.review(props.projectId, props.requirement.id, {
      action: action.value,
      review_comment: comment.value || undefined,
    })
    ElMessage.success(action.value === 'approve' ? '已通过' : '已驳回')
    visible.value = false
    emit('reviewed')
  } catch (err) {
    console.error(err)
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped lang="scss">
.review-dialog {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* 需求信息条 */
.req-target {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  background: var(--el-fill-color-light);
  border-radius: 10px;

  .req-icon {
    width: 40px;
    height: 40px;
    border-radius: 9px;
    background: var(--brand-50);
    color: var(--brand-500);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 21px;
    flex-shrink: 0;
  }

  .req-info {
    flex: 1;
    min-width: 0;
  }

  .req-code {
    font-family: 'JetBrains Mono', Menlo, monospace;
    font-size: 12px;
    color: var(--text-secondary);
    line-height: 1.4;
  }

  .req-title {
    font-size: 14.5px;
    font-weight: 600;
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

/* 小节标题 */
.section-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: -6px;

  .optional {
    font-weight: 400;
    font-size: 11px;
    color: var(--text-placeholder);
    margin-left: 2px;
  }
}

/* 审核结果卡片 */
.action-options {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.action-option {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  border: 1.5px solid var(--el-border-color-lighter);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.15s;
  background: var(--el-bg-color);

  .action-icon {
    width: 34px;
    height: 34px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 19px;
    flex-shrink: 0;
  }

  .action-info {
    flex: 1;
    min-width: 0;
  }

  .action-title {
    font-size: 13.5px;
    font-weight: 600;
    color: var(--text-primary);
    line-height: 1.4;
  }

  .action-desc {
    margin-top: 2px;
    font-size: 11.5px;
    color: var(--text-secondary);
    line-height: 1.45;
  }

  .action-check {
    font-size: 17px;
    flex-shrink: 0;
    opacity: 0;
    transition: opacity 0.15s;

    &.visible {
      opacity: 1;
    }
  }

  &.is-approve {
    .action-icon {
      background: var(--color-success-50, #ecfdf5);
      color: var(--color-success-500, #10b981);
    }
    .action-check {
      color: var(--color-success-500, #10b981);
    }

    &:hover {
      border-color: var(--color-success-500, #10b981);
    }
    &.active {
      border-color: var(--color-success-500, #10b981);
      background: var(--color-success-50, #ecfdf5);
    }
  }

  &.is-reject {
    .action-icon {
      background: var(--color-danger-50, #fef2f2);
      color: var(--color-danger-500, #ef4444);
    }
    .action-check {
      color: var(--color-danger-500, #ef4444);
    }

    &:hover {
      border-color: var(--color-danger-500, #ef4444);
    }
    &.active {
      border-color: var(--color-danger-500, #ef4444);
      background: var(--color-danger-50, #fef2f2);
    }
  }
}
</style>
