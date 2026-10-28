<template>
  <AppGlowBg variant="soft" :orbs="false">
    <div class="ds-page">
      <!-- 顶部标题 -->
      <AppPageHeader
        title="🎨 视觉系统预览"
        description="AutoTest Platform Design System — 所有规范的统一参考源。后续所有页面改造的视觉基线。"
        :breadcrumbs="['开发工具', '视觉系统']"
      >
        <template #actions>
          <el-button @click="copyDocs">
            <i class="i-solar-document-text-bold ds-btn-icon" />
            导出规范
          </el-button>
          <el-button type="primary">
            <i class="i-solar-cpu-bolt-bold ds-btn-icon" />
            应用到全站
          </el-button>
        </template>
      </AppPageHeader>

      <!-- Login Hero 大图门面 -->
      <AppSectionCard
        title="✨ · Login Hero 主插画预览"
        description="登录页用 — 等距 3D 立方体 + 4 张玻璃漂浮卡片 + 虚线连接"
      >
        <div class="hero-showcase">
          <img :src="illustLoginHero" alt="Login Hero" class="hero-img" />
        </div>
      </AppSectionCard>

      <!-- 锚点目录 -->
      <div class="ds-anchor-bar">
        <a v-for="s in sections" :key="s.id" :href="`#${s.id}`" class="anchor-item">
          <i :class="s.icon" />
          {{ s.label }}
        </a>
      </div>

      <!-- ============ 配色系统 ============ -->
      <AppSectionCard id="palette" title="01 · 配色系统" description="品牌主色 + 语义色 + 中性色三大族">
        <h4 class="ds-h4">品牌色 Brand</h4>
        <div class="palette-row">
          <div v-for="n in [50,100,200,300,400,500,600,700,800,900]" :key="n" class="swatch">
            <div class="swatch-block" :style="{ background: `var(--brand-${n})` }" />
            <div class="swatch-name">brand-{{ n }}</div>
          </div>
        </div>

        <h4 class="ds-h4">语义色 Semantic</h4>
        <div class="semantic-grid">
          <div
            v-for="s in semanticColors"
            :key="s.name"
            class="semantic-card"
          >
            <div class="sem-block" :style="{ background: s.color }" />
            <div class="sem-info">
              <div class="sem-name">{{ s.name }}</div>
              <div class="sem-hex">{{ s.hex }}</div>
              <div class="sem-use">{{ s.use }}</div>
            </div>
          </div>
        </div>

        <h4 class="ds-h4">中性色 Neutral（文字与背景）</h4>
        <div class="palette-row">
          <div v-for="n in [50,100,200,300,400,500,600,700,800,900]" :key="n" class="swatch">
            <div class="swatch-block" :style="{ background: `var(--gray-${n})` }" />
            <div class="swatch-name">gray-{{ n }}</div>
          </div>
        </div>
      </AppSectionCard>

      <!-- ============ 排版 ============ -->
      <AppSectionCard id="typography" title="02 · 排版系统" description="字号 / 字重 / 行高 / 字体栈">
        <div class="typo-grid">
          <div
            v-for="t in typoSamples"
            :key="t.label"
            class="typo-row"
            :style="{ fontSize: t.size, fontWeight: t.weight }"
          >
            <div class="typo-text">AutoTest 智能测试平台 · The quick brown fox</div>
            <div class="typo-meta">{{ t.label }} · {{ t.size }} / {{ t.weight }}</div>
          </div>
        </div>
      </AppSectionCard>

      <!-- ============ 间距与形状 ============ -->
      <AppSectionCard id="spacing" title="03 · 间距与形状" description="4px 基准网格 / 圆角 / 阴影">
        <h4 class="ds-h4">间距 Spacing（4px 基准）</h4>
        <div class="spacing-row">
          <div v-for="s in spacings" :key="s.token" class="space-item">
            <div class="space-bar" :style="{ width: s.value }" />
            <span class="space-token">{{ s.token }} = {{ s.value }}</span>
          </div>
        </div>

        <h4 class="ds-h4">圆角 Radius</h4>
        <div class="radius-row">
          <div v-for="r in radii" :key="r.token" class="radius-item">
            <div class="radius-box" :style="{ borderRadius: r.value }" />
            <span>{{ r.token }} · {{ r.value }}</span>
          </div>
        </div>

        <h4 class="ds-h4">阴影 Shadow</h4>
        <div class="shadow-row">
          <div v-for="s in shadows" :key="s.token" class="shadow-item" :style="{ boxShadow: s.value }">
            <span>{{ s.token }}</span>
          </div>
        </div>
      </AppSectionCard>

      <!-- ============ 图标系统 ============ -->
      <AppSectionCard id="icons" title="04 · 图标系统" description="Solar + Phosphor + Tabler + Lucide，按需引入，零运行时">
        <el-tabs v-model="iconTab">
          <el-tab-pane label="Solar Bold（业务彩色推荐）" name="solar-bold">
            <div class="icon-grid">
              <div v-for="name in solarBoldIcons" :key="name" class="icon-cell">
                <i :class="name" class="icon-preview" />
                <span class="icon-name">{{ name.replace('i-solar-', '').replace('-bold', '') }}</span>
              </div>
            </div>
            <div class="icon-tip">
              用法：<code class="ds-code">&lt;i class="i-solar-document-text-bold" /&gt;</code>
            </div>
          </el-tab-pane>
          <el-tab-pane label="Solar Linear（线性图标）" name="solar-linear">
            <div class="icon-grid">
              <div v-for="name in solarLinearIcons" :key="name" class="icon-cell">
                <i :class="name" class="icon-preview" />
                <span class="icon-name">{{ name.replace('i-solar-', '').replace('-linear', '') }}</span>
              </div>
            </div>
          </el-tab-pane>
          <el-tab-pane label="Phosphor（侧栏推荐）" name="ph">
            <div class="icon-grid">
              <div v-for="name in phosphorIcons" :key="name" class="icon-cell">
                <i :class="name" class="icon-preview" />
                <span class="icon-name">{{ name.replace('i-ph-', '') }}</span>
              </div>
            </div>
            <div class="icon-tip">
              用法：<code class="ds-code">&lt;i class="i-ph-list-bold" /&gt;</code>
            </div>
          </el-tab-pane>
          <el-tab-pane label="Tabler（功能图标）" name="tabler">
            <div class="icon-grid">
              <div v-for="name in tablerIcons" :key="name" class="icon-cell">
                <i :class="name" class="icon-preview" />
                <span class="icon-name">{{ name.replace('i-tabler-', '') }}</span>
              </div>
            </div>
          </el-tab-pane>
          <el-tab-pane label="Loading 动效" name="spinners">
            <div class="icon-grid">
              <div v-for="name in spinnerIcons" :key="name" class="icon-cell">
                <i :class="name" class="icon-preview" />
                <span class="icon-name">{{ name.replace('i-svg-spinners-', '') }}</span>
              </div>
            </div>
          </el-tab-pane>
          <el-tab-pane label="★ 自定义业务图标 (本项目)" name="app">
            <div
              v-for="g in ['🧪 测试', '🤖 AI', '🧩 业务']"
              :key="g"
              class="app-icon-group"
            >
              <h4 class="ds-h4 ds-h4-flat">{{ g }}</h4>
              <div class="icon-grid">
                <div
                  v-for="ico in appIcons.filter((i) => i.group === g)"
                  :key="ico.key"
                  class="icon-cell app-icon-cell"
                >
                  <i :class="[ico.cls, 'icon-preview', 'app-icon-big']" />
                  <span class="icon-name">{{ ico.label }}</span>
                  <code class="icon-code">i-app-{{ ico.key }}</code>
                </div>
              </div>
            </div>
            <div class="icon-tip">
              用法：<code class="ds-code">&lt;i class="i-app-test-case" /&gt;</code>
              手绘 24×24 SVG，<code class="ds-code">currentColor</code> 可任意着色 / 可用 <code class="ds-code">font-size</code> 缩放
            </div>

            <h4 class="ds-h4" style="margin-top: 32px">配色应用示例</h4>
            <div class="app-color-demo">
              <div class="color-demo-cell" style="color: var(--brand-500)">
                <i class="i-app-ai-spark" /> <span>主色</span>
              </div>
              <div class="color-demo-cell" style="color: var(--color-success-500)">
                <i class="i-app-test-run" /> <span>成功</span>
              </div>
              <div class="color-demo-cell" style="color: var(--color-warning-500)">
                <i class="i-app-bug" /> <span>警告</span>
              </div>
              <div class="color-demo-cell" style="color: var(--color-danger-500)">
                <i class="i-app-bug" /> <span>危险</span>
              </div>
              <div class="color-demo-cell" style="color: var(--color-info-500)">
                <i class="i-app-api" /> <span>信息</span>
              </div>
              <div class="color-demo-cell" style="color: var(--color-purple-500)">
                <i class="i-app-ai-brain" /> <span>AI</span>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </AppSectionCard>

      <!-- ============ 统计卡片 ============ -->
      <AppSectionCard id="statcards" title="05 · 统计卡 StatCard" description="软色图标容器 + 数字滚动入场 + 趋势指示">
        <div class="stat-grid">
          <AppStatCard label="用例总数" :value="2560" :trend="12.5" color="brand" :icon="iSolarDocumentTextBold" />
          <AppStatCard label="执行总数" :value="8420" :trend="8.3" color="info" :icon="iSolarPlayCircleBold" />
          <AppStatCard label="通过率" :value="98.32" :trend="2.1" :decimals="2" value-suffix="%" color="success" :icon="iSolarCheckCircleBold" />
          <AppStatCard label="缺陷总数" :value="127" :trend="-5.2" color="warning" :icon="iSolarBugBold" />
          <AppStatCard label="Agent 运行" :value="320" :trend="15.0" color="purple" :icon="iSolarRoutingBold" />
          <AppStatCard label="今日进度" :value="75" value-suffix="%" extra="已完成 18 / 24" color="cyan" :icon="iSolarChartBold" />
        </div>
      </AppSectionCard>

      <!-- ============ 按钮 ============ -->
      <AppSectionCard id="buttons" title="06 · 按钮 Button" description="主/次/文字三层，主按钮带主色阴影 + 悬浮上提">
        <h4 class="ds-h4">类型</h4>
        <el-space wrap>
          <el-button type="primary">主按钮</el-button>
          <el-button>次按钮</el-button>
          <el-button type="success">成功</el-button>
          <el-button type="warning">警告</el-button>
          <el-button type="danger">危险</el-button>
          <el-button type="info">信息</el-button>
          <el-button text>文字按钮</el-button>
          <el-button link type="primary">链接按钮</el-button>
        </el-space>

        <h4 class="ds-h4">尺寸</h4>
        <el-space>
          <el-button type="primary" size="large">大按钮</el-button>
          <el-button type="primary">默认</el-button>
          <el-button type="primary" size="small">小按钮</el-button>
        </el-space>

        <h4 class="ds-h4">带图标</h4>
        <el-space wrap>
          <el-button type="primary">
            <i class="i-solar-add-circle-bold ds-btn-icon" /> 新建用例
          </el-button>
          <el-button>
            <i class="i-solar-upload-bold ds-btn-icon" /> 导入
          </el-button>
          <el-button>
            <i class="i-solar-download-bold ds-btn-icon" /> 导出
          </el-button>
          <el-button type="danger">
            <i class="i-solar-trash-bin-trash-bold ds-btn-icon" /> 删除
          </el-button>
        </el-space>

        <h4 class="ds-h4">状态</h4>
        <el-space>
          <el-button type="primary" loading>加载中</el-button>
          <el-button type="primary" disabled>禁用</el-button>
        </el-space>
      </AppSectionCard>

      <!-- ============ 标签 / 徽章 ============ -->
      <AppSectionCard id="tags" title="07 · 标签 Tag" description="软色风格：浅底 + 同色字">
        <h4 class="ds-h4">基础标签</h4>
        <el-space wrap>
          <el-tag>默认</el-tag>
          <el-tag type="success">通过</el-tag>
          <el-tag type="warning">待执行</el-tag>
          <el-tag type="danger">失败</el-tag>
          <el-tag type="info">已禁用</el-tag>
        </el-space>

        <h4 class="ds-h4">优先级（业务约定）</h4>
        <el-space>
          <el-tag class="prio prio-p0">P0</el-tag>
          <el-tag class="prio prio-p1">P1</el-tag>
          <el-tag class="prio prio-p2">P2</el-tag>
          <el-tag class="prio prio-p3">P3</el-tag>
        </el-space>

        <h4 class="ds-h4">状态徽章</h4>
        <el-space wrap>
          <span class="status-pill is-running">● 进行中</span>
          <span class="status-pill is-pending">● 待执行</span>
          <span class="status-pill is-done">● 已完成</span>
          <span class="status-pill is-passed">● 通过</span>
          <span class="status-pill is-failed">● 失败</span>
          <span class="status-pill is-blocked">● 阻塞</span>
        </el-space>
      </AppSectionCard>

      <!-- ============ 表单 ============ -->
      <AppSectionCard id="forms" title="08 · 表单 Form" description="无边灰底 → focus 主色描边">
        <div class="form-row">
          <div class="form-col">
            <label class="form-label">输入框</label>
            <el-input placeholder="请输入..." />
          </div>
          <div class="form-col">
            <label class="form-label">选择器</label>
            <el-select placeholder="请选择" style="width: 100%">
              <el-option label="全部" value="" />
              <el-option label="进行中" value="running" />
              <el-option label="已完成" value="done" />
            </el-select>
          </div>
          <div class="form-col">
            <label class="form-label">日期选择</label>
            <el-date-picker type="date" placeholder="选择日期" style="width: 100%" />
          </div>
          <div class="form-col">
            <label class="form-label">数字输入</label>
            <el-input-number :model-value="10" style="width: 100%" />
          </div>
        </div>
        <div class="form-row">
          <div class="form-col">
            <label class="form-label">单选</label>
            <el-radio-group model-value="a">
              <el-radio value="a">手工用例</el-radio>
              <el-radio value="b">自动化</el-radio>
              <el-radio value="c">接口</el-radio>
            </el-radio-group>
          </div>
          <div class="form-col">
            <label class="form-label">开关</label>
            <el-switch :model-value="true" />
          </div>
        </div>
      </AppSectionCard>

      <!-- ============ 头像 ============ -->
      <AppSectionCard id="avatars" title="09 · 头像 Avatar" description="文字 fallback / 自动生成 / 状态点">
        <h4 class="ds-h4">尺寸（24 / 32 / 40 / 48 / 64）</h4>
        <el-space size="large">
          <AppAvatar name="张三" :size="24" />
          <AppAvatar name="李四" :size="32" />
          <AppAvatar name="王五" :size="40" />
          <AppAvatar name="Admin" :size="48" />
          <AppAvatar name="Tester" :size="64" />
        </el-space>

        <h4 class="ds-h4">配色（基于名字哈希自动分配）</h4>
        <el-space size="large" wrap>
          <AppAvatar v-for="n in palette" :key="n" :name="n" :size="40" />
        </el-space>

        <h4 class="ds-h4">带状态点</h4>
        <el-space size="large">
          <AppAvatar name="在线" :size="40" :dot="true" dot-color="success" />
          <AppAvatar name="离开" :size="40" :dot="true" dot-color="warning" />
          <AppAvatar name="忙碌" :size="40" :dot="true" dot-color="danger" />
          <AppAvatar name="离线" :size="40" :dot="true" dot-color="info" />
        </el-space>
      </AppSectionCard>

      <!-- ============ 插画资产展示 ============ -->
      <AppSectionCard
        id="illustrations"
        title="🎨 · 插画资产 Illustrations"
        description="手绘 SVG 插画 · 23 张统一风格 · 单文件 4-10KB · 矢量可无损缩放 · 前 8 张为 96×96 项目类型图标"
      >
        <div class="illust-grid">
          <div v-for="art in illustrations" :key="art.name" class="illust-cell">
            <div class="illust-canvas">
              <img :src="art.src" :alt="art.name" />
            </div>
            <div class="illust-meta">
              <div class="illust-name">{{ art.name }}</div>
              <div class="illust-file">{{ art.file }}</div>
              <div class="illust-use">{{ art.use }}</div>
              <!-- 项目图标额外展示：实际卡片中的 48px 尺寸预览 -->
              <div v-if="art.group === 'project'" class="illust-preview-row">
                <div
                  class="preview-chip"
                  :style="{ background: previewPalette[0] }"
                >
                  <img :src="art.src" :alt="art.name" />
                </div>
                <div
                  class="preview-chip"
                  :style="{ background: previewPalette[1] }"
                >
                  <img :src="art.src" :alt="art.name" />
                </div>
                <div
                  class="preview-chip"
                  :style="{ background: previewPalette[2] }"
                >
                  <img :src="art.src" :alt="art.name" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </AppSectionCard>

      <!-- ============ 空状态 ============ -->
      <AppSectionCard id="empty" title="10 · 空状态 Empty" description="场景化插画 + 引导文案 + 主操作">
        <div class="empty-showcase">
          <div class="empty-frame">
            <AppEmpty
              scene="data"
              description="还没有任何测试用例，开始创建你的第一个用例吧"
            >
              <template #actions>
                <el-button type="primary">
                  <i class="i-solar-add-circle-bold ds-btn-icon" /> 新建用例
                </el-button>
              </template>
            </AppEmpty>
          </div>
          <div class="empty-frame">
            <AppEmpty scene="search" description="试试调整筛选条件或换个关键词" />
          </div>
          <div class="empty-frame">
            <AppEmpty scene="network" description="请检查网络后重试">
              <template #actions>
                <el-button type="primary">重新加载</el-button>
              </template>
            </AppEmpty>
          </div>
          <div class="empty-frame">
            <AppEmpty scene="permission" description="联系管理员申请相应权限" />
          </div>
          <div class="empty-frame">
            <AppEmpty scene="notFound" description="您访问的页面已迁移或不存在" />
          </div>
          <div class="empty-frame">
            <AppEmpty scene="welcome" description="跟随引导完成首次配置">
              <template #actions>
                <el-button type="primary">开始引导</el-button>
              </template>
            </AppEmpty>
          </div>
          <div class="empty-frame">
            <AppEmpty scene="ai" description="AI 正在分析您的需求文档" />
          </div>
          <div class="empty-frame">
            <AppEmpty scene="success" title="测试任务全部完成" description="通过率 98.32%，共执行 8420 个用例">
              <template #actions>
                <el-button type="primary">查看报告</el-button>
              </template>
            </AppEmpty>
          </div>
          <div class="empty-frame">
            <AppEmpty scene="running" description="正在执行用例 (68 / 100)，请稍候">
              <template #actions>
                <el-button>查看进度</el-button>
              </template>
            </AppEmpty>
          </div>
          <div class="empty-frame">
            <AppEmpty scene="bug" title="缺陷处理中" description="开发已分配，3 个缺陷正在修复" />
          </div>
          <div class="empty-frame">
            <AppEmpty scene="noNotification" description="所有通知都已查阅完毕" />
          </div>
          <div class="empty-frame">
            <AppEmpty scene="report" title="报告已生成" description="可以下载或在线查看了">
              <template #actions>
                <el-button type="primary">下载报告</el-button>
              </template>
            </AppEmpty>
          </div>
          <div class="empty-frame">
            <AppEmpty scene="maintenance" description="预计 30 分钟后恢复，给您带来不便敬请谅解" />
          </div>
          <div class="empty-frame">
            <AppEmpty scene="team" description="还没有成员，邀请同事一起协作吧">
              <template #actions>
                <el-button type="primary">+ 邀请成员</el-button>
              </template>
            </AppEmpty>
          </div>
        </div>
      </AppSectionCard>

      <!-- ============ 综合示例 ============ -->
      <AppSectionCard id="composite" title="11 · 表格 + 操作综合示例" description="放在统一规范下的真实业务列表片段">
        <el-table :data="demoRows" stripe>
          <el-table-column type="selection" width="48" />
          <el-table-column prop="id" label="ID" width="120" />
          <el-table-column prop="name" label="用例名称" min-width="200" />
          <el-table-column label="所属模块" width="120">
            <template #default="{ row }">
              <el-tag type="info">{{ row.module }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="优先级" width="100">
            <template #default="{ row }">
              <el-tag :class="['prio', `prio-${row.prio.toLowerCase()}`]">{{ row.prio }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <span class="status-pill" :class="row.statusClass">● {{ row.status }}</span>
            </template>
          </el-table-column>
          <el-table-column label="创建人" width="180">
            <template #default="{ row }">
              <div class="user-cell">
                <AppAvatar :name="row.user" :size="24" />
                <span>{{ row.user }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="290" fixed="right">
            <template #default>
              <div class="row-actions">
                <el-button size="small">
                  <i class="i-solar-pen-2-linear ds-btn-icon" /> 编辑
                </el-button>
                <el-button size="small" type="primary" plain>
                  <i class="i-solar-play-circle-linear ds-btn-icon" /> 执行
                </el-button>
                <el-button size="small" type="danger" plain>
                  <i class="i-solar-trash-bin-trash-linear ds-btn-icon" /> 删除
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </AppSectionCard>

      <!-- ============ 微交互 ============ -->
      <AppSectionCard id="motion" title="12 · 微交互 Motion" description="hover 上浮 / 数字滚动 / 加载脉冲">
        <div class="motion-grid">
          <div class="motion-card hover-lift">
            <i class="i-solar-rocket-bold motion-icon" />
            <div class="motion-title">Hover 上浮</div>
            <div class="motion-desc">鼠标悬浮时 translateY(-4px) + 阴影</div>
          </div>
          <div class="motion-card">
            <div class="motion-title">数字滚动 (CountUp)</div>
            <div class="motion-big-num">
              <AppCountUp :end="98765" />
            </div>
          </div>
          <div class="motion-card">
            <div class="motion-title">加载脉冲</div>
            <div class="loading-dots">
              <span /><span /><span />
            </div>
          </div>
          <div class="motion-card">
            <div class="motion-title">主色辉光按钮</div>
            <el-button type="primary" size="large">
              <i class="i-solar-cpu-bolt-bold ds-btn-icon" />
              AI 生成
            </el-button>
          </div>
        </div>
      </AppSectionCard>

      <div class="ds-footer">
        AutoTest Platform Design System v1.0 · 所有 Token 通过 CSS Variables 注入，便于未来主题/暗色扩展
      </div>
    </div>
  </AppGlowBg>
</template>

<script setup lang="ts">import { ref } from 'vue';
import { ElMessage } from 'element-plus';
import { AppCountUp, AppStatCard, AppPageHeader, AppGlowBg, AppEmpty, AppAvatar, AppSectionCard, } from '@/components/common';
// 显式引入图标作为 stat card icon prop
import iSolarDocumentTextBold from '~icons/solar/document-text-bold';
import iSolarPlayCircleBold from '~icons/solar/play-circle-bold';
import iSolarCheckCircleBold from '~icons/solar/check-circle-bold';
import iSolarBugBold from '~icons/solar/bug-bold';
import iSolarRoutingBold from '~icons/solar/routing-bold';
import iSolarChartBold from '~icons/solar/chart-bold';
// 插画资产
import illustLoginHero from '@/assets/illustrations/login-hero.svg';
import illustEmptyData from '@/assets/illustrations/empty-data.svg';
import illustEmptySearch from '@/assets/illustrations/empty-search.svg';
import illustError404 from '@/assets/illustrations/error-404.svg';
import illustErrorNetwork from '@/assets/illustrations/error-network.svg';
import illustErrorPermission from '@/assets/illustrations/error-permission.svg';
import illustWelcome from '@/assets/illustrations/welcome.svg';
import illustAiThinking from '@/assets/illustrations/ai-thinking.svg';
import illustSuccessDone from '@/assets/illustrations/success-done.svg';
import illustRunning from '@/assets/illustrations/running.svg';
import illustBugFix from '@/assets/illustrations/bug-fix.svg';
import illustNoNotification from '@/assets/illustrations/no-notification.svg';
import illustReport from '@/assets/illustrations/report.svg';
import illustMaintenance from '@/assets/illustrations/maintenance.svg';
import illustTeam from '@/assets/illustrations/team.svg';
import illustAiCaseGen from '@/assets/illustrations/ai-case-gen.svg';
import illustAiKnowledge from '@/assets/illustrations/ai-knowledge.svg';
import illustAiChat from '@/assets/illustrations/ai-chat.svg';
import illustAiAgent from '@/assets/illustrations/ai-agent.svg';
import illustTestApi from '@/assets/illustrations/test-api.svg';
import illustTestWeb from '@/assets/illustrations/test-web.svg';
import illustTestApp from '@/assets/illustrations/test-app.svg';
import illustTestPerformance from '@/assets/illustrations/test-performance.svg';
// 项目类型图标（96×96，匹配关键词自动选择）
import illustProjectDefault from '@/assets/illustrations/project-default.svg';
import illustProjectEcommerce from '@/assets/illustrations/project-ecommerce.svg';
import illustProjectApp from '@/assets/illustrations/project-app.svg';
import illustProjectApi from '@/assets/illustrations/project-api.svg';
import illustProjectWeb from '@/assets/illustrations/project-web.svg';
import illustProjectAi from '@/assets/illustrations/project-ai.svg';
import illustProjectPerf from '@/assets/illustrations/project-perf.svg';
import illustProjectPay from '@/assets/illustrations/project-pay.svg';
const illustrations = [
    // 项目类型图标（96×96）— 优先展示
    { name: 'Project · Ecommerce', file: 'project-ecommerce.svg', use: '电商/商城项目图标', src: illustProjectEcommerce, group: 'project' },
    { name: 'Project · App', file: 'project-app.svg', use: 'APP/移动端项目图标', src: illustProjectApp, group: 'project' },
    { name: 'Project · API', file: 'project-api.svg', use: '接口测试项目图标', src: illustProjectApi, group: 'project' },
    { name: 'Project · Web', file: 'project-web.svg', use: 'Web 自动化项目图标', src: illustProjectWeb, group: 'project' },
    { name: 'Project · AI', file: 'project-ai.svg', use: 'AI 智能体项目图标', src: illustProjectAi, group: 'project' },
    { name: 'Project · Perf', file: 'project-perf.svg', use: '性能/压测项目图标', src: illustProjectPerf, group: 'project' },
    { name: 'Project · Pay', file: 'project-pay.svg', use: '支付/钱包项目图标', src: illustProjectPay, group: 'project' },
    { name: 'Project · Default', file: 'project-default.svg', use: '通用项目兜底图标', src: illustProjectDefault, group: 'project' },
    // 场景插画（240×180）
    { name: 'Login Hero', file: 'login-hero.svg', use: '登录/注册主插画', src: illustLoginHero },
    { name: 'Welcome', file: 'welcome.svg', use: '欢迎/引导/上线庆祝', src: illustWelcome },
    // AI 主题插画 ★
    { name: 'AI Case Gen', file: 'ai-case-gen.svg', use: 'AI 自动生成用例', src: illustAiCaseGen, group: 'ai' },
    { name: 'AI Knowledge', file: 'ai-knowledge.svg', use: '知识图谱可视化', src: illustAiKnowledge, group: 'ai' },
    { name: 'AI Chat', file: 'ai-chat.svg', use: 'AI 助手聊天', src: illustAiChat, group: 'ai' },
    { name: 'AI Agent', file: 'ai-agent.svg', use: '多 Agent 协作', src: illustAiAgent, group: 'ai' },
    { name: 'AI Thinking', file: 'ai-thinking.svg', use: 'AI 处理中/分析中', src: illustAiThinking, group: 'ai' },
    // 测试主题插画 ★
    { name: 'Test API', file: 'test-api.svg', use: '接口测试', src: illustTestApi, group: 'test' },
    { name: 'Test Web', file: 'test-web.svg', use: 'Web 自动化', src: illustTestWeb, group: 'test' },
    { name: 'Test App', file: 'test-app.svg', use: 'App 自动化', src: illustTestApp, group: 'test' },
    { name: 'Performance', file: 'test-performance.svg', use: '性能测试', src: illustTestPerformance, group: 'test' },
    // 业务状态
    { name: 'Running', file: 'running.svg', use: '测试执行中/任务跑', src: illustRunning },
    { name: 'Bug Fix', file: 'bug-fix.svg', use: '缺陷修复/调试中', src: illustBugFix },
    { name: 'Report', file: 'report.svg', use: '报告生成/数据导出', src: illustReport },
    { name: 'Team', file: 'team.svg', use: '团队/成员/协作', src: illustTeam },
    { name: 'Success', file: 'success-done.svg', use: '任务完成/成就', src: illustSuccessDone },
    { name: 'Maintenance', file: 'maintenance.svg', use: '维护中/施工/升级', src: illustMaintenance },
    // 空/错误
    { name: 'Empty Data', file: 'empty-data.svg', use: '通用空数据', src: illustEmptyData },
    { name: 'Empty Search', file: 'empty-search.svg', use: '搜索无结果', src: illustEmptySearch },
    { name: 'No Notification', file: 'no-notification.svg', use: '通知中心空', src: illustNoNotification },
    { name: '404 Lost', file: 'error-404.svg', use: '页面不存在', src: illustError404 },
    { name: 'Network', file: 'error-network.svg', use: '网络异常', src: illustErrorNetwork },
    { name: 'Permission', file: 'error-permission.svg', use: '无权限/访问拒绝', src: illustErrorPermission },
];
// 16 个手绘业务图标（通过 UnoCSS presetIcons 加载 src/assets/app-icons/*.svg）
// ⚠️ class 字段必须用字面字符串，方便 UnoCSS 扫描源码识别
const appIcons = [
    { key: 'test-case', label: '测试用例', group: '🧪 测试', cls: 'i-app-test-case' },
    { key: 'test-suite', label: '测试套件', group: '🧪 测试', cls: 'i-app-test-suite' },
    { key: 'test-plan', label: '测试计划', group: '🧪 测试', cls: 'i-app-test-plan' },
    { key: 'test-run', label: '测试执行', group: '🧪 测试', cls: 'i-app-test-run' },
    { key: 'test-report', label: '测试报告', group: '🧪 测试', cls: 'i-app-test-report' },
    { key: 'bug', label: '缺陷', group: '🧪 测试', cls: 'i-app-bug' },
    { key: 'ai-brain', label: 'AI 大脑', group: '🤖 AI', cls: 'i-app-ai-brain' },
    { key: 'ai-spark', label: 'AI 火花', group: '🤖 AI', cls: 'i-app-ai-spark' },
    { key: 'ai-agent', label: 'AI Agent', group: '🤖 AI', cls: 'i-app-ai-agent' },
    { key: 'knowledge', label: '知识图谱', group: '🤖 AI', cls: 'i-app-knowledge' },
    { key: 'browser', label: '浏览器', group: '🧩 业务', cls: 'i-app-browser' },
    { key: 'mobile', label: '移动端', group: '🧩 业务', cls: 'i-app-mobile' },
    { key: 'workflow', label: '工作流', group: '🧩 业务', cls: 'i-app-workflow' },
    { key: 'automation', label: '自动化', group: '🧩 业务', cls: 'i-app-automation' }
];
// 锚点目录
const sections = [
    { id: 'palette', label: '配色', icon: 'i-solar-pallete-2-bold' },
    { id: 'typography', label: '排版', icon: 'i-solar-text-bold' },
    { id: 'spacing', label: '间距', icon: 'i-solar-ruler-bold' },
    { id: 'icons', label: '图标', icon: 'i-solar-stars-bold' },
    { id: 'statcards', label: '统计卡', icon: 'i-solar-chart-bold' },
    { id: 'buttons', label: '按钮', icon: 'i-solar-cursor-bold' },
    { id: 'tags', label: '标签', icon: 'i-solar-tag-bold' },
    { id: 'forms', label: '表单', icon: 'i-solar-pen-bold' },
    { id: 'avatars', label: '头像', icon: 'i-solar-user-circle-bold' },
    { id: 'empty', label: '空状态', icon: 'i-solar-inbox-bold' },
    { id: 'composite', label: '表格', icon: 'i-solar-table-2-bold' },
    { id: 'motion', label: '动效', icon: 'i-solar-cpu-bolt-bold' },
];
// 语义色
const semanticColors = [
    { name: 'Success / 通过', color: '#10B981', hex: '#10B981', use: '成功状态、上升趋势、通过率' },
    { name: 'Warning / 警告', color: '#F59E0B', hex: '#F59E0B', use: 'P1、待处理、警示' },
    { name: 'Danger / 失败', color: '#EF4444', hex: '#EF4444', use: 'P0、失败、下降、缺陷' },
    { name: 'Info / 信息', color: '#3B82F6', hex: '#3B82F6', use: '进行中、待执行、链接' },
    { name: 'Purple / AI', color: '#8B5CF6', hex: '#8B5CF6', use: '已完成、AI、Agent' },
    { name: 'Cyan / 数据', color: '#06B6D4', hex: '#06B6D4', use: '进度、图表' },
    { name: 'Pink / 强调', color: '#EC4899', hex: '#EC4899', use: '性能测试、强调点缀' },
    { name: 'Orange / 缺陷', color: '#F97316', hex: '#F97316', use: '缺陷数、橙色系' },
];
// 排版示例
const typoSamples = [
    { label: 'H1 页标题', size: '24px', weight: '600' },
    { label: 'H2 卡片标题', size: '16px', weight: '600' },
    { label: 'H3 小节标题', size: '14px', weight: '600' },
    { label: 'Body 正文', size: '14px', weight: '400' },
    { label: 'Caption 说明', size: '13px', weight: '400' },
    { label: 'Label 极小', size: '12px', weight: '400' },
    { label: 'Display 数字', size: '28px', weight: '700' },
];
// 间距
const spacings = [
    { token: '--space-1', value: '4px' },
    { token: '--space-2', value: '8px' },
    { token: '--space-3', value: '12px' },
    { token: '--space-4', value: '16px' },
    { token: '--space-5', value: '20px' },
    { token: '--space-6', value: '24px' },
    { token: '--space-8', value: '32px' },
    { token: '--space-10', value: '40px' },
    { token: '--space-12', value: '48px' },
    { token: '--space-16', value: '64px' },
];
// 圆角
const radii = [
    { token: '--radius-xs', value: '4px' },
    { token: '--radius-sm', value: '6px' },
    { token: '--radius-md', value: '8px' },
    { token: '--radius-lg', value: '12px' },
    { token: '--radius-xl', value: '16px' },
    { token: '--radius-2xl', value: '20px' },
];
// 阴影
const shadows = [
    { token: '--shadow-xs', value: 'var(--shadow-xs)' },
    { token: '--shadow-sm', value: 'var(--shadow-sm)' },
    { token: '--shadow-md', value: 'var(--shadow-md)' },
    { token: '--shadow-lg', value: 'var(--shadow-lg)' },
    { token: '--shadow-xl', value: 'var(--shadow-xl)' },
    { token: '--shadow-brand', value: 'var(--shadow-brand)' },
];
// 图标 tab
const iconTab = ref('solar-bold');
const solarBoldIcons = [
    'i-solar-document-text-bold', 'i-solar-folder-bold', 'i-solar-cloud-bold',
    'i-solar-play-circle-bold', 'i-solar-check-circle-bold', 'i-solar-close-circle-bold',
    'i-solar-bug-bold', 'i-solar-chart-bold', 'i-solar-chart-square-bold',
    'i-solar-shield-check-bold', 'i-solar-rocket-bold', 'i-solar-user-circle-bold',
    'i-solar-settings-bold', 'i-solar-bell-bold', 'i-solar-home-2-bold',
    'i-solar-routing-bold', 'i-solar-cpu-bolt-bold', 'i-solar-stars-bold',
    'i-solar-clipboard-list-bold', 'i-solar-test-tube-minimalistic-bold',
    'i-solar-monitor-bold', 'i-solar-iphone-bold', 'i-solar-server-bold',
    'i-solar-database-bold', 'i-solar-code-bold', 'i-solar-pulse-bold',
    'i-solar-pie-chart-bold', 'i-solar-graph-bold', 'i-solar-link-bold',
    'i-solar-add-circle-bold', 'i-solar-pen-bold', 'i-solar-trash-bin-trash-bold',
];
const solarLinearIcons = [
    'i-solar-document-text-linear', 'i-solar-folder-linear', 'i-solar-cloud-linear',
    'i-solar-play-circle-linear', 'i-solar-check-circle-linear', 'i-solar-close-circle-linear',
    'i-solar-bug-linear', 'i-solar-chart-linear', 'i-solar-chart-square-linear',
    'i-solar-shield-check-linear', 'i-solar-rocket-linear', 'i-solar-user-circle-linear',
    'i-solar-settings-linear', 'i-solar-bell-linear', 'i-solar-home-2-linear',
    'i-solar-routing-linear', 'i-solar-cpu-bolt-linear', 'i-solar-stars-linear',
];
const phosphorIcons = [
    'i-ph-house-bold', 'i-ph-list-bold', 'i-ph-magnifying-glass-bold',
    'i-ph-bell-bold', 'i-ph-gear-six-bold', 'i-ph-user-bold',
    'i-ph-folder-bold', 'i-ph-files-bold', 'i-ph-rocket-launch-bold',
    'i-ph-flask-bold', 'i-ph-bug-bold', 'i-ph-chart-line-up-bold',
    'i-ph-test-tube-bold', 'i-ph-circuitry-bold', 'i-ph-graph-bold',
    'i-ph-cube-bold', 'i-ph-stack-bold', 'i-ph-tree-structure-bold',
];
const tablerIcons = [
    'i-tabler-search', 'i-tabler-filter', 'i-tabler-download',
    'i-tabler-upload', 'i-tabler-refresh', 'i-tabler-edit',
    'i-tabler-trash', 'i-tabler-eye', 'i-tabler-copy',
    'i-tabler-share', 'i-tabler-arrow-up', 'i-tabler-arrow-down',
];
const spinnerIcons = [
    'i-svg-spinners-ring-resize',
    'i-svg-spinners-bars-rotate-fade',
    'i-svg-spinners-pulse-3',
    'i-svg-spinners-dot-revolve',
    'i-svg-spinners-blocks-shuffle-3',
    'i-svg-spinners-180-ring-with-bg',
];
const palette = ['Admin', 'Tester', '张三', '李四', '王五', '赵六', '钱七', '孙八'];
/** 项目图标在卡片中常用的软色背景（与 ProjectsView 头像色板对应） */
const previewPalette = [
    'var(--brand-100)',
    'var(--color-info-50)',
    'var(--color-purple-50)',
];
// 综合表格 demo
const demoRows = [
    { id: 'TC-00001', name: '用户登录功能测试', module: '用户模块', prio: 'P0', status: '启用', statusClass: 'is-passed', user: 'Admin' },
    { id: 'TC-00002', name: '用户注册功能测试', module: '用户模块', prio: 'P1', status: '启用', statusClass: 'is-passed', user: 'Tester' },
    { id: 'TC-00003', name: '密码重置功能测试', module: '账户模块', prio: 'P1', status: '进行中', statusClass: 'is-running', user: 'Tester' },
    { id: 'TC-00004', name: '获取验证码接口', module: '用户模块', prio: 'P2', status: '已禁用', statusClass: 'is-blocked', user: '张三' },
    { id: 'TC-00005', name: '发送短信验证码', module: '用户模块', prio: 'P0', status: '失败', statusClass: 'is-failed', user: '李四' },
];
function copyDocs() {
    ElMessage.success('已复制设计规范链接到剪贴板 (Mock)');
}
</script>

<style scoped lang="scss">
.ds-page {
  padding: var(--space-6);
  > * + * {
    margin-top: var(--space-6);
  }
}

.ds-btn-icon {
  margin-right: 6px;
  display: inline-flex;
  vertical-align: -2px;
}

.ds-h4 {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--text-secondary);
  margin: var(--space-5) 0 var(--space-3);
  letter-spacing: 0.5px;
  text-transform: uppercase;

  &:first-child {
    margin-top: 0;
  }
}

.ds-code {
  background: var(--gray-100);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--brand-700);
}

/* 锚点条 */
.ds-anchor-bar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
}
.anchor-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  color: var(--text-regular);
  text-decoration: none;
  transition: var(--transition-fast);

  &:hover {
    background: var(--brand-50);
    color: var(--brand-600);
  }
  i {
    font-size: 16px;
  }
}

