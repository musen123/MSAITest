<template>
  <div class="app-elements-page">
    <AppPageHeader
      icon="i-app-automation"
      :illustration="illustTestApp"
      title="App 元素管理"
      description="管理 App 页面控件元素，如按钮、输入框等，提供元素定位符配置"
      :breadcrumbs="['App 自动化', '元素管理']"
    />

    <AppUpdateNotice
      tone="warning"
      title="App 元素管理"
      description="该功能于 7 月份新班级开班更新上线，支持智能元素定位、多端元素复用、AI 自动生成定位符"
      meta="预计 2026 年 7 月正式上线"
      cta="敬请期待"
    />

    <AppEmpty
      scene="data"
      title="功能即将上线"
      description="App 元素管理模块正在开发中"
    />
  </div>
</template>

<script setup lang="ts">
import { AppPageHeader, AppUpdateNotice, AppEmpty } from '@/components/common'
import illustTestApp from '@/assets/illustrations/test-app.svg'
</script>
