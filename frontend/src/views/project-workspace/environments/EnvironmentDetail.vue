<template>
  <div class="environment-detail">
    <!-- 页头 -->
    <AppPageHeader
      icon="i-solar-server-bold"
      :illustration="illustEnvironment"
      :title="environment?.name || '环境详情'"
      :breadcrumbs="['测试环境', '环境详情']"
    >
      <template #actions>
        <el-button text @click="handleBack">
          <i class="i-solar-arrow-left-linear btn-icon" />
          返回列表
        </el-button>
        <template v-if="!editing">
          <el-button v-permission="'environment:edit'" type="primary" @click="enterEdit">
            <i class="i-solar-pen-2-linear btn-icon" />
            编辑
          </el-button>
          <el-button
            v-if="!environment?.is_default"
            v-permission="'environment:edit'"
            @click="handleSetDefault"
          >
            <i class="i-solar-star-linear btn-icon" />
            设为默认
          </el-button>
          <el-button v-permission="'environment:create'" @click="handleClone">
            <i class="i-solar-copy-linear btn-icon" />
            克隆
          </el-button>
          <el-button
            v-permission="'environment:delete'"
            type="danger"
            :disabled="environment?.is_default"
            @click="handleDelete"
          >
            <i class="i-solar-trash-bin-trash-linear btn-icon" />
            删除
          </el-button>
        </template>
        <template v-else>
          <el-button @click="cancelEdit">取消</el-button>
          <el-button
            v-permission="'environment:edit'"
            type="primary"
            :loading="saving"
            @click="handleSaveBasic"
          >
            <i class="i-solar-check-circle-bold btn-icon" />
            保存
          </el-button>
        </template>
      </template>
    </AppPageHeader>

    <!-- 信息条 -->
    <div v-if="environment" class="env-info-bar">
      <span class="type-pill" :class="environment.env_type === 2 ? 'is-ui' : 'is-api'">
        {{ environment.env_type === 2 ? 'UI测试' : '接口测试' }}
      </span>
      <span v-if="environment.is_default" class="flag-pill is-default">默认环境</span>
      <span v-if="environment.is_global" class="flag-pill is-global">全局环境</span>
      <span class="bar-url">
        <i class="i-solar-link-linear" />
        {{ environment.base_url }}
      </span>
      <span class="bar-meta">
        <i class="i-solar-clock-circle-linear" />
        更新于 {{ formatDateTime(environment.updated_at) }}
      </span>
    </div>

    <!-- 全部数据：标签页 -->
    <AppSectionCard v-loading="loading" padless class="detail-card">
      <el-tabs v-model="activeTab" class="detail-tabs">
        <!-- 基本配置 -->
        <el-tab-pane label="基本配置" name="basic">
          <div class="tab-body">
            <!-- 查看模式 -->
            <div v-if="!editing" class="info-grid">
              <div class="info-item full-width">
                <label>基础 URL</label>
                <div class="info-value url-value">
                  <i class="i-solar-link-linear" />
                  <span>{{ environment?.base_url || '-' }}</span>
                </div>
              </div>
              <div class="info-item">
                <label>环境类型</label>
                <div class="info-value">{{ environment?.env_type === 2 ? 'UI测试' : '接口测试' }}</div>
              </div>
              <div class="info-item">
                <label>请求超时</label>
                <div class="info-value">{{ environment?.timeout || 30 }} 秒</div>
              </div>
              <div class="info-item">
                <label>代理 URL</label>
                <div class="info-value">{{ environment?.proxy_url || '未配置' }}</div>
              </div>
              <div class="info-item">
                <label>创建时间</label>
                <div class="info-value">{{ formatDateTime(environment?.created_at) }}</div>
              </div>
              <div class="info-item">
                <label>更新时间</label>
                <div class="info-value">{{ formatDateTime(environment?.updated_at) }}</div>
              </div>
              <div class="info-item full-width">
                <label>环境描述</label>
                <div class="info-value">{{ environment?.description || '暂无描述' }}</div>
              </div>
            </div>

            <!-- 编辑模式（内联，不弹框） -->
            <el-form
              v-else
              ref="basicFormRef"
              :model="editForm"
              :rules="basicRules"
              label-position="top"
              class="basic-form"
            >
              <el-form-item label="环境名称" prop="name">
                <el-input v-model="editForm.name" placeholder="请输入环境名称" maxlength="100" clearable />
              </el-form-item>
              <el-form-item label="基础 URL" prop="base_url">
                <el-input v-model="editForm.base_url" placeholder="https://api.example.com" clearable />
              </el-form-item>
              <el-form-item label="环境类型">
                <el-radio-group v-model="editForm.env_type">
                  <el-radio-button :value="1">接口测试</el-radio-button>
                  <el-radio-button :value="2">UI测试</el-radio-button>
                </el-radio-group>
              </el-form-item>
              <div class="form-row">
                <el-form-item label="请求超时(秒)">
                  <el-input-number v-model="editForm.timeout" :min="1" :max="300" controls-position="right" class="w-full" />
                </el-form-item>
                <el-form-item label="代理 URL">
                  <el-input v-model="editForm.proxy_url" placeholder="http://proxy:8080" clearable />
                </el-form-item>
              </div>
              <div class="form-row">
                <el-form-item label="设为默认">
                  <el-switch v-model="editForm.is_default" />
                </el-form-item>
                <el-form-item label="全局环境">
                  <el-switch v-model="editForm.is_global" />
                </el-form-item>
              </div>
              <el-form-item label="环境描述">
                <el-input v-model="editForm.description" type="textarea" :rows="3" maxlength="500" />
              </el-form-item>
            </el-form>
          </div>
        </el-tab-pane>

        <!-- 脚本配置 -->
        <el-tab-pane label="脚本配置" name="script">
          <div class="tab-body">
            <el-tabs v-model="activeScriptTab" class="script-tabs">
          <!-- 前置脚本 -->
          <el-tab-pane label="前置脚本" name="pre">
            <template #label>
              <div class="tab-label">
                <span>前置脚本</span>
                <el-tag
                  :type="environment?.pre_script?.is_active ? 'success' : 'info'"
                  size="small"
                >
                  {{ environment?.pre_script?.is_active ? '已启用' : '未启用' }}
                </el-tag>
              </div>
            </template>
            <div class="script-detail-content">
              <div class="script-header">
                <div class="script-meta">
                  <el-tag size="small" type="info">Python</el-tag>
                  <span class="script-desc">在使用该测试环境执行测试前执行的脚本，可用准备测试环境</span>
                </div>
                <el-button
                  v-if="!editingPreScript"
                  v-permission="'environment:edit'"
                  size="small"
                  @click="handleEditPreScript"
                >
                  编辑
                </el-button>
                <el-button
                  v-if="editingPreScript"
                  size="small"
                  @click="handleCancelPreScript"
                >
                  取消
                </el-button>
              </div>
              <div
                v-if="environment?.pre_script?.is_active || editingPreScript"
                class="script-editor-wrapper"
                :class="{ 'is-fullscreen': preScriptFullscreen }"
              >
                <div class="script-fullscreen-toggle">
                  <el-button
                    size="small"
                    circle
                    @click="preScriptFullscreen = !preScriptFullscreen"
                  >
                    <i v-if="preScriptFullscreen" class="i-solar-minimize-square-3-linear" />
                    <i v-else class="i-solar-maximize-square-3-linear" />
                  </el-button>
                </div>
                <CodeEditor
                  v-if="editingPreScript"
                  v-model="preScriptCode"
                  language="python"
                  :theme="isDark ? 'dark' : 'light'"
                  :min-height="'300px'"
                  :max-height="'500px'"
                  :show-line-count="true"
                />
                <CodeEditor
                  v-else
                  :model-value="environment?.pre_script?.code || ''"
                  language="python"
                  :theme="isDark ? 'dark' : 'light'"
                  :min-height="'300px'"
                  :max-height="'500px'"
                  :show-line-count="true"
                  :readonly="true"
                />
                <div class="script-debug-bar">
                  <el-dropdown
                    trigger="click"
                    @command="handleApplyPreTemplate"
                  >
                    <el-button size="small">
                      使用模板 <i class="i-solar-alt-arrow-down-bold" />
                    </el-button>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item command="login">登录获取Token</el-dropdown-item>
                        <el-dropdown-item command="db_query">数据库查询</el-dropdown-item>
                        <el-dropdown-item command="http_request">HTTP接口请求</el-dropdown-item>
                        <el-dropdown-item command="init_data">初始化测试数据</el-dropdown-item>
                        <el-dropdown-item command="full_setup">完整环境初始化</el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                  <el-button
                    v-if="editingPreScript"
                    type="primary"
                    size="small"
                    plain
                    @click="showPreInsertFunction = true"
                  >
                    插入函数
                  </el-button>
                  <el-button
                    v-if="editingPreScript"
                    type="success"
                    size="small"
                    plain
                    @click="showInsertEnvVarDialog = true"
                  >
                    保存变量
                  </el-button>
                  <el-button
                    type="warning"
                    size="small"
                    :loading="debuggingPreScript"
                    @click="handleDebugPreScript"
                  >
                    调试运行
                  </el-button>
                  <el-button
                    v-if="editingPreScript"
                    v-permission="'environment:edit'"
                    type="primary"
                    size="small"
                    :loading="savingPreScript"
                    @click="handleSavePreScript"
                  >
                    保存
                  </el-button>
                </div>
                <div v-if="preScriptDebugResult" class="script-debug-result">
                  <el-alert
                    :type="preScriptDebugResult.success ? 'success' : 'error'"
                    :title="preScriptDebugResult.success ? '脚本执行成功' : '脚本执行失败'"
                    show-icon
                    :closable="false"
                  />
                  <div v-if="preScriptDebugResult.output" class="debug-output">
                    <div class="debug-output-title">输出：</div>
                    <pre>{{ preScriptDebugResult.output }}</pre>
                  </div>
                  <div v-if="preScriptDebugResult.error" class="debug-output error">
                    <div class="debug-output-title">错误信息：</div>
                    <pre>{{ preScriptDebugResult.error }}</pre>
                  </div>
                  <div v-if="preScriptDebugResult.traceback" class="debug-output error">
                    <div class="debug-output-title">堆栈跟踪：</div>
                    <pre>{{ preScriptDebugResult.traceback }}</pre>
                  </div>
                  <div v-if="preScriptDebugResult.env_data && Object.keys(preScriptDebugResult.env_data).length" class="debug-output">
                    <div class="debug-output-title">环境变量快照：</div>
                    <pre>{{ JSON.stringify(preScriptDebugResult.env_data, null, 2) }}</pre>
                  </div>
                </div>
              </div>
              <div v-else class="script-empty-hint">
                <i class="i-solar-danger-triangle-bold" />
                <span>前置脚本未启用</span>
              </div>
            </div>
          </el-tab-pane>

          <!-- 后置脚本 -->
          <el-tab-pane label="后置脚本" name="post">
            <template #label>
              <div class="tab-label">
                <span>后置脚本</span>
                <el-tag
                  :type="environment?.post_script?.is_active ? 'success' : 'info'"
                  size="small"
                >
                  {{ environment?.post_script?.is_active ? '已启用' : '未启用' }}
                </el-tag>
              </div>
            </template>
            <div class="script-detail-content">
              <div class="script-header">
                <div class="script-meta">
                  <el-tag size="small" type="info">Python</el-tag>
                  <span class="script-desc">在使用该测试环境执行测试后执行的脚本，可用于清理数据</span>
                </div>
                <el-button
                  v-if="!editingPostScript"
                  v-permission="'environment:edit'"
                  size="small"
                  @click="handleEditPostScript"
                >
                  编辑
                </el-button>
                <el-button
                  v-if="editingPostScript"
                  size="small"
                  @click="handleCancelPostScript"
                >
                  取消
                </el-button>
              </div>
              <div
                v-if="environment?.post_script?.is_active || editingPostScript"
                class="script-editor-wrapper"
                :class="{ 'is-fullscreen': postScriptFullscreen }"
              >
                <div class="script-fullscreen-toggle">
                  <el-button
                    size="small"
                    circle
                    @click="postScriptFullscreen = !postScriptFullscreen"
                  >
                    <i v-if="postScriptFullscreen" class="i-solar-minimize-square-3-linear" />
                    <i v-else class="i-solar-maximize-square-3-linear" />
                  </el-button>
                </div>
                <CodeEditor
                  v-if="editingPostScript"
                  v-model="postScriptCode"
                  language="python"
                  :theme="isDark ? 'dark' : 'light'"
                  :min-height="'300px'"
                  :max-height="'500px'"
                  :show-line-count="true"
                />
                <CodeEditor
                  v-else
                  :model-value="environment?.post_script?.code || ''"
                  language="python"
                  :theme="isDark ? 'dark' : 'light'"
                  :min-height="'300px'"
                  :max-height="'500px'"
                  :show-line-count="true"
                  :readonly="true"
                />
                <div class="script-debug-bar">
                  <el-dropdown
                    trigger="click"
                    @command="handleApplyPostTemplate"
                  >
                    <el-button size="small">
                      使用模板 <i class="i-solar-alt-arrow-down-bold" />
                    </el-button>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item command="cleanup">清理测试数据</el-dropdown-item>
                        <el-dropdown-item command="db_cleanup">数据库数据清理</el-dropdown-item>
                        <el-dropdown-item command="logout">退出登录</el-dropdown-item>
                    </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                  <el-button
                    v-if="editingPostScript"
                    type="primary"
                    size="small"
                    plain
                    @click="showPostInsertFunction = true"
                  >
                    插入函数
                  </el-button>
                  <el-button
                    v-if="editingPostScript"
                    type="success"
                    size="small"
                    plain
                    @click="showInsertPostEnvVarDialog = true"
                  >
                    保存变量
                  </el-button>
                  <el-button
                    type="warning"
                    size="small"
                    :loading="debuggingPostScript"
                    @click="handleDebugPostScript"
                  >
                    调试运行
                  </el-button>
                  <el-button
                    v-if="editingPostScript"
                    v-permission="'environment:edit'"
                    type="primary"
                    size="small"
                    :loading="savingPostScript"
                    @click="handleSavePostScript"
                  >
                    保存
                  </el-button>
                </div>
                <div v-if="postScriptDebugResult" class="script-debug-result">
                  <el-alert
                    :type="postScriptDebugResult.success ? 'success' : 'error'"
                    :title="postScriptDebugResult.success ? '脚本执行成功' : '脚本执行失败'"
                    show-icon
                    :closable="false"
                  />
                  <div v-if="postScriptDebugResult.output" class="debug-output">
                    <div class="debug-output-title">输出：</div>
                    <pre>{{ postScriptDebugResult.output }}</pre>
                  </div>
                  <div v-if="postScriptDebugResult.error" class="debug-output error">
                    <div class="debug-output-title">错误信息：</div>
                    <pre>{{ postScriptDebugResult.error }}</pre>
                  </div>
                  <div v-if="postScriptDebugResult.traceback" class="debug-output error">
                    <div class="debug-output-title">堆栈跟踪：</div>
                    <pre>{{ postScriptDebugResult.traceback }}</pre>
                  </div>
                  <div v-if="postScriptDebugResult.env_data && Object.keys(postScriptDebugResult.env_data).length" class="debug-output">
                    <div class="debug-output-title">环境变量快照：</div>
                    <pre>{{ JSON.stringify(postScriptDebugResult.env_data, null, 2) }}</pre>
                  </div>
                </div>
              </div>
              <div v-else class="script-empty-hint">
                <i class="i-solar-danger-triangle-bold" />
                <span>后置脚本未启用</span>
              </div>
            </div>
          </el-tab-pane>
            </el-tabs>
          </div>
        </el-tab-pane>

        <!-- 测试变量 -->
        <el-tab-pane name="vars">
          <template #label>
            测试变量
            <span class="tab-count">{{ environment?.variable_count || 0 }}</span>
          </template>
          <VariablesPanel
            :project-id="projectId"
            :env-id="envId"
          />
        </el-tab-pane>
      </el-tabs>
    </AppSectionCard>

    <!-- 克隆环境对话框 -->
    <el-dialog
      v-model="cloneDialogVisible"
      title="克隆环境"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form label-position="top"
        ref="cloneFormRef"
        :model="cloneForm"
        :rules="cloneRules"
      >
        <el-form-item label="新环境名称" prop="name">
          <el-input
            v-model="cloneForm.name"
            placeholder="请输入新环境的名称"
            maxlength="100"
            show-word-limit
          />
        </el-form-item>
        <el-alert
          :title="`将复制环境 &quot;${environment?.name}&quot; 的所有配置和变量`"
          type="info"
          :closable="false"
          show-icon
        />
      </el-form>
      <template #footer>
        <el-button @click="cloneDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="cloning" @click="handleDoClone">
          确定
        </el-button>
      </template>
    </el-dialog>

    <!-- 插入内置函数弹窗 -->
    <InsertFunctionDialog
      v-model="showPreInsertFunction"
      :project-id="projectId"
      @insert="handleInsertPreFunction"
    />

    <!-- 插入环境变量弹窗 -->
    <el-dialog
      v-model="showInsertEnvVarDialog"
      title="插入环境变量"
      width="420px"
      :close-on-click-modal="false"
    >
      <el-form label-position="top">
        <el-form-item label="变量名">
          <el-input v-model="insertVarName" placeholder="例如：auth_token" />
        </el-form-item>
        <el-form-item label="变量值">
          <el-input v-model="insertVarValue" placeholder="例如：token_value（支持 Python 表达式）" />
        </el-form-item>
      </el-form>
      <div style="color: var(--el-text-color-secondary); font-size: 12px; margin-top: -8px;">
        将插入：<code>env_data["变量名"] = "变量值"</code>
      </div>
      <template #footer>
        <el-button @click="showInsertEnvVarDialog = false">取消</el-button>
        <el-button type="primary" @click="handleInsertEnvVar">插入</el-button>
      </template>
    </el-dialog>

    <!-- 插入内置函数弹窗（后置脚本） -->
    <InsertFunctionDialog
      v-model="showPostInsertFunction"
      :project-id="projectId"
      @insert="handleInsertPostFunction"
    />

    <!-- 插入环境变量弹窗（后置脚本） -->
    <el-dialog
      v-model="showInsertPostEnvVarDialog"
      title="插入环境变量"
      width="420px"
      :close-on-click-modal="false"
    >
      <el-form label-position="top">
        <el-form-item label="变量名">
          <el-input v-model="insertPostVarName" placeholder="例如：auth_token" />
        </el-form-item>
        <el-form-item label="变量值">
          <el-input v-model="insertPostVarValue" placeholder="例如：token_value（支持 Python 表达式）" />
        </el-form-item>
      </el-form>
      <div style="color: var(--el-text-color-secondary); font-size: 12px; margin-top: -8px;">
        将插入：<code>env_data["变量名"] = "变量值"</code>
      </div>
      <template #footer>
        <el-button @click="showInsertPostEnvVarDialog = false">取消</el-button>
        <el-button type="primary" @click="handleInsertPostEnvVar">插入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { environmentApi } from '@/api/environments'
