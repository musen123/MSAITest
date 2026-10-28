<template>
  <div class="attachment-gallery">
    <div class="gallery-grid">
      <!-- 缩略图 -->
      <div
        v-for="(url, idx) in modelValue"
        :key="url"
        class="thumb-item"
      >
        <el-image
          :src="url"
          fit="cover"
          class="thumb"
          :preview-src-list="modelValue"
          :initial-index="idx"
          preview-teleported
          :z-index="3000"
        >
          <template #error>
            <div class="thumb-error">
              <el-icon><PictureFilled /></el-icon>
            </div>
          </template>
        </el-image>
        <div v-if="!readonly" class="thumb-overlay">
          <el-button
            type="danger"
            circle
            size="small"
            @click="handleRemove(idx)"
          >
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
      </div>

      <!-- 上传按钮 -->
      <el-upload
        v-if="!readonly"
        v-show="!uploading"
        class="upload-tile"
        :show-file-list="false"
        :accept="acceptedTypes"
        :before-upload="handleBeforeUpload"
      >
        <div class="upload-tile-content">
          <el-icon class="upload-icon"><Plus /></el-icon>
          <div class="upload-text">上传图片</div>
        </div>
      </el-upload>

      <!-- 上传中 -->
      <div v-if="uploading" class="upload-tile uploading">
        <el-icon class="rotating"><Loading /></el-icon>
        <div class="upload-text">上传中...</div>
      </div>
    </div>

    <div v-if="!readonly" class="gallery-hint">
      <el-icon><InfoFilled /></el-icon>
      仅支持图片（png/jpg/jpeg/gif/webp），单张最大 20MB。
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage, type UploadRawFile } from 'element-plus'
import {
  Plus,
  Delete,
  Loading,
  PictureFilled,
  InfoFilled,
} from '@element-plus/icons-vue'
import { funcRequirementApi } from '@/api/funcTest'

const props = withDefaults(
  defineProps<{
    modelValue: string[]
    projectId: number
    readonly?: boolean
  }>(),
  { readonly: false },
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: string[]): void
}>()

const acceptedTypes = '.png,.jpg,.jpeg,.gif,.webp'
const uploading = ref(false)

async function handleBeforeUpload(file: UploadRawFile): Promise<false> {
  // 校验
  const allowed = ['image/png', 'image/jpeg', 'image/gif', 'image/webp']
  if (!allowed.includes(file.type)) {
    ElMessage.error('仅支持 png / jpg / jpeg / gif / webp 格式')
    return false
  }
  if (file.size > 20 * 1024 * 1024) {
    ElMessage.error('图片大小不能超过 20MB')
    return false
  }

  // 上传
  uploading.value = true
  try {
    const res = await funcRequirementApi.uploadAttachment(props.projectId, file)
    const url = res.data.url
    emit('update:modelValue', [...props.modelValue, url])
    ElMessage.success('上传成功')
  } catch (err) {
    console.error(err)
  } finally {
    uploading.value = false
  }
  // 阻止默认上传行为
  return false
}

function handleRemove(idx: number) {
  const next = [...props.modelValue]
  next.splice(idx, 1)
  emit('update:modelValue', next)
}
</script>

<style scoped>
.attachment-gallery {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.gallery-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 12px;
}

.thumb-item {
  position: relative;
  aspect-ratio: 1;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--el-border-color-lighter);
}

.thumb {
  width: 100%;
  height: 100%;
  cursor: zoom-in;
}

.thumb-error {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--theme-color-f7f8fa);
  color: var(--el-text-color-disabled);
  font-size: 32px;
}

.thumb-overlay {
  position: absolute;
  top: 4px;
  right: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.thumb-item:hover .thumb-overlay {
  opacity: 1;
}

.upload-tile {
  aspect-ratio: 1;
  border: 1.5px dashed var(--el-text-color-disabled);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: border-color 0.2s, background-color 0.2s;
}

.upload-tile :deep(.el-upload) {
  width: 100%;
  height: 100%;
}

.upload-tile:hover {
  border-color: var(--el-color-info);
  background: var(--theme-color-f5f9ff);
}

.upload-tile.uploading {
  cursor: not-allowed;
  flex-direction: column;
  gap: 6px;
  color: var(--el-text-color-secondary);
}

.upload-tile-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  color: var(--el-text-color-secondary);
}

.upload-icon {
  font-size: 28px;
}

.upload-text {
  font-size: 12px;
}

.gallery-hint {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.rotating {
  animation: rotate 1.2s linear infinite;
  font-size: 22px;
}

@keyframes rotate {
  to {
    transform: rotate(360deg);
  }
}
</style>
