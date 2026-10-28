<template>
  <div class="llm-config-view">
    <!-- 页头 -->
    <div class="page-header">
      <div class="page-title">
        <div class="title-row">
          <i class="i-solar-cpu-bolt-bold title-icon" />
          <h2>大模型配置</h2>
        </div>
        <p class="page-description">为不同 AI 功能分别配置模型，所有 AI 调用将优先使用您的个人配置</p>
      </div>
    </div>

    <!-- 模型类型 Tab -->
    <div class="model-tabs">
      <div
        v-for="mt in modelTypes"
        :key="mt.value"
        class="model-tab"
        :class="{ active: activeModelType === mt.value }"
        @click="onTabChange(mt.value)"
      >
        <i :class="mt.icon" class="tab-icon" />
        <span class="tab-text">{{ mt.label }}</span>
        <span v-if="(configMap[mt.value]?.length || 0) > 0" class="tab-badge">{{ configMap[mt.value].length }}</span>
      </div>
    </div>

    <!-- 内容区 -->
    <div class="content-wrapper">
      <!-- 加载中 -->
      <div v-if="loading" class="loading-state">
        <el-skeleton :rows="6" animated />
      </div>

      <!-- 已配置：多配置列表 -->
      <template v-else-if="currentConfigs.length">
        <div class="list-toolbar">
          <div class="toolbar-info">
            <i :class="currentTypeMeta?.icon" class="toolbar-icon" />
            <div class="toolbar-text">
              <div class="toolbar-title">{{ currentTypeLabel }}（{{ currentConfigs.length }}）</div>
              <div class="toolbar-desc">{{ currentTypeMeta?.desc }} · 运行时使用「默认」那条，可随时切换</div>
            </div>
          </div>
          <el-button type="primary" @click="openCreate">
            <i class="i-solar-add-circle-bold" />
            新增配置
          </el-button>
        </div>

        <div class="config-list">
          <AppSectionCard
            v-for="cfg in currentConfigs"
            :key="cfg.id"
            class="config-item"
            :class="{ 'is-default': cfg.is_default }"
          >
            <div class="config-row">
              <div class="config-main">
                <div class="config-name-line">
                  <span class="config-alias">{{ cfg.name || cfg.model }}</span>
                  <el-tag v-if="cfg.is_default" type="success" size="small" effect="dark" class="default-tag">
                    <i class="i-solar-star-bold" /> 默认
                  </el-tag>
                  <el-tag size="small" effect="plain" class="provider-tag">{{ displayProviderName(cfg) }}</el-tag>
                </div>
                <div class="config-meta">
                  <span class="meta-item"><span class="meta-k">模型</span>{{ cfg.model }}</span>
                  <span class="meta-item"><span class="meta-k">Key</span><span class="mono">{{ cfg.api_key }}</span></span>
                  <span v-if="cfg.base_url" class="meta-item"><span class="meta-k">Base URL</span><span class="small">{{ cfg.base_url }}</span></span>
                </div>
              </div>
              <div class="config-ops">
                <el-button
                  v-if="!cfg.is_default"
                  size="small"
                  type="primary"
                  plain
                  :loading="settingDefaultId === cfg.id"
                  @click="handleSetDefault(cfg)"
                >
                  <i class="i-solar-star-line-duotone" />
                  设为默认
                </el-button>
                <el-button size="small" :loading="quickTestingId === cfg.id" @click="handleQuickTest(cfg)">
                  <i class="i-solar-bolt-circle-bold" />
                  检测
                </el-button>
                <el-button size="small" @click="openEdit(cfg)">
                  <i class="i-solar-pen-2-bold" />
                  编辑
                </el-button>
                <el-popconfirm
                  :title="`确定删除配置「${cfg.name || cfg.model}」吗？${cfg.is_default && currentConfigs.length > 1 ? '删除后将自动指定另一条为默认。' : ''}`"
                  confirm-button-text="确定删除"
                  cancel-button-text="取消"
                  confirm-button-type="danger"
                  width="240"
                  @confirm="handleDelete(cfg)"
                >
                  <template #reference>
                    <el-button size="small" type="danger" plain :loading="deletingId === cfg.id">
                      <i class="i-solar-trash-bin-trash-bold" />
                      删除
                    </el-button>
                  </template>
                </el-popconfirm>
              </div>
            </div>
          </AppSectionCard>
        </div>
      </template>

      <!-- 未配置 -->
      <div v-else class="no-config">
        <div class="no-config-inner">
          <img :src="configIllustration" alt="AI Model" class="no-config-img" />
          <h3>尚未配置{{ currentTypeLabel }}</h3>
          <p>配置后即可使用 AI 智能功能，可添加多个并随时切换默认</p>
          <el-button type="primary" size="large" @click="openCreate">
            <i class="i-solar-add-circle-bold" />
            立即配置
          </el-button>
        </div>
      </div>
    </div>

    <!-- 底部配置说明 -->
    <div class="config-notice">
      <i class="i-solar-info-circle-bold" />
      <span>配置保存后立即生效，所有 AI 功能将优先使用您的个人配置。如需帮助请参考文档。</span>
      <a href="javascript:void(0)" class="notice-link">查看配置文档</a>
    </div>

    <!-- 配置弹框 -->
    <el-dialog
      v-model="showForm"
      :width="720"
      :close-on-click-modal="false"
      destroy-on-close
      align-center
      class="config-dialog"
    >
      <!-- 自定义标题 -->
      <template #header="{ titleId, titleClass }">
        <span :id="titleId" :class="titleClass">
          <i class="i-solar-cpu-bolt-bold" />
          <span>{{ editingId ? '修改' : '新增' }}{{ currentTypeLabel }}</span>
        </span>
      </template>

      <!-- OpenAI / Anthropic Tab -->
      <el-tabs v-model="activeApiTab" class="api-tabs" @tab-change="onApiTabChange">
        <el-tab-pane label="兼容 OpenAI" name="openai" />
        <el-tab-pane v-if="activeModelType === 'text'" label="兼容 Anthropic" name="anthropic" />
      </el-tabs>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        class="config-form"
      >
        <el-form-item label="配置别名">
          <el-input v-model="form.name" placeholder="可选，便于区分多个配置，如「DeepSeek 主力」" clearable maxlength="100" />
        </el-form-item>

        <el-form-item label="模型名称" prop="model">
          <el-input v-model="form.model" placeholder="请输入或从下方快捷配置中选择" clearable />
        </el-form-item>

        <el-form-item label="API Key" prop="api_key">
          <el-input
            v-model="form.api_key"
            type="password"
            show-password
            placeholder="请输入 API Key"
            autocomplete="new-password"
          />
        </el-form-item>

        <el-form-item label="Base URL">
          <el-input
            v-model="form.base_url"
            :placeholder="activeApiTab === 'anthropic' ? '可选，使用代理时填写' : '必填，接口服务地址'"
            clearable
          />
        </el-form-item>

        <!-- 视觉模型专属：Midscene 模型家族（App 自动化视觉定位必填） -->
        <el-form-item v-if="activeModelType === 'vision'" label="模型家族（App 自动化）">
          <el-select
            v-model="form.model_family"
            placeholder="App 自动化视觉定位必选；家族配错会导致坐标偏移"
            clearable
            filterable
            style="width: 100%"
          >
            <el-option v-for="f in MIDSCENE_FAMILIES" :key="f" :label="f" :value="f" />
          </el-select>
          <div class="family-hint">
            仅 App 自动化（Midscene）使用：豆包 Seed 系选 doubao-seed，通义选
            qwen3-vl / qwen2.5-vl，智谱选 glm-v。其他功能不受影响，可留空。
          </div>
        </el-form-item>

        <!-- 快捷配置 -->
        <div class="preset-section">
          <div class="preset-title">
            <i class="i-solar-bolt-circle-bold" />
            <span>快捷配置</span>
            <span class="preset-hint">点击自动填写服务地址和推荐模型</span>
          </div>

          <div class="preset-grid">
            <div
              v-for="preset in currentPresets"
              :key="preset.name"
              class="preset-card"
              :class="{ active: selectedPreset === preset.name }"
              @click="applyPreset(preset)"
            >
              <div class="preset-logo">{{ preset.logo }}</div>
              <div class="preset-info">
                <div class="preset-name">{{ preset.name }}</div>
              </div>
            </div>
          </div>

          <el-alert
            v-if="selectedPresetData?.warn"
            :title="selectedPresetData.warn"
            type="warning"
            show-icon
            :closable="false"
            class="preset-warn"
          />

          <div v-if="selectedPresetData?.models.length" class="model-chips">
            <span class="model-chips-label">推荐模型：</span>
            <el-tag
              v-for="m in selectedPresetData.models"
              :key="m"
              size="small"
              class="model-chip"
              :type="form.model === m ? 'primary' : 'info'"
              effect="plain"
              style="cursor:pointer"
              @click="form.model = m"
            >{{ m }}</el-tag>
          </div>
        </div>
      </el-form>

      <template #footer>
        <div class="dialog-footer">
          <div class="footer-left">
            <el-button :loading="testing" @click="handleTestConnection">
              <i v-if="!testing" class="i-solar-bolt-circle-bold" />
              {{ testing ? '验证中...' : '验证连接' }}
            </el-button>
            <el-tag
              v-if="testResult"
              :type="testResult.success ? 'success' : 'danger'"
              effect="light"
              class="test-result-tag"
            >
              <i v-if="testResult.success" class="i-solar-check-circle-bold" />
              {{ testResult.message }}
              <span v-if="testResult.latency_ms > 0" class="latency">（{{ testResult.latency_ms }}ms）</span>
            </el-tag>
          </div>
          <div class="footer-right">
            <el-button @click="showForm = false">取消</el-button>
            <el-button type="primary" :loading="saving" @click="handleSave">
              <i class="i-solar-check-circle-bold" />
              保存配置
            </el-button>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import {
  llmConfigApi,
  type LlmConfigData,
  type LlmConfigForm,
  type LlmConfigUpdateForm,
  type TestConnectionForm,
  type ModelType,
  type TestConnectionResult,
} from '@/api/llmConfig'
import AppSectionCard from '@/components/common/AppSectionCard.vue'