import type { Environment, ScriptConfig, EnvType } from '@/api/environments'
import VariablesPanel from './components/VariablesPanel.vue'
import CodeEditor from '@/components/common/CodeEditor.vue'
import { AppPageHeader, AppSectionCard } from '@/components/common'
import illustEnvironment from '@/assets/illustrations/environment.svg'
import InsertFunctionDialog from '@/components/common/InsertFunctionDialog.vue'

const route = useRoute()
const router = useRouter()

// 路由参数
const projectId = computed(() => {
  const id = Number(route.params.id)
  return isNaN(id) ? 0 : id
})
const envId = computed(() => {
  const id = Number(route.params.envId)
  return isNaN(id) ? undefined : id
})

// 数据
const loading = ref(false)
const environment = ref<Environment | null>(null)

// 脚本编辑状态
const activeScriptTab = ref('pre')
const editingPreScript = ref(false)
const editingPostScript = ref(false)
const savingPreScript = ref(false)
const savingPostScript = ref(false)
const preScriptCode = ref('')
const postScriptCode = ref('')

// 主题状态
const isDark = computed(() => {
  const htmlElement = document.documentElement
  return htmlElement.getAttribute('data-theme') === 'dark'
})

// 顶部标签 + 基本配置内联编辑
const activeTab = ref<'basic' | 'script' | 'vars'>('basic')
const editing = ref(false)
const saving = ref(false)
const basicFormRef = ref<FormInstance>()
const editForm = ref({
  name: '',
  base_url: '',
  description: '',
  env_type: 1 as EnvType,
  is_default: false,
  is_global: false,
  proxy_url: '',
  timeout: 30,
})
const basicRules: FormRules = {
  name: [
    { required: true, message: '请输入环境名称', trigger: 'blur' },
    { min: 1, max: 100, message: '长度在 1 到 100 个字符', trigger: 'blur' },
  ],
  base_url: [
    { required: true, message: '请输入基础 URL', trigger: 'blur' },
    { pattern: /^https?:\/\/.+/, message: '请输入有效的 URL', trigger: 'blur' },
  ],
}