/* 调色板 */
.palette-row {
  display: grid;
  grid-template-columns: repeat(10, 1fr);
  gap: var(--space-2);
}
.swatch {
  text-align: center;
}
.swatch-block {
  height: 56px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-light);
}
.swatch-name {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 4px;
  font-family: var(--font-mono);
}

.semantic-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: var(--space-3);
}
.semantic-card {
  display: flex;
  gap: var(--space-3);
  padding: var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-card);
}
.sem-block {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-md);
  flex-shrink: 0;
}
.sem-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.sem-name {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}
.sem-hex {
  font-size: 11px;
  font-family: var(--font-mono);
  color: var(--text-secondary);
}
.sem-use {
  font-size: 11px;
  color: var(--text-placeholder);
}

/* 排版 */
.typo-grid {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.typo-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  background: var(--gray-50);
  border-radius: var(--radius-md);
  color: var(--text-primary);
}
.typo-meta {
  font-size: 12px;
  font-family: var(--font-mono);
  color: var(--text-placeholder);
  font-weight: 400 !important;
}

/* 间距 */
.spacing-row {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.space-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.space-bar {
  height: 24px;
  background: var(--brand-200);
  border-radius: 4px;
}
.space-token {
  font-size: 12px;
  font-family: var(--font-mono);
  color: var(--text-secondary);
}

/* 圆角 */
.radius-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
}
.radius-item {
  text-align: center;
}
.radius-box {
  width: 80px;
  height: 80px;
  background: var(--brand-100);
  border: 2px solid var(--brand-300);
  margin-bottom: 6px;
}
.radius-item span {
  font-size: 11px;
  font-family: var(--font-mono);
  color: var(--text-secondary);
}

