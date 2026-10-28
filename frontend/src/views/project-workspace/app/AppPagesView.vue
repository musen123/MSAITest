<template>
  <div class="app-pages-page">
    <AppPageHeader
      icon="i-solar-iphone-bold"
      :illustration="illustTestApp"
      title="App 页面管理"
      description="管理 App 被测页面的基本信息，如页面名称、包名 / Bundle ID、Activity 名等"
      :breadcrumbs="['App 自动化', '页面管理']"
    />

    <AppUpdateNotice
      tone="purple"
      title="App 页面管理"
      description="该功能于 7 月份新班级开班更新上线，支持 Android / iOS 双端页面信息维护、批量导入"
      meta="预计 2026 年 7 月正式上线"
      cta="敬请期待"
    />

    <AppEmpty
      scene="data"
      title="功能即将上线"
      description="App 页面管理模块正在开发中"
    />
  </div>
</template>

<script setup lang="ts">
import { AppPageHeader, AppUpdateNotice, AppEmpty } from '@/components/common'
import illustTestApp from '@/assets/illustrations/test-app.svg'
</script>