// 对话框状态
const cloneDialogVisible = ref(false)
const cloning = ref(false)

// 克隆表单
const cloneFormRef = ref<FormInstance>()
const cloneForm = ref({
  name: '',
})
const cloneRules: FormRules = {
  name: [
    { required: true, message: '请输入环境名称', trigger: 'blur' },
    { min: 1, max: 100, message: '长度在 1 到 100 个字符', trigger: 'blur' },
  ],
}

// 加载环境详情
const loadEnvironment = async () => {
  loading.value = true
  try {
    const res = await environmentApi.getEnvironmentDetail(projectId.value, envId.value)
    environment.value = res.data
  } catch (error) {
    console.error('加载环境详情失败:', error)
    handleBack()
  } finally {
    loading.value = false
  }
}

// 返回列表
const handleBack = () => {
  router.push({
    name: 'Environments',
    params: { id: projectId.value },
  })
}

// 一键进入内联编辑（基本配置），不再弹框
const enterEdit = () => {
  const e = environment.value
  if (!e) return
  editForm.value = {
    name: e.name,
    base_url: e.base_url,
    description: e.description || '',
    env_type: e.env_type ?? 1,
    is_default: e.is_default,
    is_global: e.is_global,
    proxy_url: e.proxy_url || '',
    timeout: e.timeout ?? 30,
  }
  activeTab.value = 'basic'
  editing.value = true
}