/* 阴影 */
.shadow-row {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: var(--space-5);
}
.shadow-item {
  height: 80px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-family: var(--font-mono);
  color: var(--text-secondary);
}

/* 图标 */
.icon-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: var(--space-2);
}
.icon-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: var(--gray-50);
  transition: var(--transition-fast);
  cursor: pointer;

  &:hover {
    background: var(--brand-50);
    transform: translateY(-2px);
    .icon-preview {
      color: var(--brand-500);
    }
  }
}
.icon-preview {
  font-size: 28px;
  color: var(--text-regular);
  transition: color var(--duration-fast);
}
.icon-name {
  font-size: 11px;
  color: var(--text-secondary);
  font-family: var(--font-mono);
  text-align: center;
  word-break: break-all;
  line-height: 1.3;
}
.icon-tip {
  margin-top: var(--space-4);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}

/* 自定义业务图标 */
.app-icon-group + .app-icon-group {
  margin-top: var(--space-5);
}
.ds-h4-flat {
  margin: 0 0 var(--space-2) !important;
  text-transform: none !important;
  letter-spacing: normal !important;
  color: var(--text-primary) !important;
}
.app-icon-cell {
  padding: var(--space-4) var(--space-3) !important;

  &:hover .app-icon-big {
    color: var(--brand-500);
    transform: scale(1.15);
  }
}
.app-icon-big {
  font-size: 32px !important;
  color: var(--text-regular);
  transition: var(--transition-base);
}
.icon-code {
  display: block;
  margin-top: 4px;
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-placeholder);
}
.app-color-demo {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
  gap: var(--space-3);
}
.color-demo-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-4);
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);

  i { font-size: 28px; }
  span {
    font-size: var(--font-size-xs);
    color: var(--text-secondary);
    font-weight: var(--font-weight-medium);
  }
}

