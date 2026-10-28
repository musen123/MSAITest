<template>
  <el-dialog
    :model-value="modelValue"
    width="1000px"
    :close-on-click-modal="false"
    class="app-dialog environment-form-dialog"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <template #header>
      <div class="dialog-header">
        <h3 class="dialog-title">{{ isEdit ? '编辑环境' : '新建环境' }}</h3>
        <p class="dialog-desc">创建一个新的测试环境，用于管理和执行测试任务</p>
      </div>
    </template>

    <el-form
      ref="formRef"
      :model="formData"
      :rules="formRules"
      label-position="top"
      class="environment-form"
    >
      <el-tabs v-model="activeTab" class="environment-tabs">
        <!-- 基本信息标签页 -->
        <el-tab-pane label="基本信息" name="basic">
          <div class="form-grid">
            <el-form-item label="环境名称" prop="name" required>
              <el-input
                v-model="formData.name"
                placeholder="请输入环境名称"
                maxlength="100"
                show-word-limit
                clearable
              />
            </el-form-item>

            <el-form-item label="基础URL" prop="base_url" required>
              <el-input
                v-model="formData.base_url"
                placeholder="https://api.example.com"
                maxlength="500"
                clearable
              />
            </el-form-item>

            <el-form-item label="环境类型" prop="env_type">
              <el-radio-group v-model="formData.env_type">
                <el-radio-button :value="1">接口测试</el-radio-button>
                <el-radio-button :value="2">UI测试</el-radio-button>
              </el-radio-group>
            </el-form-item>

            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="请求超时(秒)" prop="timeout">
                  <el-input-number
                    v-model="formData.timeout"
                    :min="1"
                    :max="300"
                    :step="1"
                    controls-position="right"
                    class="full-width"
                  />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="代理URL">
                  <el-input
                    v-model="formData.proxy_url"
                    placeholder="http://proxy:8080"
                    maxlength="500"
                    clearable
                  />
                </el-form-item>
              </el-col>
            </el-row>

            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="设为默认">
                  <div class="switch-row">
                    <el-switch v-model="formData.is_default" />
                    <span class="form-hint">默认环境将作为项目的首选环境</span>
                  </div>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="全局环境">
                  <div class="switch-row">
                    <el-switch v-model="formData.is_global" />
                    <span class="form-hint">全局环境可被所有项目使用</span>
                  </div>
                </el-form-item>
              </el-col>
            </el-row>

            <el-form-item label="环境描述">
              <el-input
                v-model="formData.description"
                type="textarea"
                :rows="3"
                placeholder="简要描述该环境的用途"
                maxlength="500"
                show-word-limit
              />
            </el-form-item>

            <!-- 传输选项（执行器一等配置，该环境下所有用例默认生效，用例级可覆盖） -->
            <div class="transport-block">
              <div class="transport-head">
                <i class="i-solar-tuning-2-linear" />
                <span>传输选项</span>
                <span class="form-hint">该环境下所有用例执行时默认生效</span>
              </div>
              <el-row :gutter="20">
                <el-col :span="8">
                  <el-form-item label="校验 HTTPS 证书">
                    <div class="switch-row">
                      <el-switch v-model="formData.verify_ssl" />
                      <span class="form-hint">自签测试环境可关</span>
                    </div>
                  </el-form-item>
                </el-col>
                <el-col :span="8">
                  <el-form-item label="跟随重定向">
                    <div class="switch-row">
                      <el-switch v-model="formData.allow_redirects" />
                      <span class="form-hint">关掉可断言 3xx</span>
                    </div>
                  </el-form-item>
                </el-col>
                <el-col :span="8">
                  <el-form-item label="保持 Cookie 会话">
                    <div class="switch-row">
                      <el-switch v-model="formData.keep_cookies" />
                      <span class="form-hint">登录后续用例复用</span>
                    </div>
                  </el-form-item>
                </el-col>
              </el-row>
              <el-row :gutter="20">
                <el-col :span="8">
                  <el-form-item label="连接异常重试次数">
                    <el-input-number
                      v-model="formData.retry_times"
                      :min="0"
                      :max="10"
                      :step="1"
                      controls-position="right"
                      class="full-width"
                    />
                  </el-form-item>
                </el-col>
              </el-row>
            </div>

            <!-- 被测系统 Prometheus(压测 ↔ SUT 关联,O3) -->
            
          </div>
        </el-tab-pane>

        <!-- 前置脚本标签页 -->
        <el-tab-pane label="前置脚本" name="pre-script">
          <div class="script-tab-content">
            <div class="script-header">
              <div class="script-header-left">
                <span class="script-title">前置脚本</span>
                <el-tag size="small" type="info">Python</el-tag>
              </div>
              <el-switch
                v-model="formData.pre_script!.is_active"
                inline-prompt
                active-text="启用"
                inactive-text="禁用"
              />
            </div>

            <div v-if="formData.pre_script!.is_active" class="script-editor-wrapper">
              <div class="script-usage-hint">
                <i class="i-solar-info-circle-bold" />
                <span>
                  可用对象：<code>env_data</code>（读写环境变量，如 <code>env_data['token'] = ...</code>）、<code>global_function.*</code>（数据生成）、<code>db</code>（被测库直连，需先在「数据库」页配置连接）。用例执行前运行一次。
                </span>
              </div>
              <CodeEditor
                v-model="formData.pre_script!.code"
                language="python"
                :theme="isDark ? 'dark' : 'light'"
                :min-height="'500px'"
                :max-height="'700px'"
                :show-line-count="true"
                class="full-width-editor"
              />
            </div>
            <div v-else class="script-disabled-hint">
              <i class="i-solar-danger-triangle-bold" />
              <span>前置脚本已禁用，启用后即可编辑</span>
            </div>
          </div>
        </el-tab-pane>

        <!-- 后置脚本标签页 -->
        <el-tab-pane label="后置脚本" name="post-script">
          <div class="script-tab-content">
            <div class="script-header">
              <div class="script-header-left">
                <span class="script-title">后置脚本</span>
                <el-tag size="small" type="info">Python</el-tag>
              </div>
              <el-switch
                v-model="formData.post_script!.is_active"
                inline-prompt
                active-text="启用"
                inactive-text="禁用"
              />
            </div>

            <div v-if="formData.post_script!.is_active" class="script-editor-wrapper">
              <div class="script-usage-hint">
                <i class="i-solar-info-circle-bold" />
                <span>
                  可用对象：<code>env_data</code>（读写环境变量）、<code>global_function.*</code>（数据生成）、<code>db</code>（被测库直连，需先在「数据库」页配置连接）。
                  全部用例执行完后运行一次，常用于<strong>清理测试数据</strong>，例如：
                  <code>db.execute('测试库', "DELETE FROM users WHERE username LIKE 'autotest_%'")</code>
                </span>
              </div>
              <CodeEditor
                v-model="formData.post_script!.code"
                language="python"
                :theme="isDark ? 'dark' : 'light'"
                :min-height="'500px'"
                :max-height="'700px'"
                :show-line-count="true"
                class="full-width-editor"
              />
            </div>
            <div v-else class="script-disabled-hint">
              <i class="i-solar-danger-triangle-bold" />
              <span>后置脚本已禁用，启用后即可编辑</span>
            </div>
          </div>
        </el-tab-pane>

        <!-- 测试变量标签页 -->
        <el-tab-pane name="variables">
          <template #label>
            测试变量
            <span v-if="variables.length" class="tab-count">{{ variables.length }}</span>
          </template>
          <div class="vars-tab">
            <div class="vars-toolbar">
              <span class="vars-hint">
                配置该环境下的测试变量，用例中以 <code>{{ '${变量名}' }}</code> 引用
              </span>
              <el-button size="small" @click="addVariable">
                <i class="i-solar-add-circle-linear mr-1" /> 添加变量
              </el-button>
            </div>

            <div v-if="variables.length === 0" class="vars-empty">
              暂无变量，点击「添加变量」创建第一个
            </div>

            <div v-else class="vars-table">
              <div class="vars-row vars-row--head">
                <span>变量名</span>
                <span>值</span>
                <span>类型</span>
                <span>描述</span>
                <span />
              </div>
              <div v-for="(v, idx) in variables" :key="idx" class="vars-row">
                <el-input v-model="v.name" placeholder="变量名" size="small" />
                <el-input
                  v-model="v.value"
                  :type="v.type === 'password' ? 'password' : 'text'"
                  :show-password="v.type === 'password'"
                  placeholder="值"
                  size="small"
                />
                <el-select v-model="v.type" size="small">
                  <el-option label="文本" value="text" />
                  <el-option label="密码" value="password" />
                  <el-option label="JSON" value="json" />
                  <el-option label="动态" value="dynamic" />
                </el-select>
                <el-input v-model="v.description" placeholder="描述（可选）" size="small" />
                <el-button link type="danger" class="vars-del" @click="removeVariable(idx)">
                  <i class="i-solar-trash-bin-trash-linear" />
                </el-button>
              </div>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-form>

    <template #footer>
      <el-button @click="handleCancel">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">
        <i v-if="!submitting" class="i-solar-check-circle-bold mr-1" />
        {{ isEdit ? '保存' : '创建' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">import { ref, computed, watch } from 'vue';
import { ElMessage, type FormInstance, type FormRules } from 'element-plus';
import { environmentApi } from '@/api/environments';
import type { Environment, ScriptConfig, VariableType, ImportVariablesRequest } from '@/api/environments';
import CodeEditor from '@/components/common/CodeEditor.vue';
import type { CodeLanguage } from '@/components/common/CodeEditor.vue';
interface Props {
    modelValue: boolean;
    environment?: Environment | null;
    projectId: number;
}
interface Emits {
    (e: 'update:modelValue', value: boolean): void;
    (e: 'success'): void;
}
const props = defineProps<Props>();
const emit = defineEmits<Emits>();
const formRef = ref<FormInstance>();
const submitting = ref(false);
const activeTab = ref('basic');
const isEdit = computed(() => !!props.environment);
const isDark = computed(() => document.documentElement.getAttribute('data-theme') === 'dark');
const getEditorLanguage = (): CodeLanguage => 'python';
const formData = ref({
    name: '',
    base_url: '',
    description: '',
    env_type: 1 as 1 | 2,
    is_default: false,
    is_global: false,
    proxy_url: '',
    timeout: 30,
    verify_ssl: true,
    allow_redirects: true,
    keep_cookies: false,
    retry_times: 1,
    pre_script: { language: 'python' as 'python' | 'javascript', code: '', is_active: false },
    post_script: { language: 'python' as 'python' | 'javascript', code: '', is_active: false }
});
// SUT Prometheus 测试连接状态（须声明在 resetForm / watch(immediate) 之前，否则 TDZ）


const formRules: FormRules = {
    name: [
        { required: true, message: '请输入环境名称', trigger: 'blur' },
        { min: 1, max: 100, message: '长度在 1 到 100 个字符', trigger: 'blur' },
    ],
    base_url: [
        { required: true, message: '请输入基础URL', trigger: 'blur' },
        { pattern: /^https?:\/\/.+/, message: '请输入有效的URL', trigger: 'blur' },
    ],
    timeout: [
        { required: true, message: '请输入超时时间', trigger: 'blur' },
        { type: 'number', min: 1, max: 300, message: '超时时间在 1-300 秒之间', trigger: 'blur' },
    ],
};
// ==================== 测试变量 ====================
interface VarRow {
    id: number | null;
    name: string;
    value: string;
    type: VariableType;
    description: string;
}
const variables = ref<VarRow[]>([]);
const addVariable = () => {
    variables.value.push({ id: null, name: '', value: '', type: 'text', description: '' });
};
const removeVariable = (idx: number) => {
    variables.value.splice(idx, 1);
};
const loadVariables = async (envId: number) => {
    try {
        const res = await environmentApi.getVariableList(props.projectId, envId);
        variables.value = (res.data || []).map((v) => ({
            id: v.id,
            name: v.name,
            value: v.value,
            type: v.type,
            description: v.description || '',
        }));
    }
    catch {
        variables.value = [];
    }
};
/** replace 模式整组覆盖，新环境用返回的 envId */
const saveVariables = async (envId: number) => {
    const list = variables.value
        .filter((v) => v.name.trim())
        .map((v, i) => ({
        name: v.name.trim(),
        value: v.value ?? '',
        type: v.type,
        description: v.description || '',
        is_active: true,
        sort_order: i,
    }));
    // 编辑模式始终覆盖（含清空删除）；创建模式无变量则跳过
    if (!isEdit.value && list.length === 0)
        return;
    await environmentApi.importVariables(props.projectId, envId, {
        content: {
            environment: formData.value.name || '',
            exported_at: new Date().toISOString(),
            variables: list,
        },
        mode: 'replace',
    } as unknown as ImportVariablesRequest);
};
const resetForm = () => {
    formData.value = {
        name: '', base_url: '', description: '',
        env_type: 1, is_default: false, is_global: false,
        proxy_url: '', timeout: 30,
        verify_ssl: true, allow_redirects: true, keep_cookies: false, retry_times: 1,
        pre_script: { language: 'python', code: '', is_active: false },
        post_script: { language: 'python', code: '', is_active: false }
    };
    variables.value = [];
    
    formRef.value?.clearValidate();
};
watch(() => props.modelValue, (isOpen) => { if (isOpen)
    activeTab.value = 'basic'; });
watch(() => props.environment, (env) => {
    if (env) {
        const defaultScript: ScriptConfig = { language: 'python', code: '', is_active: false };
        formData.value = {
            name: env.name,
            base_url: env.base_url,
            description: env.description || '',
            env_type: env.env_type ?? 1,
            is_default: env.is_default,
            is_global: env.is_global,
            proxy_url: env.proxy_url || '',
            timeout: env.timeout,
            verify_ssl: env.verify_ssl ?? true,
            allow_redirects: env.allow_redirects ?? true,
            keep_cookies: env.keep_cookies ?? false,
            retry_times: env.retry_times ?? 1,
            pre_script: env.pre_script ? { ...defaultScript, ...env.pre_script } : defaultScript,
            post_script: env.post_script ? { ...defaultScript, ...env.post_script } : defaultScript
        };
        
        loadVariables(env.id);
    }
    else {
        resetForm();
    }
}, { immediate: true });
const handleSubmit = async () => {
    if (!formRef.value)
        return;
    await formRef.value.validate(async (valid) => {
        if (!valid)
            return;
        submitting.value = true;
        try {
            const payload = {
                name: formData.value.name,
                base_url: formData.value.base_url,
                description: formData.value.description || undefined,
                env_type: formData.value.env_type,
                is_default: formData.value.is_default,
                is_global: formData.value.is_global,
                proxy_url: formData.value.proxy_url || undefined,
                timeout: formData.value.timeout,
                verify_ssl: formData.value.verify_ssl,
                allow_redirects: formData.value.allow_redirects,
                keep_cookies: formData.value.keep_cookies,
                retry_times: formData.value.retry_times,
                pre_script: formData.value.pre_script,
                post_script: formData.value.post_script
            };
            let envId: number;
            if (isEdit.value && props.environment) {
                await environmentApi.updateEnvironment(props.projectId, props.environment.id, payload);
                envId = props.environment.id;
            }
            else {
                const res = await environmentApi.createEnvironment(props.projectId, payload);
                envId = res.data.id;
            }
            // 保存测试变量（replace 整组覆盖）
            await saveVariables(envId);
            ElMessage.success(isEdit.value ? '更新成功' : '创建成功');
            emit('success');
        }
        catch (error) {
            console.error('提交失败:', error);
        }
        finally {
            submitting.value = false;
        }
    });
};
// ==================== SUT Prometheus 测试连接 ====================

const handleCancel = () => emit('update:modelValue', false);
</script>

<style scoped lang="scss">
.environment-form {
  :deep(.el-form-item) {
    margin-bottom: var(--space-5);
  }

  :deep(.el-form-item__label) {
    font-weight: var(--font-weight-medium);
    color: var(--text-primary);
    padding-bottom: 6px;
    line-height: 1.4;
  }

  :deep(.el-form-item.is-required) {
    .el-form-item__label::before {
      color: var(--brand-500);
      margin-right: 4px;
    }
  }
}

.transport-block {
  margin-top: var(--space-2);
  margin-bottom: var(--space-3);
  padding: var(--space-4);
  border: 1px dashed var(--border-base);
  border-radius: var(--radius-md);
  background: var(--bg-page);

  .transport-head {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: var(--space-3);
    font-weight: var(--font-weight-medium);
    color: var(--text-primary);
    i { font-size: 17px; color: var(--brand-500); }
  }
  .form-hint {
    font-weight: var(--font-weight-normal);
    font-size: var(--font-size-xs);
    color: var(--text-placeholder);
  }
}

.sut-prom-block {
  margin-top: var(--space-2);
  padding: var(--space-4);
  border: 1px dashed var(--border-base);
  border-radius: var(--radius-md);
  background: var(--bg-page);

  .sut-prom-head {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: var(--space-3);
    font-weight: var(--font-weight-medium);
    color: var(--text-primary);
    i { font-size: 17px; color: var(--brand-500); }
  }
  .form-hint {
    font-weight: var(--font-weight-normal);
    font-size: var(--font-size-xs);
    color: var(--text-placeholder);
  }
  .sut-prom-test {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    flex-wrap: wrap;
  }
  .test-result {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: var(--font-size-sm);
    i { font-size: 15px; }
    &.ok { color: var(--color-success-600); }
    &.fail { color: var(--color-danger-600); }
  }
  .btn-icon { margin-right: 4px; vertical-align: -2px; }
}

.form-grid {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.switch-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding-top: 4px;
}

.form-hint {
  font-size: 12px;
  color: var(--text-placeholder);
}

.form-hint-danger {
  color: var(--color-danger-600);
  b { font-weight: var(--font-weight-semibold); }
}

.full-width {
  width: 100%;
}

// Tabs
.environment-tabs {
  :deep(.el-tabs__header) {
    margin: 0 0 var(--space-4);
    border-bottom: 1px solid var(--border-light);
  }

  :deep(.el-tabs__item) {
    font-size: 14px;
    font-weight: var(--font-weight-medium);
    color: var(--text-secondary);
    padding: 0 16px;
    height: 40px;
    line-height: 40px;

    &.is-active {
      color: var(--brand-500);
      font-weight: var(--font-weight-semibold);
    }

    &:hover { color: var(--brand-500); }
  }

  :deep(.el-tabs__active-bar) {
    background-color: var(--brand-500);
    height: 2px;
  }

  :deep(.el-tabs__content) {
    max-height: 60vh;
    overflow-y: auto;
    padding-right: 4px;
  }
}

// Script
.script-tab-content {
  padding: 4px 0;
  display: flex;
  flex-direction: column;
}

.script-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  margin-bottom: 12px;
  background: var(--gray-50);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-light);
}