const cancelEdit = () => {
  editing.value = false
  basicFormRef.value?.clearValidate()
}

const handleSaveBasic = async () => {
  if (!basicFormRef.value || !environment.value) return
  await basicFormRef.value.validate(async (valid) => {
    if (!valid || !environment.value) return
    saving.value = true
    try {
      await environmentApi.updateEnvironment(projectId.value, environment.value.id, {
        name: editForm.value.name,
        base_url: editForm.value.base_url,
        description: editForm.value.description || undefined,
        env_type: editForm.value.env_type,
        is_default: editForm.value.is_default,
        is_global: editForm.value.is_global,
        proxy_url: editForm.value.proxy_url || undefined,
        timeout: editForm.value.timeout,
        pre_script: environment.value.pre_script,
        post_script: environment.value.post_script,
      })
      ElMessage.success('保存成功')
      editing.value = false
      loadEnvironment()
    } catch (error) {
      console.error('保存环境失败:', error)
    } finally {
      saving.value = false
    }
  })
}

// 设为默认
const handleSetDefault = async () => {
  if (!environment.value) return

  try {
    await environmentApi.setDefaultEnvironment(projectId.value, environment.value.id)
    ElMessage.success('已设置为默认环境')
    loadEnvironment()
  } catch (error) {
    console.error('设置默认环境失败:', error)
  }
}