/* 统计卡 */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: var(--space-4);
}

/* 标签 */
.prio {
  height: 22px;
  line-height: 22px;
  padding: 0 8px;
  border-radius: var(--radius-xs);
  font-size: 12px;
  font-weight: var(--font-weight-semibold);
  border: none;

  &.prio-p0 { background: var(--color-danger-50);  color: var(--color-danger-600); }
  &.prio-p1 { background: var(--color-warning-50); color: var(--color-warning-600); }
  &.prio-p2 { background: var(--color-info-50);    color: var(--color-info-600); }
  &.prio-p3 { background: var(--gray-100);         color: var(--gray-600); }
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 4px 10px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: var(--font-weight-medium);

  &.is-running { background: var(--color-info-50);    color: var(--color-info-600); }
  &.is-pending { background: var(--color-warning-50); color: var(--color-warning-600); }
  &.is-done    { background: var(--color-purple-50);  color: var(--color-purple-600); }
  &.is-passed  { background: var(--color-success-50); color: var(--color-success-600); }
  &.is-failed  { background: var(--color-danger-50);  color: var(--color-danger-600); }
  &.is-blocked { background: var(--gray-100);         color: var(--gray-600); }
}

/* 表单 */
.form-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}
.form-label {
  display: block;
  font-size: var(--font-size-sm);
  color: var(--text-regular);
  margin-bottom: 6px;
}