// ==================== 静态资源 ====================

const configIllustration = new URL('@/assets/illustrations/ai-chat.svg', import.meta.url).href

// ==================== 模型类型定义 ====================

const modelTypes = [
  { value: 'text' as ModelType, label: '文本模型', icon: 'i-solar-chat-round-dots-bold', desc: '用于对话、内容生成等 AI 功能' },
  { value: 'embed' as ModelType, label: '嵌入模型', icon: 'i-solar-link-round-bold', desc: '用于语义搜索、向量检索等功能' },
  { value: 'vision' as ModelType, label: '视觉模型', icon: 'i-solar-eye-bold', desc: '用于图片理解、截图分析等功能' },
  { value: 'rerank' as ModelType, label: '重排模型', icon: 'i-solar-sort-vertical-bold', desc: '用于知识库深度检索重排（OpenAI 兼容 /rerank）' },
]

// ==================== 预设 ====================

interface Preset {
  name: string
  logo: string
  desc: string
  provider: string
  base_url: string
  models: string[]
  warn?: string
  types?: ModelType[]
}

const allPresets: Preset[] = [
  {
    name: 'DeepSeek',
    logo: '🤖',
    desc: '深度求索 V4，高性能低成本',
    provider: 'openai',
    base_url: 'https://api.deepseek.com',
    // chat/reasoner 为兼容别名，2026-07-24 后下线，新接入请用 v4-pro / v4-flash
    models: ['deepseek-v4-pro', 'deepseek-v4-flash', 'deepseek-chat', 'deepseek-reasoner'],
    types: ['text'],
  },
  {
    name: '硅基流动',
    logo: '⚡',
    desc: 'SiliconFlow，聚合多家开源模型',
    provider: 'openai',
    base_url: 'https://api.siliconflow.cn/v1',
    models: ['deepseek-ai/DeepSeek-V4-Pro', 'Qwen/Qwen3.6-35B-A3B', 'deepseek-ai/DeepSeek-V3.2', 'BAAI/bge-m3', 'BAAI/bge-large-zh-v1.5'],
  },
  {
    name: 'MiniMax',
    logo: '🌟',
    desc: 'MiniMax M3，软件工程 / Agent 能力领先',
    provider: 'openai',
    base_url: 'https://api.minimaxi.com/v1',
    models: ['MiniMax-M3', 'MiniMax-M2.7', 'MiniMax-M2.7-highspeed', 'MiniMax-M2.5'],
    types: ['text'],
  },
  {
    name: '火山方舟',
    logo: '🔥',
    desc: '字节跳动豆包 Seed 2.0，原生多模态',
    provider: 'openai',
    base_url: 'https://ark.cn-beijing.volces.com/api/v3',
    models: ['doubao-seed-2.0-pro', 'doubao-seed-2.0-code', 'doubao-seed-2.0-lite', 'doubao-embedding-large', 'doubao-embedding'],
  },
  {
    name: 'Kimi',
    logo: '🌙',
    desc: '月之暗面 Kimi K2.6 / K2.7，多模态 + Agent',
    provider: 'openai',
    base_url: 'https://api.moonshot.cn/v1',
    models: ['kimi-k2.6', 'kimi-k2.7-code', 'kimi-k2.5', 'moonshot-v1-128k', 'moonshot-v1-128k-vision-preview'],
  },
  {
    name: '通义千问',
    logo: '🎯',
    desc: '阿里云通义千问，全模态 + 长上下文',
    provider: 'openai',
    base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    models: ['qwen-max', 'qwen-plus', 'qwen-flash', 'qwen-vl-max', 'text-embedding-v4'],
  },
  {
    name: '智谱 GLM',
    logo: '🧠',
    desc: '清华智谱 GLM-4.7，代码与推理强',
    provider: 'openai',
    base_url: 'https://open.bigmodel.cn/api/paas/v4',
    models: ['glm-4.7', 'glm-4.6', 'glm-4.6v', 'embedding-3'],
  },
  {
    name: 'OpenAI',
    logo: '🌐',
    desc: 'OpenAI GPT-5.5 新版发布，需境外访问',
    provider: 'openai',
    base_url: 'https://api.openai.com/v1',
    models: ['gpt-5.5', 'gpt-5.4', 'gpt-5.4-mini', 'text-embedding-3-large', 'text-embedding-3-small'],
    warn: '需要服务器配置固定 IP 的 VPN 代理，使用非固定 IP 存在封号风险',
  },
  {
    name: 'Claude 官方',
    logo: '🤿',
    desc: 'Anthropic 直连，需境外访问',
    provider: 'anthropic',
    base_url: '',
    models: ['claude-opus-4-8', 'claude-sonnet-4-6', 'claude-haiku-4-5-20251001', 'claude-fable-5', 'claude-opus-4-7'],
    warn: '需要服务器配置固定 IP 的 VPN 代理，使用非固定 IP 存在封号风险',
    types: ['text'],
  },
  {
    name: 'Claude 代理',
    logo: '🔀',
    desc: '通过代理访问 Claude API',
    provider: 'anthropic',
    base_url: '',
    models: ['claude-opus-4-8', 'claude-sonnet-4-6', 'claude-haiku-4-5-20251001', 'claude-fable-5', 'claude-opus-4-7'],
    types: ['text'],
  },
]