// 克隆环境
const handleClone = () => {
  if (!environment.value) return
  cloneForm.value.name = `${environment.value.name} - 副本`
  cloneDialogVisible.value = true
}

// 执行克隆
const handleDoClone = async () => {
  if (!cloneFormRef.value || !environment.value) return

  await cloneFormRef.value.validate(async (valid) => {
    if (!valid) return

    cloning.value = true
    try {
      await environmentApi.cloneEnvironment(projectId.value, environment.value!.id, {
        name: cloneForm.value.name,
      })
      ElMessage.success('克隆成功')
      cloneDialogVisible.value = false
      // 克隆成功后跳转到列表页
      handleBack()
    } catch (error) {
      console.error('克隆环境失败:', error)
    } finally {
      cloning.value = false
    }
  })
}

// 删除环境
const handleDelete = async () => {
  if (!environment.value) return

  try {
    await ElMessageBox.confirm(
      `确定要删除环境 "${environment.value.name}" 吗？删除后将无法恢复。`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
    await environmentApi.deleteEnvironment(projectId.value, environment.value.id)
    ElMessage.success('删除成功')
    handleBack()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除环境失败:', error)
    }
  }
}

// 格式化日期时间
const formatDateTime = (datetime?: string) => {
  if (!datetime) return '-'
  const date = new Date(datetime)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

const PRE_SCRIPT_TEMPLATES: Record<string, { name: string; code: string }> = {
  login: {
    name: '登录获取Token',
    code: `import requests

base_url = env_data.get("base_url", "")
login_url = base_url + "/api/v1/auth/login"

resp = requests.post(login_url, json={
    "username": "your_username",
    "password": "your_password",
})
result = resp.json()

if result.get("code") == 200:
    env_data["auth_token"] = result["data"]["access_token"]
    env_data["user_id"] = str(result["data"]["user"]["id"])
else:
    raise Exception(f"登录失败: {result.get('message')}")
`,
  },
  db_query: {
    name: '数据库查询',
    code: `import pymysql

conn = pymysql.connect(
    host="localhost",
    port=3306,
    user="root",
    password="your_password",
    database="your_database",
    charset="utf8mb4",
)
cursor = conn.cursor(pymysql.cursors.DictCursor)

cursor.execute("SELECT id, name FROM users WHERE role = 'admin' LIMIT 1")
row = cursor.fetchone()

if row:
    env_data["admin_user_id"] = str(row["id"])
    env_data["admin_user_name"] = row["name"]

cursor.close()
conn.close()
`,
  },
  http_request: {
    name: 'HTTP接口请求',
    code: `import requests

base_url = env_data.get("base_url", "")

resp = requests.get(
    base_url + "/api/v1/projects",
    headers={"Authorization": f"Bearer {env_data.get('auth_token', '')}"},
)
result = resp.json()

if result.get("code") == 200:
    projects = result["data"]["items"]
    if projects:
        env_data["project_id"] = str(projects[0]["id"])
`,
  },
  init_data: {
    name: '初始化测试数据',
    code: `import random
import string

env_data["test_username"] = "test_" + ''.join(random.choices(string.ascii_lowercase, k=6))
env_data["test_email"] = f"{env_data['test_username']}@test.com"
env_data["test_phone"] = "138" + ''.join(random.choices(string.digits, k=8))
env_data["test_password"] = "Test@" + ''.join(random.choices(string.ascii_letters + string.digits, k=8))
`,
  },
  full_setup: {
    name: '完整环境初始化',
    code: `import requests
import random
import string

base_url = env_data.get("base_url", "")

# 1. 登录获取 Token
login_resp = requests.post(base_url + "/api/v1/auth/login", json={
    "username": "admin",
    "password": "admin123",
})
login_data = login_resp.json()
if login_data.get("code") != 200:
    raise Exception(f"登录失败: {login_data.get('message')}")
env_data["auth_token"] = login_data["data"]["access_token"]
token = env_data["auth_token"]
headers = {"Authorization": f"Bearer {token}"}

# 2. 生成测试数据
env_data["test_name"] = "test_" + ''.join(random.choices(string.ascii_lowercase, k=6))
env_data["test_email"] = f"{env_data['test_name']}@test.com"

print(f"环境初始化完成, token={token[:20]}...")
`,
  },
}

const POST_SCRIPT_TEMPLATES: Record<string, { name: string; code: string }> = {
  cleanup: {
    name: '清理测试数据',
    code: `# 清理前置脚本生成的测试数据
# 请根据实际情况修改清理逻辑

test_user = env_data.get("test_username")
if test_user:
    print(f"清理测试用户: {test_user}")
    # requests.delete(base_url + f"/api/v1/users/{test_user}")
`,
  },
  db_cleanup: {
    name: '数据库数据清理',
    code: `import pymysql

conn = pymysql.connect(
    host="localhost",
    port=3306,
    user="root",
    password="your_password",
    database="your_database",
    charset="utf8mb4",
)
cursor = conn.cursor()

# 删除测试数据（请根据实际情况修改）
test_name = env_data.get("test_name", "")
if test_name:
    cursor.execute("DELETE FROM users WHERE name = %s", (test_name,))
    print(f"删除测试用户: {test_name}, 影响行数: {cursor.rowcount}")

conn.commit()
cursor.close()
conn.close()
`,
  },
  logout: {
    name: '退出登录',
    code: `import requests

base_url = env_data.get("base_url", "")
token = env_data.get("auth_token", "")

if token:
    resp = requests.post(
        base_url + "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    print(f"退出登录响应: {resp.status_code}")
    env_data.pop("auth_token", None)
`,
  },
}

const handleApplyPreTemplate = (command: string) => {
  const tpl = PRE_SCRIPT_TEMPLATES[command]
  if (!tpl) return
  const existing = (preScriptCode.value || '').trim()
  preScriptCode.value = existing ? existing + '\n\n' + tpl.code : tpl.code
  editingPreScript.value = true
}

const showPreInsertFunction = ref(false)
const preScriptEditorRef = ref<InstanceType<typeof CodeEditor>>()
const preScriptFullscreen = ref(false)
const postScriptFullscreen = ref(false)

const handleInsertPreFunction = (code: string) => {
  preScriptCode.value = (preScriptCode.value || '') + '\n' + code
}

const showInsertEnvVarDialog = ref(false)
const insertVarName = ref('')
const insertVarValue = ref('')

const handleInsertEnvVar = () => {
  if (!insertVarName.value.trim()) {
    ElMessage.warning('请输入变量名')
    return
  }
  const name = insertVarName.value.trim()
  const value = insertVarValue.value || ''
  const code = `env_data["${name}"] = "${value}"`
  preScriptCode.value = (preScriptCode.value || '') + '\n' + code
  showInsertEnvVarDialog.value = false
  insertVarName.value = ''
  insertVarValue.value = ''
}

const debuggingPreScript = ref(false)
const preScriptDebugResult = ref<{ success: boolean; output: string; env_data?: Record<string, any>; error?: string; traceback?: string } | null>(null)

const handleDebugPreScript = async () => {
  if (!environment.value) return
  debuggingPreScript.value = true
  preScriptDebugResult.value = null
  try {
    const res = await environmentApi.debugScript(
      projectId.value,
      environment.value.id,
      'pre',
    )
    preScriptDebugResult.value = res.data
  } catch (e: any) {
    console.error('前置脚本调试请求失败:', e)
  } finally {
    debuggingPreScript.value = false
  }
}

// ==================== 后置脚本 ====================

const handleApplyPostTemplate = (command: string) => {
  const tpl = POST_SCRIPT_TEMPLATES[command]
  if (!tpl) return
  const existing = (postScriptCode.value || '').trim()
  postScriptCode.value = existing ? existing + '\n\n' + tpl.code : tpl.code
  editingPostScript.value = true
}

const showPostInsertFunction = ref(false)
const postScriptEditorRef = ref<InstanceType<typeof CodeEditor>>()

const handleInsertPostFunction = (code: string) => {
  postScriptCode.value = (postScriptCode.value || '') + '\n' + code
}

const showInsertPostEnvVarDialog = ref(false)
const insertPostVarName = ref('')
const insertPostVarValue = ref('')

const handleInsertPostEnvVar = () => {
  if (!insertPostVarName.value.trim()) {
    ElMessage.warning('请输入变量名')
    return
  }
  const name = insertPostVarName.value.trim()
  const value = insertPostVarValue.value || ''
  const code = `env_data["${name}"] = "${value}"`
  postScriptCode.value = (postScriptCode.value || '') + '\n' + code
  showInsertPostEnvVarDialog.value = false
  insertPostVarName.value = ''
  insertPostVarValue.value = ''
}

const debuggingPostScript = ref(false)
const postScriptDebugResult = ref<{ success: boolean; output: string; env_data?: Record<string, any>; error?: string; traceback?: string } | null>(null)

const handleDebugPostScript = async () => {
  if (!environment.value) return
  debuggingPostScript.value = true
  postScriptDebugResult.value = null
  try {
    const res = await environmentApi.debugScript(
      projectId.value,
      environment.value.id,
      'post',
    )
    postScriptDebugResult.value = res.data
  } catch (e: any) {
    console.error('后置脚本调试请求失败:', e)
  } finally {
    debuggingPostScript.value = false
  }
}

// 编辑前置脚本
const handleEditPreScript = () => {
  if (!environment.value) return
  preScriptCode.value = environment.value.pre_script?.code || ''
  editingPreScript.value = true
}

// 取消编辑前置脚本
const handleCancelPreScript = () => {
  editingPreScript.value = false
  preScriptCode.value = ''
}

// 保存前置脚本
const handleSavePreScript = async () => {
  if (!environment.value) return

  savingPreScript.value = true
  try {
    const defaultScript: ScriptConfig = {
      language: 'python',
      code: '',
      is_active: true,
    }

    await environmentApi.updateEnvironment(projectId.value, environment.value.id, {
      name: environment.value.name,
      base_url: environment.value.base_url,
      description: environment.value.description,
      is_default: environment.value.is_default,
      is_global: environment.value.is_global,
      proxy_url: environment.value.proxy_url,
      timeout: environment.value.timeout,
      pre_script: {
        ...defaultScript,
        code: preScriptCode.value,
        is_active: true,
      },
      post_script: environment.value.post_script,
    })

    ElMessage.success('前置脚本保存成功')
    editingPreScript.value = false
    loadEnvironment()
  } catch (error) {
    console.error('保存前置脚本失败:', error)
  } finally {
    savingPreScript.value = false
  }
}

// 编辑后置脚本
const handleEditPostScript = () => {
  if (!environment.value) return
  postScriptCode.value = environment.value.post_script?.code || ''
  editingPostScript.value = true
}

// 取消编辑后置脚本
const handleCancelPostScript = () => {
  editingPostScript.value = false
  postScriptCode.value = ''
}

// 保存后置脚本
const handleSavePostScript = async () => {
  if (!environment.value) return

  savingPostScript.value = true
  try {
    const defaultScript: ScriptConfig = {
      language: 'python',
      code: '',
      is_active: true,
    }

    await environmentApi.updateEnvironment(projectId.value, environment.value.id, {
      name: environment.value.name,
      base_url: environment.value.base_url,
      description: environment.value.description,
      is_default: environment.value.is_default,
      is_global: environment.value.is_global,
      proxy_url: environment.value.proxy_url,
      timeout: environment.value.timeout,
      pre_script: environment.value.pre_script,
      post_script: {
        ...defaultScript,
        code: postScriptCode.value,
        is_active: true,
      },
    })

    ElMessage.success('后置脚本保存成功')
    editingPostScript.value = false
    loadEnvironment()
  } catch (error) {
    console.error('保存后置脚本失败:', error)
  } finally {
    savingPostScript.value = false
  }
}

// 初始化
onMounted(() => {
  loadEnvironment()
})
</script>

<style scoped lang="scss">
// ========================================
// 页面布局
// ========================================

.environment-detail {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 20px;
  overflow-y: auto;
  padding-bottom: 20px;

  // 自定义滚动条
  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-track {
    background: var(--theme-transparent);
  }

  &::-webkit-scrollbar-thumb {
    background: var(--workspace-border-color-light);
    border-radius: 3px;

    &:hover {
      background: var(--workspace-border-color);
    }
  }
}

// ========================================
// 页面头部
// ========================================

.btn-icon {
  margin-right: 6px;
  font-size: 16px;
  vertical-align: -3px;
}

// ========================================
// 信息条
// ========================================

.env-info-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
  padding: 0 var(--space-1);
}

