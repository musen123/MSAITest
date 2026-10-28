<template>
  <el-dialog
    v-model="visible"
    :title="isBatch ? `批量评审（${cases.length} 条）` : '用例评审'"
    width="520px"
    :close-on-click-modal="false"
    @open="handleOpen"
  >
    <div class="review-dialog">
      <!-- 单条：用例信息条 -->
      <div v-if="!isBatch && cases[0]" class="case-target">
        <div class="case-icon">
          <i class="i-app-test-case" />
        </div>
        <div class="case-info">
          <div class="case-code">
            {{ cases[0].code || `#${cases[0].id}` }}
          </div>
          <div class="case-title">{{ cases[0].title }}</div>
        </div>
      </div>

      <!-- 批量：数量摘要条 -->
      <div v-else class="case-target is-batch">
        <div class="case-icon">
          <i class="i-solar-checklist-minimalistic-bold" />
        </div>
        <div class="case-info">
          <div class="case-title">已选中 {{ cases.length }} 条用例</div>
          <div class="case-code">评审结果将统一应用到全部选中用例</div>
        </div>
      </div>

      <!-- 评审结果（卡片二选） -->
      <div class="section-label">评审结果</div>
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
            <div class="action-desc">评审通过，用例进入「已评审」状态</div>
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
            <div class="action-desc">退回草稿，调整后需重新提交评审</div>
          </div>
          <i
            class="i-solar-check-circle-bold action-check"
            :class="{ visible: action === 'reject' }"
          />
        </div>
      </div>

      <!-- 评审意见 -->
      <div class="section-label">
        评审意见
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
 * 功能用例评审弹框（用例列表页待评审 tab / 详情页共用）
 *
 * 传 1 条 = 单条评审，传多条 = 批量评审；
 * 提交成功后 emit('reviewed') 由父组件刷新列表与统计。
 */
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { funcTestCaseApi } from '@/api/funcTest'
import type { FuncTestCase } from '@/types/func-test'

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    projectId: number
    cases: FuncTestCase[]
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

const isBatch = computed(() => props.cases.length > 1)
const action = ref<'approve' | 'reject'>('approve')
const comment = ref('')
const submitting = ref(false)

function handleOpen() {
  action.value = props.initialAction
  comment.value = ''
}

async function handleSubmit() {
  const first = props.cases[0]
  if (!first) return
  submitting.value = true
  try {
    const payload = {
      action: action.value,
      review_comment: comment.value || undefined,
    }
    if (isBatch.value) {
      const res = await funcTestCaseApi.batchReview(props.projectId, {
        ...payload,
        case_ids: props.cases.map((c) => c.id),
      })
      ElMessage.success(
        `已${action.value === 'approve' ? '通过' : '驳回'} ${res.data.reviewed} 条用例`,
      )
    } else {
      await funcTestCaseApi.review(props.projectId, first.id, payload)
      ElMessage.success(action.value === 'approve' ? '已通过' : '已驳回')
    }
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

/* 用例信息条 */
.case-target {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  background: var(--el-fill-color-light);
  border-radius: 10px;

  .case-icon {
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

  &.is-batch .case-icon {
    background: var(--color-warning-50);
    color: var(--color-warning-600);
  }

  .case-info {
    flex: 1;
    min-width: 0;
  }

  .case-code {
    font-family: 'JetBrains Mono', Menlo, monospace;
    font-size: 12px;
    color: var(--text-secondary);
    line-height: 1.4;
  }

  .case-title {
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

/* 评审结果卡片 */
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