// ==================== 状态 ====================

const loading = ref(false)
const saving = ref(false)
const showForm = ref(false)
const activeModelType = ref<ModelType>('text')
const activeApiTab = ref<'openai' | 'anthropic'>('openai')
const selectedPreset = ref('')
const configMap = ref<Record<string, LlmConfigData[]>>({ text: [], embed: [], vision: [] })
const formRef = ref<FormInstance>()
// 当前编辑的配置 id：null 表示新增
const editingId = ref<number | null>(null)
// 各行操作的 loading（按 id 区分，避免整列表 loading）
const deletingId = ref<number | null>(null)
const settingDefaultId = ref<number | null>(null)
const quickTestingId = ref<number | null>(null)

const form = ref<LlmConfigForm>({
  model_type: 'text',
  name: '',
  provider: 'openai',
  model: '',
  api_key: '',
  base_url: '',
  model_family: '',
})

/** Midscene 支持的模型家族（闭集，App 自动化视觉定位用；配错=坐标静默偏移） */
const MIDSCENE_FAMILIES = [
  'doubao-seed', 'doubao-vision', 'qwen3-vl', 'qwen2.5-vl', 'glm-v', 'auto-glm',
  'gemini', 'vlm-ui-tars', 'vlm-ui-tars-doubao', 'gpt-5', 'kimi', 'xiaomi-mimo',
]