.type-pill,
.flag-pill {
  height: 22px;
  padding: 0 10px;
  border-radius: var(--radius-full);
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  font-weight: var(--font-weight-semibold);
}
.type-pill.is-api { background: var(--color-info-50); color: var(--color-info-600); }
.type-pill.is-ui { background: var(--color-warning-50); color: var(--color-warning-600); }
.flag-pill.is-default { background: var(--color-success-50); color: var(--color-success-600); }
.flag-pill.is-global { background: var(--brand-50); color: var(--brand-600); }

.bar-url {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--text-regular);

  i { color: var(--text-placeholder); }
}
.bar-meta {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
  font-size: 13px;
  color: var(--text-secondary);

  i { color: var(--text-placeholder); }
}

.vars-count {
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--gray-100);
  padding: 2px 10px;
  border-radius: var(--radius-full);
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;

  .info-item {
    display: flex;
    flex-direction: column;
    gap: 8px;

    &.full-width {
      grid-column: 1 / -1;
    }

    label {
      font-size: 13px;
      color: var(--workspace-text-secondary);
      font-weight: 500;
    }

    .info-value {
      font-size: 14px;
      color: var(--workspace-text-primary);
      padding: 8px 12px;
      background: var(--workspace-fill-color-extra-light);
      border-radius: 6px;
      min-height: 38px;
      display: flex;
      align-items: center;

      &.url-value {
        color: var(--workspace-color-primary);
        font-family: 'SF Mono', 'Monaco', 'Consolas', 'Liberation Mono', 'Courier New', monospace;
        font-size: 13px;

        .el-icon {
          margin-right: 8px;
          font-size: 14px;
        }
      }
    }
  }
}