.script-header-left {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.script-title {
  font-size: 14px;
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}

.script-editor-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;

  :deep(.code-editor) {
    flex: 1;
    display: flex;
    flex-direction: column;
    border-radius: var(--radius-md);
    overflow: hidden;
    border: 1px solid var(--border-light);

    .editor-container {
      flex: 1;
      min-height: 500px !important;
      max-height: 700px !important;
    }
  }
}

.full-width-editor { width: 100%; }

.script-disabled-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: 60px 20px;
  background: var(--gray-50);
  border: 2px dashed var(--border-light);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: 14px;

  i { font-size: 24px; color: var(--text-placeholder); }
}

.script-usage-hint {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-bottom: 8px;
  padding: 8px 12px;
  background: var(--gray-50);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.7;

  i {
    flex-shrink: 0;
    margin-top: 2px;
    font-size: 14px;
    color: var(--brand-500);
  }

  code {
    padding: 1px 5px;
    border-radius: 4px;
    background: var(--gray-100);
    color: var(--text-primary);
    font-family: var(--font-mono, monospace);
    font-size: 11px;
  }

  strong { color: var(--text-primary); }
}

// 测试变量
.tab-count {
  margin-left: 6px;
  padding: 0 6px;
  border-radius: var(--radius-full);
  background: var(--brand-50);
  color: var(--brand-600);
  font-size: 11px;
}

.vars-tab { padding: 4px 0; }

.vars-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.vars-hint {
  font-size: 12px;
  color: var(--text-secondary);

  code {
    font-family: var(--font-mono);
    background: var(--gray-100);
    padding: 1px 6px;
    border-radius: var(--radius-sm);
    color: var(--brand-700);
  }
}

.vars-empty {
  padding: 40px 0;
  text-align: center;
  color: var(--text-placeholder);
  font-size: 13px;
  border: 1px dashed var(--border-light);
  border-radius: var(--radius-md);
  background: var(--gray-50);
}

.vars-table {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.vars-row {
  display: grid;
  grid-template-columns: 1.2fr 1.5fr 110px 1.4fr 40px;
  gap: var(--space-2);
  align-items: center;
  padding: 8px 12px;
  border-top: 1px solid var(--border-light);

  &:first-child { border-top: none; }
}

.vars-row--head {
  background: var(--gray-50);
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  font-weight: var(--font-weight-medium);
}

.vars-del { justify-self: center; }
</style>