/* Login Hero 大图展示 */
.hero-showcase {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-6);
  background:
    radial-gradient(ellipse 600px 400px at 30% 40%, rgba(0, 185, 107, 0.12), transparent 70%),
    radial-gradient(ellipse 500px 300px at 70% 60%, rgba(45, 204, 126, 0.08), transparent 70%),
    var(--bg-card);
  border-radius: var(--radius-lg);
  min-height: 480px;
}
.hero-img {
  max-width: 100%;
  max-height: 460px;
  width: auto;
  height: auto;
  display: block;
}

/* 插画资产 */
.illust-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: var(--space-4);
}
.illust-cell {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  overflow: hidden;
  background: var(--bg-card);
  transition: var(--transition-base);

  &:hover {
    transform: translateY(-3px);
    box-shadow: var(--shadow-lg);
    border-color: var(--brand-300);
  }
}
.illust-canvas {
  height: 180px;
  background:
    radial-gradient(circle at 50% 50%, var(--brand-glow-soft), transparent 70%),
    var(--gray-50);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-3);
  border-bottom: 1px solid var(--border-light);

  img {
    width: 100%;
    height: 100%;
    object-fit: contain;
  }
}
.illust-meta {
  padding: var(--space-3) var(--space-4);
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.illust-name {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}
.illust-file {
  font-size: 11px;
  font-family: var(--font-mono);
  color: var(--brand-600);
}
.illust-use {
  font-size: 11px;
  color: var(--text-placeholder);
  margin-top: 2px;
}

/* 项目图标实际使用场景预览（48px 卡片尺寸） */
.illust-preview-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px dashed var(--border-light);
}
.preview-chip {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 3px;
  overflow: hidden;
  flex-shrink: 0;

  img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    display: block;
  }
}