const rules: FormRules = {
  model: [{ required: true, message: '请输入模型名称', trigger: 'blur' }],
  api_key: [{ required: true, message: '请输入 API Key', trigger: 'blur' }],
}

const testing = ref(false)
const testResult = ref<TestConnectionResult | null>(null)

// ==================== 计算属性 ====================

const currentConfigs = computed<LlmConfigData[]>(() => configMap.value[activeModelType.value] ?? [])
const currentTypeMeta = computed(() => modelTypes.find(m => m.value === activeModelType.value))
const currentTypeLabel = computed(() => currentTypeMeta.value?.label ?? '')

const currentPresets = computed<Preset[]>(() => {
  return allPresets.filter((p) => {
    if (activeApiTab.value === 'anthropic') return p.provider === 'anthropic'
    if (p.provider === 'anthropic') return false
    if (!p.types) return true
    return p.types.includes(activeModelType.value)
  })
})

const selectedPresetData = computed<Preset | undefined>(() =>
  allPresets.find((p) => p.name === selectedPreset.value)
)

// ==================== 方法 ====================

function displayProviderName(config: LlmConfigData) {
  if (config.provider === 'anthropic') return 'Anthropic Claude'
  if (!config.base_url) return 'OpenAI'
  const match = allPresets.find((p) => {
    if (!p.base_url) return false
    const host = p.base_url.replace('https://', '').split('/')[0]
    return host && config.base_url?.includes(host)
  })
  return match?.name ?? 'OpenAI 兼容'
}