// ========================================
// 脚本内容
// ========================================

.script-tabs {
  margin-top: 0;

  :deep(.el-tabs__header) {
    margin: 0 0 20px 0;
  }

  :deep(.el-tabs__item) {
    .tab-label {
      display: flex;
      align-items: center;
      gap: 8px;

      .el-tag {
        margin-left: 4px;
      }
    }
  }
}

.script-detail-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.script-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--workspace-fill-color-extra-light);
  border: 1px solid var(--workspace-border-color-lighter);
  border-radius: 8px;

  .script-meta {
    display: flex;
    align-items: center;
    gap: 12px;

    .el-tag {
      margin: 0;
    }

    .script-desc {
      font-size: 13px;
      color: var(--workspace-text-secondary);
    }
  }
}

.script-editor-wrapper {
  position: relative;

  :deep(.code-editor) {
    border-radius: 8px;
    overflow: hidden;
  }

  &.is-fullscreen {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    z-index: 9999;
    background: var(--el-bg-color);
    padding: 16px;
    display: flex;
    flex-direction: column;
    overflow: auto;

    :deep(.code-editor) {
      flex: 1;
      min-height: 0;
    }

    .script-debug-bar {
      flex-shrink: 0;
    }

    .script-debug-result {
      flex-shrink: 0;
    }
  }
}