/* 空状态展示 */
.empty-showcase {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--space-4);
}
.empty-frame {
  background: var(--gray-50);
  border-radius: var(--radius-md);
  border: 1px dashed var(--border-base);
}

/* 表格综合 */
.user-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.row-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

/* 微交互 */
.motion-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: var(--space-4);
}
.motion-card {
  padding: var(--space-5);
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  transition: var(--transition-base);
  text-align: center;
}
.hover-lift:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-lg);
  border-color: var(--brand-300);
}
.motion-icon {
  font-size: 32px;
  color: var(--brand-500);
  margin-bottom: var(--space-2);
  display: block;
}
.motion-title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin-bottom: var(--space-2);
}
.motion-desc {
  font-size: 12px;
  color: var(--text-secondary);
}
.motion-big-num {
  font-size: var(--font-size-4xl);
  font-weight: var(--font-weight-bold);
  color: var(--brand-500);
}
.loading-dots {
  display: inline-flex;
  gap: 6px;

  span {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--brand-500);
    animation: dot-pulse 1.4s infinite ease-in-out;

    &:nth-child(2) { animation-delay: 0.16s; }
    &:nth-child(3) { animation-delay: 0.32s; }
  }
}
@keyframes dot-pulse {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.5; }
  40% { transform: scale(1); opacity: 1; }
}

/* footer */
.ds-footer {
  text-align: center;
  padding: var(--space-8) 0;
  font-size: var(--font-size-xs);
  color: var(--text-placeholder);
}
</style>