function onTabChange(type: ModelType) {
  activeModelType.value = type
  showForm.value = false
  selectedPreset.value = ''
  testResult.value = null
}

function onApiTabChange() {
  selectedPreset.value = ''
  form.value.model = ''
  form.value.base_url = ''
  form.value.provider = activeApiTab.value
}

function applyPreset(preset: Preset) {
  selectedPreset.value = preset.name
  form.value.provider = preset.provider
  form.value.base_url = preset.base_url
  if (preset.models.length) form.value.model = preset.models[0] ?? ''
}

function resetForm() {
  form.value = {
    model_type: activeModelType.value,
    name: '',
    provider: 'openai',
    model: '',
    api_key: '',
    base_url: '',
    model_family: '',
  }
  selectedPreset.value = ''
  testResult.value = null
}

function openCreate() {
  editingId.value = null
  activeApiTab.value = 'openai'
  resetForm()
  showForm.value = true
}

async function openEdit(cfg: LlmConfigData) {
  editingId.value = cfg.id
  activeApiTab.value = cfg.provider === 'anthropic' ? 'anthropic' : 'openai'
  form.value = {
    model_type: cfg.model_type,
    name: cfg.name ?? '',
    provider: cfg.provider,
    model: cfg.model,
    api_key: '',
    base_url: cfg.base_url ?? '',
    model_family: cfg.model_family ?? '',
  }
  selectedPreset.value = ''
  testResult.value = null
  showForm.value = true
  try {
    const res = await llmConfigApi.getFull(cfg.id)
    if (res.data?.api_key) form.value.api_key = res.data.api_key
  } catch { /* ignore */ }
}