.script-fullscreen-toggle {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 10;
  opacity: 0.6;
  transition: opacity 0.2s;

  &:hover {
    opacity: 1;
  }
}

.script-empty-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 60px 20px;
  background: var(--workspace-fill-color-extra-light);
  border: 2px dashed var(--workspace-border-color-lighter);
  border-radius: 8px;
  color: var(--workspace-text-secondary);
  font-size: 14px;

  .el-icon {
    font-size: 20px;
  }
}

.script-debug-bar {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.script-debug-result {
  margin-top: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 12px;
  background: var(--el-fill-color-lighter, var(--el-fill-color-light));

  .el-alert {
    margin-bottom: 12px;
  }
}

.debug-output {
  margin-top: 8px;

  &.error pre {
    color: var(--el-color-danger);
  }

  .debug-output-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--el-text-color-regular);
    margin-bottom: 4px;
  }

  pre {
    margin: 0;
    padding: 8px 12px;
    background: var(--el-fill-color, var(--theme-color-f0f2f5));
    border-radius: 4px;
    font-size: 12px;
    line-height: 1.6;
    overflow-x: auto;
    white-space: pre-wrap;
    word-break: break-all;
  }
}

// 保留旧的脚本内容样式（用于其他地方）
.script-content {
  background: var(--workspace-fill-color-extra-light);
  border: 1px solid var(--workspace-border-color-lighter);
  border-radius: 8px;
  padding: 16px;
  overflow-x: auto;

  pre {
    margin: 0;
    font-family: 'SF Mono', 'Monaco', 'Consolas', 'Liberation Mono', 'Courier New', monospace;
    font-size: 13px;
    line-height: 1.6;

    code {
      color: var(--workspace-text-primary);
    }
  }
}

// ========================================
// 变量管理区域
// ========================================

// ========================================
// 详情标签页 + 内联编辑表单
// ========================================
.detail-tabs {
  :deep(.el-tabs__header) {
    margin: 0;
    padding: 0 var(--space-5);
    border-bottom: 1px solid var(--border-light);
  }
  :deep(.el-tabs__nav-wrap::after) {
    display: none;
  }
  :deep(.el-tabs__item) {
    height: 46px;
    font-size: 14px;
    font-weight: var(--font-weight-medium);
    color: var(--text-secondary);

    &.is-active {
      color: var(--brand-600);
      font-weight: var(--font-weight-semibold);
    }
  }
  :deep(.el-tabs__active-bar) {
    background: var(--brand-500);
  }
}

.tab-count {
  margin-left: 6px;
  padding: 0 6px;
  border-radius: var(--radius-full);
  background: var(--brand-50);
  color: var(--brand-600);
  font-size: 11px;
}

.tab-body {
  padding: var(--space-5) var(--space-6);
}

.basic-form {
  max-width: 720px;

  .form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-5);
  }
  .w-full {
    width: 100%;
  }

  :deep(.el-form-item__label) {
    font-weight: var(--font-weight-medium);
    color: var(--text-primary);
  }
}

// ========================================
// 响应式设计
// ========================================

@media (max-width: 1024px) {
  .info-grid {
    grid-template-columns: 1fr !important;
  }
}

@media (max-width: 768px) {
  .env-info-bar {
    gap: var(--space-2);
  }
}

// ========================================
// 暗色模式
// ========================================

[data-theme='dark'] {
  .info-value {
    background: rgba(var(--theme-rgb-white), 0.04);

    &.url-value {
      background: rgba(var(--theme-rgb-primary), 0.08);
    }
  }

  .script-content {
    background: rgba(var(--theme-rgb-black), 0.2);
    border-color: rgba(var(--theme-rgb-white), 0.1);
  }
}
</style>
