<template>
  <div class="code-editor-demo">
    <div class="page-header">
      <h1>代码编辑器演示</h1>
      <p>基于 CodeMirror 6 的代码编辑器组件</p>
    </div>

    <!-- 主题切换 -->
    <div class="demo-section">
      <h2>主题切换</h2>
      <div class="theme-switcher">
        <el-radio-group v-model="currentTheme" size="large">
          <el-radio-button value="light">亮色主题</el-radio-button>
          <el-radio-button value="dark">暗色主题</el-radio-button>
        </el-radio-group>
      </div>
    </div>

    <!-- Python 编辑器 -->
    <div class="demo-section">
      <h2>Python 脚本编辑</h2>
      <CodeEditor
        v-model="pythonCode"
        language="python"
        :theme="currentTheme"
        :min-height="'300px'"
        :show-language-selector="false"
        :show-line-count="true"
      />
    </div>

    <!-- JavaScript 编辑器 -->
    <div class="demo-section">
      <h2>JavaScript 脚本编辑</h2>
      <CodeEditor
        v-model="javascriptCode"
        language="javascript"
        :theme="currentTheme"
        :min-height="'300px'"
        :show-language-selector="false"
        :show-line-count="true"
      />
    </div>

    <!-- JSON 编辑器 -->
    <div class="demo-section">
      <h2>JSON 数据编辑</h2>
      <JsonEditor
        v-model="jsonData"
        title="环境变量配置"
        :theme="currentTheme"
        @valid="handleJsonValid"
      />
    </div>

    <!-- 多语言编辑器 -->
    <div class="demo-section">
      <h2>多语言切换</h2>
      <CodeEditor
        v-model="multiLangCode"
        :language="selectedLanguage"
        :theme="currentTheme"
        :show-language-selector="true"
        :show-line-count="true"
        @update:language="handleLanguageChange"
      />
    </div>

    <!-- 只读模式 -->
    <div class="demo-section">
      <h2>只读模式</h2>
      <CodeEditor
        v-model="readonlyCode"
        language="python"
        :theme="currentTheme"
        :readonly="true"
        :show-line-count="true"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import CodeEditor from '@/components/common/CodeEditor.vue'
import JsonEditor from '@/components/common/JsonEditor.vue'
import type { CodeLanguage } from '@/components/common/CodeEditor.vue'

// 当前主题
const currentTheme = ref<'light' | 'dark'>('light')

// Python 代码示例
const pythonCode = ref(`def run(env):
    """
    前置脚本示例
    Args:
        env: 环境变量字典
    """
    # 添加时间戳
    import time
    env['timestamp'] = str(int(time.time()))

    # 添加随机数
    import random
    env['request_id'] = str(random.randint(10000, 99999))

    # 打印调试信息
    print(f"前置脚本执行完成: {env['timestamp']}")

    return env
`)

// JavaScript 代码示例
const javascriptCode = ref(`/**
 * 后置脚本示例
 * @param {Object} response - 响应对象
 * @param {Object} env - 环境变量
 */
function run(response, env) {
    // 提取响应头
    const headers = response.headers || {};

    // 计算响应时间
    const responseTime = Date.now() - env.requestStartTime;

    // 保存到环境变量
    env.responseTime = responseTime;
    env.contentType = headers['content-type'] || 'unknown';

    console.log(\`响应时间: \${responseTime}ms\`);
    console.log(\`Content-Type: \${env.contentType}\`);

    return env;
}
`)

// JSON 数据示例
const jsonData = ref({
  environment: {
    name: "测试环境",
    base_url: "https://api.example.com",
    description: "用于测试的环境配置"
  },
  variables: [
    {
      name: "api_key",
      value: "sk-xxxxxxxxxxxxxxxx",
      type: "password",
      description: "API 密钥"
    },
    {
      name: "timeout",
      value: 30000,
      type: "number",
      description: "超时时间（毫秒）"
    }
  ],
  settings: {
    retry: 3,
    delay: 1000,
    enable_cache: true
  }
})

// 多语言代码
const selectedLanguage = ref<CodeLanguage>('python')
const multiLangCode = ref(`# 这是一个多语言编辑器演示
# 你可以通过右上角的下拉框切换语言

def example():
    print("Hello, World!")
    return True
`)

// 只读代码
const readonlyCode = ref(`# 此编辑器为只读模式
# 你无法修改此代码

def readonly_example():
    """
    这是一个只读的代码示例
    """
    return "Readonly Mode"
`)

// 处理 JSON 验证
const handleJsonValid = (isValid: boolean) => {
  if (isValid) {
    console.log('JSON 格式正确')
  }
}

// 处理语言切换
const handleLanguageChange = (language: CodeLanguage) => {
  selectedLanguage.value = language
  ElMessage.success(`切换到 ${language} 语言`)
}
</script>

<style scoped lang="scss">
.code-editor-demo {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

.page-header {
  margin-bottom: 32px;
  text-align: center;

  h1 {
    font-size: 32px;
    font-weight: 600;
    color: var(--workspace-text-primary);
    margin: 0 0 8px 0;
  }

  p {
    font-size: 16px;
    color: var(--workspace-text-secondary);
    margin: 0;
  }
}

.demo-section {
  margin-bottom: 48px;

  h2 {
    font-size: 20px;
    font-weight: 600;
    color: var(--workspace-text-primary);
    margin: 0 0 16px 0;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--workspace-border-color-lighter);
  }
}

.theme-switcher {
  display: flex;
  gap: 16px;
  padding: 16px;
  background: var(--workspace-fill-color-extra-light);
  border-radius: 8px;
}
</style>