async function fetchAllConfigs() {
  loading.value = true
  try {
    const res = await llmConfigApi.list()
    const map: Record<string, LlmConfigData[]> = { text: [], embed: [], vision: [] }
    for (const c of res.data ?? []) (map[c.model_type] ??= []).push(c)
    configMap.value = map
  } catch {
    // ignore
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  if (!testResult.value?.success) {
    ElMessage.warning('请先点击"验证连接"并通过测试，再保存配置')
    return
  }

  saving.value = true
  try {
    if (editingId.value) {
      const payload: LlmConfigUpdateForm = {
        name: form.value.name || null,
        provider: form.value.provider,
        model: form.value.model,
        api_key: form.value.api_key,
        base_url: form.value.base_url || '',
      }
      if (activeModelType.value === 'vision') {
        payload.model_family = form.value.model_family || null
      }
      await llmConfigApi.update(editingId.value, payload)
    } else {
      const payload: LlmConfigForm = {
        model_type: activeModelType.value,
        provider: form.value.provider,
        model: form.value.model,
        api_key: form.value.api_key,
      }
      if (form.value.name) payload.name = form.value.name
      if (form.value.base_url) payload.base_url = form.value.base_url
      if (activeModelType.value === 'vision' && form.value.model_family) {
        payload.model_family = form.value.model_family
      }
      await llmConfigApi.create(payload)
    }
    showForm.value = false
    ElMessage.success(editingId.value ? '配置已更新' : '配置已创建')
    await fetchAllConfigs()
  } catch (e) {
    console.error('保存大模型配置失败', e)
  } finally {
    saving.value = false
  }
}

async function handleSetDefault(cfg: LlmConfigData) {
  settingDefaultId.value = cfg.id
  try {
    await llmConfigApi.setDefault(cfg.id)
    ElMessage.success('已设为默认')
    await fetchAllConfigs()
  } catch (e) {
    console.error('设置默认失败', e)
  } finally {
    settingDefaultId.value = null
  }
}

async function handleDelete(cfg: LlmConfigData) {
  deletingId.value = cfg.id
  try {
    await llmConfigApi.remove(cfg.id)
    ElMessage.success('配置已删除')
    await fetchAllConfigs()
  } catch (e) {
    console.error('删除大模型配置失败', e)
  } finally {
    deletingId.value = null
  }
}

async function handleTestConnection() {
  if (!form.value.model || !form.value.api_key) {
    ElMessage.warning('请先填写模型名称和 API Key')
    return
  }
  testing.value = true
  testResult.value = null
  try {
    const payload: TestConnectionForm = {
      model_type: activeModelType.value,
      provider: form.value.provider,
      model: form.value.model,
      api_key: form.value.api_key,
    }
    if (form.value.base_url) payload.base_url = form.value.base_url
    const res = await llmConfigApi.testConnection(payload)
    testResult.value = res.data
    if (res.data?.success) {
      ElMessage.success({ message: res.data.message || '连接成功', duration: 3000 })
    } else {
      ElMessage.error({ message: res.data?.message || '连接失败', duration: 5000 })
    }
  } catch {
    testResult.value = { success: false, message: '请求失败，请检查网络', latency_ms: 0 }
  } finally {
    testing.value = false
  }
}

// 对已保存的某条配置做连通性检测：先取完整 key 再测
async function handleQuickTest(cfg: LlmConfigData) {
  quickTestingId.value = cfg.id
  try {
    const full = await llmConfigApi.getFull(cfg.id)
    const apiKey = full.data?.api_key
    if (!apiKey) {
      ElMessage.error('无法获取该配置的 API Key')
      return
    }
    const payload: TestConnectionForm = {
      model_type: cfg.model_type,
      provider: cfg.provider,
      model: cfg.model,
      api_key: apiKey,
    }
    if (cfg.base_url) payload.base_url = cfg.base_url
    const res = await llmConfigApi.testConnection(payload)
    if (res.data?.success) {
      ElMessage.success(`「${cfg.name || cfg.model}」连接正常${res.data.latency_ms ? `（${res.data.latency_ms}ms）` : ''}`)
    } else {
      ElMessage.error(res.data?.message || '连接异常')
    }
  } catch {
    ElMessage.error('检测请求失败')
  } finally {
    quickTestingId.value = null
  }
}

onMounted(fetchAllConfigs)
</script>

<style lang="scss" scoped>
.llm-config-view {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

// ==================== 页头 ====================

.page-header {
  h2 {
    font-size: 22px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0 0 4px;
  }

  .page-description {
    font-size: 14px;
    color: var(--text-secondary);
    margin: 0;
  }
}

// ==================== 标题图标 ====================
.title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.title-icon {
  font-size: 22px;
  color: var(--brand-500);
}

// ==================== 模型 Tab ====================

.model-tabs {
  display: flex;
  gap: 12px;
}

.model-tab {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  border-radius: 10px;
  background: var(--bg-card);
  border: 1.5px solid var(--border-light);
  cursor: pointer;
  transition: all 0.2s;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-regular);

  &:hover {
    border-color: var(--brand-300);
    background: var(--brand-50);
  }

  &.active {
    border-color: var(--brand-500);
    background: var(--brand-50);
    color: var(--brand-700);
    box-shadow: 0 0 0 3px var(--brand-100);
  }

  .tab-icon {
    font-size: 16px;
  }

  .tab-badge {
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 10px;
    background: var(--color-success-100, #dcfce7);
    color: var(--color-success-600, #16a34a);
    font-weight: 600;
  }
}

// ==================== 内容区 ====================

.content-wrapper {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.loading-state {
  padding: 20px;
}

// ==================== 多配置列表 ====================

.list-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;

  .toolbar-info {
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: 0;
  }

  .toolbar-icon {
    font-size: 22px;
    color: var(--brand-500, #16a34a);
    flex-shrink: 0;
  }

  .toolbar-title {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
  }

  .toolbar-desc {
    font-size: 12px;
    color: var(--text-placeholder);
    margin-top: 2px;
  }
}

.config-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.config-item {
  transition: border-color 0.2s, box-shadow 0.2s;

  &.is-default {
    border-color: var(--color-success-500, #22c55e);
    box-shadow: 0 0 0 1px var(--color-success-500, #22c55e) inset;
  }
}

.config-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.config-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.config-name-line {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;

  .config-alias {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
    word-break: break-all;
  }

  .default-tag i {
    margin-right: 2px;
  }
}

.config-meta {
  display: flex;
  align-items: center;
  gap: 18px;
  flex-wrap: wrap;
  font-size: 13px;
  color: var(--text-secondary, var(--text-primary));

  .meta-item {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
    word-break: break-all;
  }

  .meta-k {
    font-size: 12px;
    color: var(--text-placeholder);
  }

  .mono {
    font-family: 'SF Mono', 'Fira Code', monospace;
    letter-spacing: 0.5px;
  }

  .small {
    font-size: 12px;
    color: var(--text-placeholder);
  }
}

.config-ops {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  flex-wrap: wrap;
}

// ==================== 当前配置卡片 ====================

.current-config {
  display: flex;
  gap: 28px;
  align-items: flex-start;
}

.config-illustration {
  flex-shrink: 0;
  width: 180px;
  height: 160px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  overflow: hidden;

  img {
    width: 140px;
    height: 140px;
    object-fit: contain;
  }
}

.config-detail {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.config-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px 14px;
  background: var(--bg-hover, #f8fafc);
  border-radius: 10px;
  border: 1px solid var(--border-lighter, var(--border-light));
}

.field-label {
  font-size: 12px;
  color: var(--text-placeholder);
  font-weight: 500;
}

.field-value {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
  word-break: break-all;
  min-width: 0;

  &.mono {
    font-family: 'SF Mono', 'Fira Code', monospace;
    letter-spacing: 0.5px;
  }

  &.small {
    font-size: 12px;
  }
}

.field-check {
  color: var(--color-success-500, #22c55e);
  font-size: 14px;
  flex-shrink: 0;
}

.field-action {
  background: none;
  border: none;
  padding: 2px;
  cursor: pointer;
  color: var(--text-placeholder);
  font-size: 14px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  border-radius: 4px;
  transition: color 0.2s;

  &:hover {
    color: var(--brand-500);
  }
}

.config-actions {
  display: flex;
  gap: 12px;
  padding-top: 4px;
}

// ==================== 状态与使用信息 ====================

.status-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.status-card-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.status-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;

  &.success {
    color: var(--color-success-600, #16a34a);
  }

  &.error {
    color: var(--color-danger-500, #ef4444);
  }

  > i {
    font-size: 18px;
  }
}

.status-time {
  font-size: 12px;
  color: var(--text-placeholder);
}

.status-metrics {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.metric-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 12px 8px;
  background: var(--bg-hover, #f8fafc);
  border-radius: 8px;
}

.metric-label {
  font-size: 12px;
  color: var(--text-placeholder);
}

.metric-value {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);

  &.text-success {
    color: var(--color-success-500, #22c55e);
  }

  &.text-danger {
    color: var(--color-danger-500, #ef4444);
  }
}

.status-footer {
  display: flex;
  justify-content: flex-start;
}

// ==================== 使用信息卡 ====================

.usage-card-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.usage-main {
  display: flex;
  gap: 24px;
  align-items: center;
}

.usage-ring {
  flex-shrink: 0;

  .ring-text {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
  }

  .ring-value {
    font-size: 18px;
    font-weight: 700;
    color: var(--text-primary);
  }

  .ring-label {
    font-size: 11px;
    color: var(--text-placeholder);
  }
}

.usage-stats {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
}

.usage-stat {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: var(--bg-hover, #f8fafc);
  border-radius: 8px;

  .stat-label {
    font-size: 13px;
    color: var(--text-secondary);
  }

  .stat-value {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
  }
}

.usage-bar-section {
  .usage-bar-header {
    display: flex;
    justify-content: space-between;
    font-size: 13px;
    color: var(--text-secondary);
    margin-bottom: 6px;

    .usage-bar-percent {
      font-weight: 600;
      color: var(--brand-500);
    }
  }
}

// ==================== 未配置 ====================

.no-config {
  padding: 40px 0;

  .no-config-inner {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    text-align: center;

    .no-config-img {
      width: 120px;
      height: 120px;
      object-fit: contain;
      opacity: 0.6;
      margin-bottom: 8px;
    }

    h3 {
      font-size: 16px;
      font-weight: 600;
      color: var(--text-primary);
      margin: 0;
    }

    p {
      font-size: 14px;
      color: var(--text-secondary);
      margin: 0;
    }
  }
}

// ==================== 底部说明 ====================

.config-notice {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: var(--brand-50, #eff6ff);
  border: 1px solid var(--brand-100, #dbeafe);
  border-radius: 10px;
  font-size: 13px;
  color: var(--brand-700, #1d4ed8);

  > i {
    font-size: 16px;
    flex-shrink: 0;
  }

  .notice-link {
    margin-left: auto;
    flex-shrink: 0;
    color: var(--brand-500);
    font-weight: 500;
    text-decoration: none;

    &:hover {
      text-decoration: underline;
    }
  }
}

// ==================== 弹框 ====================

:deep(.config-dialog) {
  border-radius: 14px;
  overflow: hidden;
}

.api-tabs {
  margin-bottom: 4px;
}

.config-form {
  :deep(.el-form-item) {
    margin-bottom: 16px;
  }

  :deep(.el-form-item__label) {
    padding: 0 0 6px;
    font-size: 13px;
    font-weight: 500;
    color: var(--text-regular);
  }

  :deep(.el-input__wrapper) {
    border-radius: 8px;
  }
}

/* 模型家族提示（vision 专属） */
.family-hint {
  margin-top: 4px;
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  line-height: 1.5;
}

.preset-section {
  background: var(--bg-hover, #f8fafc);
  border: 1px solid var(--border-light);
  border-radius: 10px;
  padding: 16px;
  margin-top: 4px;
}

.preset-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 14px;

  > i {
    color: var(--brand-500);
    font-size: 16px;
  }

  .preset-hint {
    font-size: 12px;
    color: var(--text-placeholder);
    font-weight: 400;
    margin-left: 4px;
  }
}

.preset-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.preset-card {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: var(--bg-card);
  border: 1.5px solid var(--border-light);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.18s ease;

  &:hover {
    border-color: var(--brand-300);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
    transform: translateY(-1px);
  }

  &.active {
    border-color: var(--brand-500);
    background: var(--brand-50);
    box-shadow: 0 0 0 2px var(--brand-100);
  }
}

.preset-logo {
  font-size: 20px;
  flex-shrink: 0;
}

.preset-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.preset-warn {
  margin-top: 12px;
}

.model-chips {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 12px;

  .model-chips-label {
    font-size: 12px;
    color: var(--text-placeholder);
  }
}

.dialog-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;

  .footer-left {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .footer-right {
    display: flex;
    gap: 10px;
  }

  .test-result-tag {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }

  .latency {
    opacity: 0.7;
    font-size: 12px;
  }
}
</style>
