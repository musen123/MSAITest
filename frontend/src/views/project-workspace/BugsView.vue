<template>
  <div class="bugs-page">
    <!-- ============ 页头 ============ -->
    <AppPageHeader
      icon="i-app-bug"
      :illustration="illustBugFix"
      title="缺陷管理"
      description="跟踪和管理项目缺陷，支持状态流转、指派与 AI 智能分析"
      :breadcrumbs="['项目工作区', '缺陷管理']"
    >
      <template #actions>
        <el-button v-permission="'bug:create'" type="primary" @click="openCreateDialog">
          <i class="i-solar-add-circle-bold btn-icon" />
          创建 Bug
        </el-button>
      </template>
    </AppPageHeader>

    <!-- ============ 统计卡 ============ -->
    <div class="stat-grid">
      <AppStatCard label="Bug 总数" :value="bugStats.total" color="brand">
        <template #icon><i class="i-solar-bug-bold dash-card-icon" /></template>
      </AppStatCard>
      <AppStatCard label="待处理" :value="statsPending" color="warning">
        <template #icon><i class="i-solar-clock-bold dash-card-icon" /></template>
      </AppStatCard>
      <AppStatCard label="处理中" :value="statsInProgress" color="info">
        <template #icon><i class="i-solar-loader-bold dash-card-icon" /></template>
      </AppStatCard>
      <AppStatCard label="已解决" :value="statsResolved" color="success">
        <template #icon><i class="i-solar-check-circle-bold dash-card-icon" /></template>
      </AppStatCard>
    </div>

    <!-- ============ 筛选区 ============ -->
    <div class="filter-bar">
      <div class="filter-fields">
        <div class="filter-field">
          <label>关键词</label>
          <el-input
            v-model="filters.keyword"
            placeholder="搜索标题或编号"
            clearable
            @keyup.enter="handleSearch"
            @clear="handleSearch"
          >
            <template #prefix>
              <i class="i-solar-magnifer-linear" />
            </template>
          </el-input>
        </div>

        <div class="filter-field">
          <label>状态</label>
          <el-select
            v-model="filters.status"
            placeholder="全部状态"
            clearable
            @change="handleSearch"
          >
            <el-option
              v-for="s in STATUS_OPTIONS"
              :key="s.value"
              :label="s.label"
              :value="s.value"
            />
          </el-select>
        </div>

        <div class="filter-field">
          <label>严重程度</label>
          <el-select
            v-model="filters.severity"
            placeholder="全部"
            clearable
            @change="handleSearch"
          >
            <el-option
              v-for="s in SEVERITY_OPTIONS"
              :key="s.value"
              :label="s.label"
              :value="s.value"
            />
          </el-select>
        </div>

        <div class="filter-field">
          <label>优先级</label>
          <el-select
            v-model="filters.priority"
            placeholder="全部"
            clearable
            @change="handleSearch"
          >
            <el-option
              v-for="p in PRIORITY_OPTIONS"
              :key="p.value"
              :label="p.label"
              :value="p.value"
            />
          </el-select>
        </div>

        <div class="filter-field">
          <label>指派人</label>
          <el-select
            v-model="filters.assigned_to"
            placeholder="全部"
            clearable
            filterable
            :loading="membersLoading"
            @change="handleSearch"
          >
            <el-option
              v-for="m in projectMembers"
              :key="m.user.id"
              :value="m.user.id"
              :label="m.user.real_name || m.user.username"
            />
          </el-select>
        </div>

        <div class="filter-field">
          <label>创建人</label>
          <el-select
            v-model="filters.created_by"
            placeholder="全部"
            clearable
            filterable
            :loading="membersLoading"
            @change="handleSearch"
          >
            <el-option
              v-for="m in projectMembers"
              :key="m.user.id"
              :value="m.user.id"
              :label="m.user.real_name || m.user.username"
            />
          </el-select>
        </div>
      </div>

      <div class="filter-actions">
        <el-checkbox v-model="filters.is_archived" @change="handleSearch">查看已归档</el-checkbox>
        <el-button @click="resetFilters">
          <i class="i-solar-refresh-linear btn-icon" />
          重置
        </el-button>
        <el-button type="primary" @click="handleSearch">
          <i class="i-solar-magnifer-bold btn-icon" />
          查询
        </el-button>
      </div>
    </div>

    <!-- ============ 视图切换 + 内容 ============ -->
    <AppSectionCard padless>
      <div class="view-bar">
        <div class="view-left">
          <el-radio-group v-model="viewMode" size="small">
            <el-radio-button value="card">
              <i class="i-solar-widget-2-bold" style="margin-right:4px" />
              卡片
            </el-radio-button>
            <el-radio-button value="table">
              <i class="i-solar-list-bold" style="margin-right:4px" />
              列表
            </el-radio-button>
          </el-radio-group>
        </div>
        <div class="view-right">
          <span class="result-hint">共 {{ pagination.total }} 条</span>
        </div>
      </div>

      <!-- 卡片视图 -->
      <div v-if="viewMode === 'card'" v-loading="loading" class="card-view">
        <AppEmpty
          v-if="!loading && bugs.length === 0"
          scene="data"
          description="暂无 Bug 记录，点击「创建 Bug」开始"
        >
          <template #actions>
            <el-button v-permission="'bug:create'" type="primary" @click="openCreateDialog">
              <i class="i-solar-add-circle-bold btn-icon" />
              立即创建
            </el-button>
          </template>
        </AppEmpty>
        <div v-else class="card-grid">
          <div
            v-for="item in bugs"
            :key="item.id"
            class="bug-card"
            @click="handleViewBug(item)"
          >
            <div class="card-header">
              <span class="bug-key">{{ item.bug_key }}</span>
              <el-tag :type="statusTagType(item.status)" size="small">
                {{ statusLabel(item.status) }}
              </el-tag>
              <el-tag v-if="item.is_archived" type="info" size="small">已归档</el-tag>
            </div>

            <div class="card-body">
              <h3 class="bug-title">{{ item.title }}</h3>
              <p class="bug-desc">{{ truncate(item.title, 80) }}</p>
            </div>

            <div class="card-meta">
              <span class="severity-pill" :class="`severity-${item.severity}`">
                {{ severityLabel(item.severity) }}
              </span>
              <span class="priority-pill" :class="`priority-${item.priority}`">
                {{ priorityLabel(item.priority) }}
              </span>
              <span class="assignee">{{ item.assignee_name || '未指派' }}</span>
            </div>

            <div class="card-footer">
              <span class="create-time">{{ formatDate(item.created_at) }}</span>
              <div class="card-actions">
                <button class="icon-btn-sm" title="查看" @click.stop="handleViewBug(item)">
                  <i class="i-solar-eye-linear" />
                </button>
                <button v-permission="'bug:edit'" class="icon-btn-sm" title="编辑" @click.stop="openEditDialog(item)">
                  <i class="i-solar-pen-2-linear" />
                </button>
                <button v-permission="'bug:delete'" class="icon-btn-sm danger" title="删除" @click.stop="handleDelete(item)">
                  <i class="i-solar-trash-bin-trash-linear" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 表格视图 -->
      <div v-else class="table-view">
        <el-table
          v-loading="loading"
          :data="bugs"
          row-key="id"
          style="width: 100%"
        >
          <el-table-column prop="bug_key" label="编号" width="175">
            <template #default="{ row }">
              <span class="bug-key-cell">{{ row.bug_key }}</span>
            </template>
          </el-table-column>

          <el-table-column prop="title" label="标题" min-width="220" show-overflow-tooltip />

          <el-table-column label="严重程度" width="100">
            <template #default="{ row }">
              <span class="severity-pill" :class="`severity-${row.severity}`">
                {{ severityLabel(row.severity) }}
              </span>
            </template>
          </el-table-column>

          <el-table-column label="优先级" width="90">
            <template #default="{ row }">
              <span class="priority-pill" :class="`priority-${row.priority}`">
                {{ priorityLabel(row.priority) }}
              </span>
            </template>
          </el-table-column>

          <el-table-column label="状态" width="105">
            <template #default="{ row }">
              <span class="status-pill" :class="`status-${row.status}`">
                {{ statusLabel(row.status) }}
              </span>
            </template>
          </el-table-column>

          <el-table-column label="指派人" width="100">
            <template #default="{ row }">
              {{ row.assignee_name || '-' }}
            </template>
          </el-table-column>

          <el-table-column label="创建时间" width="155">
            <template #default="{ row }">
              <span class="muted-text">{{ formatDate(row.created_at) }}</span>
            </template>
          </el-table-column>

          <el-table-column label="操作" width="250" fixed="right">
            <template #default="{ row }">
              <div class="row-actions">
                <el-button size="small" @click="handleViewBug(row)">
                  <i class="i-solar-eye-linear btn-icon-sm" />查看
                </el-button>
                <el-button v-permission="'bug:edit'" size="small" @click="openEditDialog(row)">
                  <i class="i-solar-pen-2-linear btn-icon-sm" />
                </el-button>
                <el-dropdown trigger="click" @command="(cmd: string) => handleCommand(cmd, row)">
                  <el-button size="small">
                    更多
                    <i class="i-solar-arrow-down-linear" />
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="status">变更状态</el-dropdown-item>
                      <el-dropdown-item command="assign">指派</el-dropdown-item>
                      <el-dropdown-item command="resolve">解决 / 关闭</el-dropdown-item>
                      <el-dropdown-item command="archive">
                        {{ row.is_archived ? '取消归档' : '归档' }}
                      </el-dropdown-item>
                      <el-dropdown-item command="delete" divided>
                        <span class="danger-text">删除</span>
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>
            </template>
          </el-table-column>

          <template #empty>
            <AppEmpty
              v-if="!loading"
              scene="data"
              description="暂无 Bug 记录，点击「创建 Bug」开始"
            >
              <template #actions>
                <el-button v-permission="'bug:create'" type="primary" @click="openCreateDialog">
                  <i class="i-solar-add-circle-bold btn-icon" />
                  立即创建
                </el-button>
              </template>
            </AppEmpty>
          </template>
        </el-table>
      </div>

      <!-- 分页 -->
      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          background
          @size-change="loadBugs"
          @current-change="loadBugs"
        />
      </div>
    </AppSectionCard>

    <!-- Bug 详情抽屉 -->
    <el-drawer
      v-model="showDetail"
      direction="rtl"
      size="62%"
      :before-close="closeDetail"
    >
      <template #header>
        <div v-if="currentBug" class="drawer-header-content">
          <div class="drawer-title-row">
            <span class="drawer-bug-key">{{ currentBug.bug_key }}</span>
            <el-tag :type="statusTagType(currentBug.status)" style="margin-left: 10px">
              {{ statusLabel(currentBug.status) }}
            </el-tag>
            <el-tag v-if="currentBug.is_archived" type="info" style="margin-left: 6px">
              已归档
            </el-tag>
          </div>
          <div class="drawer-action-row">
            <el-button size="small" @click="openStatusDialog(currentBug)">变更状态</el-button>
            <el-button v-permission="'bug:assign'" size="small" @click="openAssignDialog(currentBug)">指派</el-button>
            <el-button v-permission="['bug:resolve', 'bug:close']" size="small" @click="openResolveDialog(currentBug)">解决/关闭</el-button>
            <el-button v-permission="'bug:edit'" size="small" @click="openEditDialog(currentBug)">编辑</el-button>
          </div>
        </div>
      </template>

      <template v-if="currentBug">
        <el-tabs v-model="detailTab" class="detail-tabs" @tab-change="onDetailTabChange">
          <!-- 基本信息 Tab -->
          <el-tab-pane label="基本信息" name="info">
            <div class="bug-detail">
              <h3 class="bug-detail-title">{{ currentBug.title }}</h3>

              <div class="detail-meta-grid">
                <div class="meta-item">
                  <span class="meta-label">严重程度</span>
                  <el-tag :type="severityTagType(currentBug.severity)" size="small">
                    {{ severityLabel(currentBug.severity) }}
                  </el-tag>
                </div>
                <div class="meta-item">
                  <span class="meta-label">优先级</span>
                  <el-tag :type="priorityTagType(currentBug.priority)" size="small">
                    {{ priorityLabel(currentBug.priority) }}
                  </el-tag>
                </div>
                <div class="meta-item">
                  <span class="meta-label">模块</span>
                  <span class="meta-value">{{ currentBug.module_name || '-' }}</span>
                </div>
                <div class="meta-item">
                  <span class="meta-label">指派人</span>
                  <span class="meta-value">{{ currentBug.assignee_name || '-' }}</span>
                </div>
                <div class="meta-item">
                  <span class="meta-label">创建人</span>
                  <span class="meta-value">{{ currentBug.creator_name || '-' }}</span>
                </div>
                <div class="meta-item">
                  <span class="meta-label">发现环境</span>
                  <span class="meta-value">{{ currentBug.environment || '-' }}</span>
                </div>
                <div v-if="currentBug.external_bug_key" class="meta-item">
                  <span class="meta-label">外部编号</span>
                  <span class="meta-value">{{ currentBug.external_bug_key }}</span>
                </div>
                <div class="meta-item">
                  <span class="meta-label">创建时间</span>
                  <span class="meta-value">{{ formatDate(currentBug.created_at) }}</span>
                </div>
                <div class="meta-item">
                  <span class="meta-label">更新时间</span>
                  <span class="meta-value">{{ formatDate(currentBug.updated_at) }}</span>
                </div>
              </div>

              <div v-if="currentBug.tags?.length" class="bug-tags-row">
                <el-tag
                  v-for="tag in currentBug.tags"
                  :key="tag"
                  size="small"
                  class="bug-tag"
                >
                  {{ tag }}
                </el-tag>
              </div>

              <div class="detail-section">
                <div class="section-label">描述</div>
                <div class="section-body">{{ currentBug.description || '-' }}</div>
              </div>

              <div v-if="currentBug.reproduction_steps" class="detail-section">
                <div class="section-label">复现步骤</div>
                <div class="section-body pre-wrap">{{ currentBug.reproduction_steps }}</div>
              </div>

              <div v-if="currentBug.expected_result || currentBug.actual_result" class="result-row">
                <div v-if="currentBug.expected_result" class="detail-section half">
                  <div class="section-label">预期结果</div>
                  <div class="section-body">{{ currentBug.expected_result }}</div>
                </div>
                <div v-if="currentBug.actual_result" class="detail-section half">
                  <div class="section-label">实际结果</div>
                  <div class="section-body actual">{{ currentBug.actual_result }}</div>
                </div>
              </div>
            </div>
          </el-tab-pane>

          <!-- 操作历史 Tab -->
          <el-tab-pane label="操作历史" name="history">
            <div v-loading="historyLoading" class="history-panel">
              <el-timeline v-if="histories.length">
                <el-timeline-item
                  v-for="h in histories"
                  :key="h.id"
                  :timestamp="formatDate(h.operated_at)"
                  placement="top"
                >
                  <div class="history-item">
                    <span class="h-operator">{{ h.operator_name || `用户 ${h.operated_by}` }}</span>
                    <span class="h-action">{{ historyActionLabel(h.action) }}</span>
                    <span v-if="h.from_value || h.to_value" class="h-change">
                      {{ h.from_value || '—' }} → {{ h.to_value || '—' }}
                    </span>
                    <p v-if="h.comment" class="h-comment">{{ h.comment }}</p>
                  </div>
                </el-timeline-item>
              </el-timeline>
              <el-empty v-else-if="!historyLoading" description="暂无操作历史" />
            </div>
          </el-tab-pane>

          <!-- AI 分析 Tab -->
          <el-tab-pane label="AI 分析" name="ai">
            <div class="ai-panel">
              <div class="ai-trigger-bar">
                <el-button
                  type="primary"
                  :loading="aiTriggering"
                  @click="triggerAiAnalysis"
                >
                  {{ currentBug.has_ai_analysis ? '重新分析' : '触发 AI 分析' }}
                </el-button>
                <span class="ai-tip">AI 将自动分析根因、推荐解决方案并识别相似 Bug</span>
              </div>

              <!-- 状态展示 -->
              <div v-if="aiStatus" class="ai-status-row">
                <el-tag :type="aiStatusTagType(aiStatus.analysis_status)" size="large">
                  {{ aiStatusLabel(aiStatus.analysis_status) }}
                </el-tag>
                <span class="ai-time">{{ formatDate(aiStatus.created_at) }}</span>
              </div>

              <!-- 分析结果 -->
              <template v-if="aiResult && aiResult.analysis_status === 'completed'">
                <template v-if="aiResult.root_cause_analysis">
                  <div class="ai-block-title">根因分析</div>
                  <pre class="ai-json">{{ JSON.stringify(aiResult.root_cause_analysis, null, 2) }}</pre>
                </template>

                <template v-if="aiResult.solution_recommendation">
                  <div class="ai-block-title">解决方案推荐</div>
                  <pre class="ai-json">{{ JSON.stringify(aiResult.solution_recommendation, null, 2) }}</pre>
                </template>

                <template v-if="aiResult.similar_bugs?.length">
                  <div class="ai-block-title">相似 Bug</div>
                  <div
                    v-for="(b, i) in aiResult.similar_bugs"
                    :key="i"
                    class="similar-bug-item"
                  >
                    <span class="sim-key">{{ b.bug_key }}</span>
                    <span class="sim-title">{{ b.title }}</span>
                    <el-tag size="small" :type="statusTagType(b.status)">
                      {{ statusLabel(b.status) }}
                    </el-tag>
                    <span class="sim-score">
                      相似度 {{ Math.round(b.similarity_score * 100) }}%
                    </span>
                  </div>
                </template>

                <template v-if="aiResult.severity_assessment">
                  <div class="ai-block-title">严重程度评估</div>
                  <pre class="ai-json">{{ JSON.stringify(aiResult.severity_assessment, null, 2) }}</pre>
                </template>
              </template>

              <!-- 失败提示 -->
              <el-alert
                v-if="aiStatus?.analysis_status === 'failed'"
                type="error"
                :closable="false"
                style="margin-top: 12px"
              >
                分析失败：{{ aiStatus.error_message || '未知错误，请重新触发分析' }}
              </el-alert>

              <!-- 空状态 -->
              <el-empty
                v-if="!aiStatus && !currentBug.has_ai_analysis && !aiTriggering"
                description="尚未触发 AI 分析"
              />
            </div>
          </el-tab-pane>
        </el-tabs>
      </template>
    </el-drawer>

    <!-- 创建 / 编辑 Bug 对话框 -->
    <el-dialog
      v-model="showBugDialog"
      :title="editingBug ? '编辑 Bug' : '创建 Bug'"
      width="700px"
      @close="resetBugForm"
    >
      <el-form label-position="top"
        ref="bugFormRef"
        :model="bugForm"
        :rules="bugRules"
      >
        <el-form-item label="标题" prop="title">
          <el-input
            v-model="bugForm.title"
            placeholder="请输入 Bug 标题"
            maxlength="255"
            show-word-limit
          />
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="严重程度" prop="severity">
              <el-select v-model="bugForm.severity" style="width: 100%">
                <el-option
                  v-for="s in SEVERITY_OPTIONS"
                  :key="s.value"
                  :label="s.label"
                  :value="s.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="优先级" prop="priority">
              <el-select v-model="bugForm.priority" style="width: 100%">
                <el-option
                  v-for="p in PRIORITY_OPTIONS"
                  :key="p.value"
                  :label="p.label"
                  :value="p.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="所属模块">
              <el-select
                v-model="bugForm.module_id"
                placeholder="选择模块"
                clearable
                filterable
                style="width: 100%"
                :loading="modulesLoading"
              >
                <el-option
                  v-for="m in flattenModules(projectModules)"
                  :key="m.id"
                  :label="m.path || m.name"
                  :value="m.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="指派给">
              <el-select
                v-model="bugForm.assigned_to"
                placeholder="选择指派人"
                clearable
                filterable
                style="width: 100%"
                :loading="membersLoading"
              >
                <el-option
                  v-for="mem in projectMembers"
                  :key="mem.user.id"
                  :value="mem.user.id"
                  :label="mem.user.real_name || mem.user.username"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="描述" prop="description">
          <el-input
            v-model="bugForm.description"
            type="textarea"
            :rows="4"
            placeholder="请输入 Bug 详细描述"
          />
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="发现环境">
              <el-input v-model="bugForm.environment" placeholder="如：测试环境 v1.2.3" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="外部编号">
              <el-input v-model="bugForm.external_bug_key" placeholder="如：JIRA-1234" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="复现步骤">
          <el-input
            v-model="bugForm.reproduction_steps"
            type="textarea"
            :rows="3"
            placeholder="请描述复现步骤"
          />
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="预期结果">
              <el-input
                v-model="bugForm.expected_result"
                type="textarea"
                :rows="2"
                placeholder="预期的正确结果"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="实际结果">
              <el-input
                v-model="bugForm.actual_result"
                type="textarea"
                :rows="2"
                placeholder="实际观察到的结果"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="标签">
          <el-select
            v-model="bugForm.tags"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="输入标签后按 Enter 确认"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showBugDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitBugForm">
          {{ editingBug ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 变更状态对话框 -->
    <el-dialog v-model="showStatusDialog" title="变更状态" width="440px">
      <el-form label-position="top">
        <el-form-item label="目标状态">
          <el-select v-model="statusForm.status" style="width: 100%">
            <el-option
              v-for="s in availableStatuses"
              :key="s.value"
              :label="s.label"
              :value="s.value"
            />
          </el-select>
          <div v-if="!availableStatuses.length" class="form-tip">
            当前状态（{{ statusLabel(actionTarget?.status || '') }}）不允许进一步流转
          </div>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="statusForm.comment" type="textarea" :rows="2" placeholder="可选备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showStatusDialog = false">取消</el-button>
        <el-button
          type="primary"
          :loading="actionLoading"
          :disabled="!availableStatuses.length"
          @click="submitStatusChange"
        >
          确认
        </el-button>
      </template>
    </el-dialog>

    <!-- 指派对话框 -->
    <el-dialog v-model="showAssignDialog" title="指派 Bug" width="440px">
      <el-form label-position="top">
        <el-form-item label="指派给">
          <el-select
            v-model="assignForm.assigned_to"
            filterable
            placeholder="搜索成员姓名或用户名"
            style="width: 100%"
            :loading="membersLoading"
            no-data-text="暂无项目成员"
            clearable
          >
            <el-option
              v-for="m in projectMembers"
              :key="m.user.id"
              :value="m.user.id"
              :label="m.user.real_name || m.user.username"
            >
              <div class="member-option">
                <span class="member-name">{{ m.user.real_name || m.user.username }}</span>
                <span class="member-username">@{{ m.user.username }}</span>
                <el-tag size="small" type="info" class="member-role">{{ m.project_role }}</el-tag>
              </div>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="assignForm.comment" type="textarea" :rows="2" placeholder="可选备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAssignDialog = false">取消</el-button>
        <el-button type="primary" :loading="actionLoading" @click="submitAssign">确认</el-button>
      </template>
    </el-dialog>

    <!-- 解决 / 关闭 / 重开对话框 -->
    <el-dialog v-model="showResolveDialog" title="操作 Bug" width="440px">
      <template v-if="availableResolveActions.length">
        <el-form label-position="top">
          <el-form-item label="操作类型">
            <el-radio-group v-model="resolveForm.action" style="display: flex; flex-direction: column; gap: 8px">
              <el-radio
                v-for="act in availableResolveActions"
                :key="act"
                :value="act"
              >
                {{ RESOLVE_ACTION_LABELS[act] }}
              </el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="resolveForm.comment" type="textarea" :rows="2" placeholder="可选备注" />
          </el-form-item>
        </el-form>
      </template>
      <template v-else>
        <el-result icon="warning" title="当前状态不支持此操作">
          <template #sub-title>
            <div class="resolve-hint">
              <p>Bug 当前状态为「<strong>{{ statusLabel(actionTarget?.status || '') }}</strong>」</p>
              <p>状态流转规则：</p>
              <ul>
                <li><strong>标记已解决</strong>：需先将状态变更为「处理中」</li>
                <li><strong>关闭 / 重新打开</strong>：需状态为「已解决」或「已验证」</li>
              </ul>
            </div>
          </template>
        </el-result>
      </template>
      <template #footer>
        <el-button @click="showResolveDialog = false">{{ availableResolveActions.length ? '取消' : '关闭' }}</el-button>
        <el-button
          v-if="availableResolveActions.length"
          type="primary"
          :loading="actionLoading"
          @click="submitResolve"
        >
          确认
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import illustBugFix from '@/assets/illustrations/bug-fix.svg'
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import AppPageHeader from '@/components/common/AppPageHeader.vue'
import AppStatCard from '@/components/common/AppStatCard.vue'
import AppSectionCard from '@/components/common/AppSectionCard.vue'
import AppEmpty from '@/components/common/AppEmpty.vue'
import { bugApi } from '@/api/bugs'
import { moduleStatsApi, type BugsStats } from '@/api/module-stats'
import { projectApi, type ProjectMember, type ProjectModule } from '@/api/projects'
import type {
  Bug,
  BugListItem,
  BugHistory,
  AiAnalysisStatus,
  AiAnalysisResult,
  BugCreate,
  BugUpdate,
} from '@/types/bugs'

const route = useRoute()
const projectId = computed(() => Number(route.params.id))

// ── 常量配置 ──────────────────────────────────────────────

const STATUS_OPTIONS = [
  { value: 'new', label: '新建' },
  { value: 'assigned', label: '已指派' },
  { value: 'in_progress', label: '处理中' },
  { value: 'resolved', label: '已解决' },
  { value: 'verified', label: '已验证' },
  { value: 'reopened', label: '重新打开' },
  { value: 'closed', label: '已关闭' },
  { value: 'postponed', label: '延后' },
  { value: 'wontfix', label: '不修复' },
]

const SEVERITY_OPTIONS = [
  { value: 'critical', label: '致命' },
  { value: 'major', label: '严重' },
  { value: 'moderate', label: '中等' },
  { value: 'minor', label: '轻微' },
  { value: 'trivial', label: '微不足道' },
]

const PRIORITY_OPTIONS = [
  { value: 'urgent', label: '紧急' },
  { value: 'high', label: '高' },
  { value: 'medium', label: '中' },
  { value: 'low', label: '低' },
]

const VALID_TRANSITIONS: Record<string, string[]> = {
  new: ['assigned', 'postponed', 'wontfix'],
  assigned: ['in_progress', 'postponed', 'wontfix'],
  in_progress: ['resolved', 'postponed', 'wontfix'],
  resolved: ['verified', 'reopened', 'closed'],
  verified: ['closed', 'reopened'],
  reopened: ['assigned', 'in_progress', 'postponed', 'wontfix'],
  closed: [],
  postponed: ['assigned', 'wontfix'],
  wontfix: [],
}

// ── 列表状态 ──────────────────────────────────────────────

const loading = ref(false)
const bugs = ref<BugListItem[]>([])

const viewMode = ref<'card' | 'table'>('table')

const pagination = ref({
  page: 1,
  pageSize: 20,
  total: 0,
})

const filters = ref({
  keyword: '',
  status: '',
  severity: '',
  priority: '',
  assigned_to: null as number | null,
  created_by: null as number | null,
  is_archived: false,
})

// module-stats 全量口径（桶归并与项目概览一致）
const bugStats = ref<BugsStats>({ total: 0, by_status: {} })

async function loadBugStats() {
  try {
    const res = await moduleStatsApi.get(projectId.value, 'bugs')
    bugStats.value = res.data
  } catch (err) {
    console.error(err)
  }
}

function sumStatuses(statuses: string[]): number {
  return statuses.reduce(
    (acc, s) => acc + (bugStats.value.by_status[s] || 0),
    0,
  )
}

const statsPending = computed(() => sumStatuses(['new', 'reopened']))
const statsInProgress = computed(() => sumStatuses(['assigned', 'in_progress']))
const statsResolved = computed(() => sumStatuses(['resolved', 'verified']))

function truncate(str: string, len: number): string {
  if (str.length <= len) return str
  return str.slice(0, len) + '...'
}

async function loadBugs() {
  loading.value = true
  try {
    const res = await bugApi.list(projectId.value, {
      keyword: filters.value.keyword || undefined,
      status: filters.value.status || undefined,
      severity: filters.value.severity || undefined,
      priority: filters.value.priority || undefined,
      assigned_to: filters.value.assigned_to || undefined,
      created_by: filters.value.created_by || undefined,
      is_archived: filters.value.is_archived,
      page: pagination.value.page,
      page_size: pagination.value.pageSize,
    })
    bugs.value = res.data?.items || []
    pagination.value.total = res.data?.total || 0
  } catch (e) {
    console.error('加载 Bug 列表失败', e)
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pagination.value.page = 1
  loadBugs()
}

function resetFilters() {
  filters.value = { keyword: '', status: '', severity: '', priority: '', assigned_to: null, created_by: null, is_archived: false }
  pagination.value.page = 1
  loadBugs()
}

// ── Bug 详情 ──────────────────────────────────────────────

const showDetail = ref(false)
const currentBug = ref<Bug | null>(null)
const detailTab = ref('info')

const historyLoading = ref(false)
const histories = ref<BugHistory[]>([])

const aiStatus = ref<AiAnalysisStatus | null>(null)
const aiResult = ref<AiAnalysisResult | null>(null)
const aiTriggering = ref(false)
let aiPollTimer: ReturnType<typeof setInterval> | null = null

async function handleViewBug(row: BugListItem) {
  try {
    const res = await bugApi.get(projectId.value, row.id)
    currentBug.value = res.data || null
    showDetail.value = true
    detailTab.value = 'info'
    histories.value = []
    aiStatus.value = null
    aiResult.value = null
  } catch (e) {
    console.error('加载 Bug 详情失败', e)
  }
}

function closeDetail() {
  showDetail.value = false
  stopAiPolling()
}

watch(detailTab, async (tab) => {
  if (!currentBug.value) return
  if (tab === 'history' && !histories.value.length) {
    await loadHistories()
  } else if (tab === 'ai') {
    await loadAiData()
  }
})

function onDetailTabChange(tab: string) {
  detailTab.value = tab
}

async function loadHistories() {
  if (!currentBug.value) return
  historyLoading.value = true
  try {
    const res = await bugApi.getHistories(projectId.value, currentBug.value.id)
    histories.value = res.data || []
  } catch (e) {
    console.error('加载历史记录失败', e)
  } finally {
    historyLoading.value = false
  }
}

async function loadAiData() {
  if (!currentBug.value?.has_ai_analysis) return
  try {
    const res = await bugApi.getAiAnalysisStatus(projectId.value, currentBug.value.id)
    aiStatus.value = res.data || null
    if (aiStatus.value?.analysis_status === 'completed') {
      const r = await bugApi.getAiAnalysis(projectId.value, currentBug.value.id)
      aiResult.value = r.data || null
    } else if (aiStatus.value?.analysis_status === 'processing') {
      startAiPolling()
    }
  } catch {
    // 尚未分析，忽略 404
  }
}

async function triggerAiAnalysis() {
  if (!currentBug.value) return
  aiTriggering.value = true
  stopAiPolling()
  try {
    await bugApi.triggerAiAnalysis(projectId.value, currentBug.value.id)
    ElMessage.success('AI 分析已触发，请稍候')
    currentBug.value.has_ai_analysis = true
    aiResult.value = null
    await loadAiData()
  } catch (e) {
    console.error('触发 AI 分析失败', e)
  } finally {
    aiTriggering.value = false
  }
}

function startAiPolling() {
  stopAiPolling()
  aiPollTimer = setInterval(async () => {
    if (!currentBug.value) return
    try {
      const res = await bugApi.getAiAnalysisStatus(projectId.value, currentBug.value.id)
      aiStatus.value = res.data || null
      if (aiStatus.value?.analysis_status === 'completed') {
        const r = await bugApi.getAiAnalysis(projectId.value, currentBug.value.id)
        aiResult.value = r.data || null
        stopAiPolling()
      } else if (aiStatus.value?.analysis_status === 'failed') {
        stopAiPolling()
      }
    } catch {
      stopAiPolling()
    }
  }, 2000)
}

function stopAiPolling() {
  if (aiPollTimer) {
    clearInterval(aiPollTimer)
    aiPollTimer = null
  }
}

// ── 创建 / 编辑 Bug ───────────────────────────────────────

const showBugDialog = ref(false)
const editingBug = ref<BugListItem | null>(null)
const submitting = ref(false)
const bugFormRef = ref<FormInstance>()

const bugForm = ref({
  title: '',
  description: '',
  severity: 'moderate' as string,
  priority: 'medium' as string,
  module_id: undefined as number | undefined,
  assigned_to: undefined as number | undefined,
  environment: '',
  reproduction_steps: '',
  expected_result: '',
  actual_result: '',
  tags: [] as string[],
  external_bug_key: '',
})

const bugRules = {
  title: [{ required: true, message: '请输入 Bug 标题', trigger: 'blur' }],
  description: [{ required: true, message: '请输入 Bug 描述', trigger: 'blur' }],
  severity: [{ required: true, message: '请选择严重程度', trigger: 'change' }],
  priority: [{ required: true, message: '请选择优先级', trigger: 'change' }],
}

function openCreateDialog() {
  editingBug.value = null
  resetBugForm()
  loadProjectMembers()
  loadProjectModules()
  showBugDialog.value = true
}

function openEditDialog(bug: BugListItem | Bug) {
  editingBug.value = bug
  const b = bug as Bug
  bugForm.value = {
    title: b.title,
    description: b.description || '',
    severity: b.severity,
    priority: b.priority,
    module_id: b.module_id,
    assigned_to: b.assigned_to,
    environment: b.environment || '',
    reproduction_steps: b.reproduction_steps || '',
    expected_result: b.expected_result || '',
    actual_result: b.actual_result || '',
    tags: b.tags ? [...b.tags] : [],
    external_bug_key: b.external_bug_key || '',
  }
  loadProjectMembers()
  loadProjectModules()
  showBugDialog.value = true
}

function resetBugForm() {
  bugForm.value = {
    title: '',
    description: '',
    severity: 'moderate',
    priority: 'medium',
    module_id: undefined,
    assigned_to: undefined,
    environment: '',
    reproduction_steps: '',
    expected_result: '',
    actual_result: '',
    tags: [],
    external_bug_key: '',
  }
  bugFormRef.value?.clearValidate()
}

async function submitBugForm() {
  await bugFormRef.value?.validate()
  submitting.value = true
  try {
    const payload: BugCreate = {
      title: bugForm.value.title,
      description: bugForm.value.description,
      severity: bugForm.value.severity as BugCreate['severity'],
      priority: bugForm.value.priority as BugCreate['priority'],
      module_id: bugForm.value.module_id,
      assigned_to: bugForm.value.assigned_to,
      environment: bugForm.value.environment || undefined,
      reproduction_steps: bugForm.value.reproduction_steps || undefined,
      expected_result: bugForm.value.expected_result || undefined,
      actual_result: bugForm.value.actual_result || undefined,
      tags: bugForm.value.tags.length ? bugForm.value.tags : undefined,
      external_bug_key: bugForm.value.external_bug_key || undefined,
    }

    if (editingBug.value) {
      await bugApi.update(projectId.value, editingBug.value.id, payload as BugUpdate)
      ElMessage.success('Bug 已更新')
      // 若抽屉正在展示该 Bug，刷新详情
      if (currentBug.value?.id === editingBug.value.id) {
        const r = await bugApi.get(projectId.value, editingBug.value.id)
        currentBug.value = r.data || null
      }
    } else {
      await bugApi.create(projectId.value, payload)
      ElMessage.success('Bug 创建成功')
    }

    showBugDialog.value = false
    loadBugs()
    loadBugStats()
  } catch (e) {
    console.error('保存 Bug 失败', e)
  } finally {
    submitting.value = false
  }
}

// ── 状态变更 ──────────────────────────────────────────────

const showStatusDialog = ref(false)
const actionTarget = ref<BugListItem | null>(null)
const actionLoading = ref(false)
const statusForm = ref({ status: '', comment: '' })

const availableStatuses = computed(() => {
  if (!actionTarget.value) return []
  const valid = VALID_TRANSITIONS[actionTarget.value.status] || []
  return STATUS_OPTIONS.filter((s) => valid.includes(s.value))
})

function openStatusDialog(bug: BugListItem | Bug) {
  actionTarget.value = bug
  const first = (VALID_TRANSITIONS[bug.status] || [])[0] || ''
  statusForm.value = { status: first, comment: '' }
  showStatusDialog.value = true
}

async function submitStatusChange() {
  if (!actionTarget.value || !statusForm.value.status) return
  actionLoading.value = true
  try {
    await bugApi.changeStatus(projectId.value, actionTarget.value.id, {
      status: statusForm.value.status as Bug['status'],
      comment: statusForm.value.comment || undefined,
    })
    ElMessage.success('状态已更新')
    showStatusDialog.value = false
    await refreshAfterAction(actionTarget.value.id)
  } catch (e) {
    console.error('状态变更失败', e)
  } finally {
    actionLoading.value = false
  }
}

// ── 指派 ─────────────────────────────────────────────────

const showAssignDialog = ref(false)
const assignForm = ref<{ assigned_to: number | null; comment: string }>({
  assigned_to: null,
  comment: '',
})
const projectMembers = ref<ProjectMember[]>([])
const membersLoading = ref(false)
const projectModules = ref<ProjectModule[]>([])
const modulesLoading = ref(false)

async function loadProjectMembers() {
  if (projectMembers.value.length) return
  membersLoading.value = true
  try {
    const res = await projectApi.getProjectMembers(projectId.value)
    projectMembers.value = res.data || []
  } catch (e) {
    console.error('加载项目成员失败', e)
  } finally {
    membersLoading.value = false
  }
}

async function loadProjectModules() {
  if (projectModules.value.length) return
  modulesLoading.value = true
  try {
    const res = await projectApi.getModuleTree(projectId.value)
    projectModules.value = res.data || []
  } catch (e) {
    console.error('加载项目模块失败', e)
  } finally {
    modulesLoading.value = false
  }
}

function flattenModules(modules: ProjectModule[], prefix = ''): ProjectModule[] {
  const result: ProjectModule[] = []
  for (const m of modules) {
    result.push({ ...m, path: prefix + m.name })
    if (m.children?.length) {
      result.push(...flattenModules(m.children, prefix + m.name + ' / '))
    }
  }
  return result
}

function openAssignDialog(bug: BugListItem | Bug) {
  actionTarget.value = bug
  assignForm.value = { assigned_to: bug.assigned_to ?? null, comment: '' }
  showAssignDialog.value = true
  loadProjectMembers()
}

async function submitAssign() {
  if (!actionTarget.value) return
  if (!assignForm.value.assigned_to) {
    ElMessage.warning('请选择指派人')
    return
  }
  actionLoading.value = true
  try {
    await bugApi.assign(projectId.value, actionTarget.value.id, {
      assigned_to: assignForm.value.assigned_to,
      comment: assignForm.value.comment || undefined,
    })
    ElMessage.success('指派成功')
    showAssignDialog.value = false
    await refreshAfterAction(actionTarget.value.id)
  } catch (e) {
    console.error('指派失败', e)
  } finally {
    actionLoading.value = false
  }
}

// ── 解决 / 关闭 / 重开 ───────────────────────────────────

// 每种状态下允许的 resolve 操作
const RESOLVE_ACTION_MAP: Record<string, Array<'resolve' | 'close' | 'reopen'>> = {
  in_progress: ['resolve'],
  resolved: ['close', 'reopen'],
  verified: ['close', 'reopen'],
}

const RESOLVE_ACTION_LABELS: Record<string, string> = {
  resolve: '标记已解决（需处理中状态）',
  close: '关闭 Bug',
  reopen: '重新打开',
}

const availableResolveActions = computed(() => {
  if (!actionTarget.value) return []
  return RESOLVE_ACTION_MAP[actionTarget.value.status] || []
})

const showResolveDialog = ref(false)
const resolveForm = ref({
  action: 'resolve' as 'resolve' | 'close' | 'reopen',
  comment: '',
})

function openResolveDialog(bug: BugListItem | Bug) {
  actionTarget.value = bug
  const actions = RESOLVE_ACTION_MAP[bug.status] || []
  resolveForm.value = { action: actions[0] ?? 'resolve', comment: '' }
  showResolveDialog.value = true
}

async function submitResolve() {
  if (!actionTarget.value) return
  actionLoading.value = true
  try {
    await bugApi.resolve(projectId.value, actionTarget.value.id, {
      action: resolveForm.value.action,
      comment: resolveForm.value.comment || undefined,
    })
    const msgMap = {
      resolve: 'Bug 已标记为已解决',
      close: 'Bug 已关闭',
      reopen: 'Bug 已重新打开',
    }
    ElMessage.success(msgMap[resolveForm.value.action])
    showResolveDialog.value = false
    await refreshAfterAction(actionTarget.value.id)
  } catch (e) {
    console.error('解决/关闭 Bug 操作失败', e)
  } finally {
    actionLoading.value = false
  }
}

// ── 归档 & 删除 ───────────────────────────────────────────

async function handleArchive(bug: BugListItem) {
  const toArchive = !bug.is_archived
  await ElMessageBox.confirm(
    `确认${toArchive ? '归档' : '取消归档'} Bug「${bug.bug_key}」？`,
    '确认',
    { type: 'warning' },
  )
  try {
    await bugApi.archive(projectId.value, bug.id, toArchive)
    ElMessage.success(toArchive ? 'Bug 已归档' : '已取消归档')
    loadBugs()
    loadBugStats()
  } catch (e) {
    console.error('归档操作失败', e)
  }
}

async function handleDelete(bug: BugListItem) {
  await ElMessageBox.confirm(
    `确认删除 Bug「${bug.bug_key}」？此操作不可恢复。`,
    '删除确认',
    {
      type: 'warning',
      confirmButtonText: '删除',
      confirmButtonClass: 'el-button--danger',
    },
  )
  try {
    await bugApi.delete(projectId.value, bug.id)
    ElMessage.success('Bug 已删除')
    if (showDetail.value && currentBug.value?.id === bug.id) {
      closeDetail()
    }
    loadBugs()
    loadBugStats()
  } catch (e) {
    console.error('删除 Bug 失败', e)
  }
}

function handleCommand(cmd: string, row: BugListItem) {
  if (cmd === 'status') openStatusDialog(row)
  else if (cmd === 'assign') openAssignDialog(row)
  else if (cmd === 'resolve') openResolveDialog(row)
  else if (cmd === 'archive') handleArchive(row)
  else if (cmd === 'delete') handleDelete(row)
}

// ── 通用刷新 ──────────────────────────────────────────────

async function refreshAfterAction(bugId: number) {
  loadBugs()
  loadBugStats()
  if (currentBug.value?.id === bugId) {
    try {
      const r = await bugApi.get(projectId.value, bugId)
      currentBug.value = r.data || null
      // 如果历史 tab 已加载，重新加载
      if (detailTab.value === 'history') {
        histories.value = []
        await loadHistories()
      }
    } catch {
      // ignore
    }
  }
}

// ── 工具函数 ──────────────────────────────────────────────

function statusLabel(s: string) {
  return STATUS_OPTIONS.find((o) => o.value === s)?.label || s
}

function statusTagType(s: string): '' | 'success' | 'info' | 'warning' | 'danger' {
  const map: Record<string, '' | 'success' | 'info' | 'warning' | 'danger'> = {
    new: 'info',
    assigned: 'warning',
    in_progress: '',
    resolved: 'success',
    verified: 'success',
    reopened: 'warning',
    closed: 'info',
    postponed: 'info',
    wontfix: 'danger',
  }
  return map[s] ?? 'info'
}

function severityLabel(s: string) {
  return SEVERITY_OPTIONS.find((o) => o.value === s)?.label || s
}

function severityTagType(s: string): '' | 'success' | 'info' | 'warning' | 'danger' {
  const map: Record<string, '' | 'success' | 'info' | 'warning' | 'danger'> = {
    critical: 'danger',
    major: 'warning',
    moderate: '',
    minor: 'info',
    trivial: 'info',
  }
  return map[s] ?? 'info'
}

function priorityLabel(p: string) {
  return PRIORITY_OPTIONS.find((o) => o.value === p)?.label || p
}

function priorityTagType(p: string): '' | 'success' | 'info' | 'warning' | 'danger' {
  const map: Record<string, '' | 'success' | 'info' | 'warning' | 'danger'> = {
    urgent: 'danger',
    high: 'warning',
    medium: '',
    low: 'info',
  }
  return map[p] ?? 'info'
}

function historyActionLabel(action: string) {
  const map: Record<string, string> = {
    created: '创建了 Bug',
    status_changed: '变更了状态',
    assigned: '指派了 Bug',
    severity_changed: '修改了严重程度',
    priority_changed: '修改了优先级',
    resolved: '标记为已解决',
    reopened: '重新打开了 Bug',
    closed: '关闭了 Bug',
  }
  return map[action] || action
}

function aiStatusLabel(status: string) {
  const map: Record<string, string> = {
    processing: 'AI 分析中…',
    completed: '分析完成',
    failed: '分析失败',
  }
  return map[status] || status
}

function aiStatusTagType(status: string): '' | 'success' | 'info' | 'warning' | 'danger' {
  const map: Record<string, '' | 'success' | 'info' | 'warning' | 'danger'> = {
    processing: 'warning',
    completed: 'success',
    failed: 'danger',
  }
  return map[status] ?? 'info'
}

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

onMounted(() => {
  loadBugs()
  loadBugStats()
  loadProjectMembers()
})
onUnmounted(stopAiPolling)
</script>

<style scoped lang="scss">
.bugs-page {
  min-height: 100%;
}

// ── 统计卡片 ──────────────────────────────────────────────

.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

// ── 筛选栏 ──────────────────────────────────────────────

.filter-bar {
  background: #fff;
  border-radius: 12px;
  padding: 16px 20px;
  margin-bottom: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);

  .filter-fields {
    display: flex;
    flex-wrap: wrap;
    gap: 16px 24px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--el-border-color-light);
    margin-bottom: 16px;
  }

  .filter-field {
    display: flex;
    flex-direction: column;
    gap: 6px;
    width: calc(16.666% - 20px);
    min-width: 140px;

    label {
      font-size: 12px;
      font-weight: 500;
      color: var(--el-text-color-secondary);
    }

    :deep(.el-input),
    :deep(.el-select) {
      width: 100%;
    }
  }

  .filter-actions {
    display: flex;
    align-items: center;
    gap: 12px;
    justify-content: flex-end;
  }
}

// ── 视图切换 ──────────────────────────────────────────────

.view-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 20px;
  border-bottom: 1px solid var(--el-border-color-light);

  .view-left {
    :deep(.el-radio-button__inner) {
      padding: 6px 16px;
      font-size: 13px;
    }
  }

  .view-right {
    display: flex;
    align-items: center;
    gap: 12px;

    .result-hint {
      font-size: 13px;
      color: var(--el-text-color-secondary);
    }
  }
}

// ── 卡片视图 ──────────────────────────────────────────────

.card-view {
  padding: 16px;

  .card-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
  }

  .bug-card {
    background: #fff;
    border-radius: 12px;
    padding: 16px;
    cursor: pointer;
    transition: all 0.2s ease;
    border: 1px solid var(--el-border-color-light);

    &:hover {
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
      transform: translateY(-2px);
    }

    .card-header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 12px;

      .bug-key {
        font-family: 'JetBrains Mono', 'Fira Code', monospace;
        font-size: 14px;
        font-weight: 600;
        color: var(--theme-color-2563eb);
      }
    }

    .card-body {
      margin-bottom: 12px;

      .bug-title {
        font-size: 15px;
        font-weight: 500;
        color: var(--theme-text-strong);
        margin: 0 0 8px;
        line-height: 1.4;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
      }

      .bug-desc {
        font-size: 13px;
        color: var(--el-text-color-secondary);
        line-height: 1.5;
        margin: 0;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
      }
    }

    .card-meta {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      margin-bottom: 12px;

      .severity-pill,
      .priority-pill {
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 12px;
        font-weight: 500;
      }

      .severity-critical {
        background: var(--theme-color-fef2f2);
        color: var(--theme-color-d946ef);
      }
      .severity-major {
        background: var(--theme-color-fef3c7);
        color: var(--theme-color-f59e0b);
      }
      .severity-moderate {
        background: var(--theme-color-f0f9ff);
        color: var(--theme-color-0ea5e9);
      }
      .severity-minor,
      .severity-trivial {
        background: var(--theme-color-f1f5f9);
        color: var(--theme-color-64748b);
      }

      .priority-urgent {
        background: var(--theme-color-fef2f2);
        color: var(--theme-color-d946ef);
      }
      .priority-high {
        background: var(--theme-color-fef3c7);
        color: var(--theme-color-f59e0b);
      }
      .priority-medium {
        background: var(--theme-color-f0fdf4);
        color: var(--theme-color-10b981);
      }
      .priority-low {
        background: var(--theme-color-f1f5f9);
        color: var(--theme-color-64748b);
      }

      .assignee {
        font-size: 12px;
        color: var(--el-text-color-secondary);
        margin-left: auto;
      }
    }

    .card-footer {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-top: 12px;
      border-top: 1px solid var(--el-border-color-light);

      .create-time {
        font-size: 12px;
        color: var(--el-text-color-secondary);
      }

      .card-actions {
        display: flex;
        gap: 4px;

        .icon-btn-sm {
          width: 28px;
          height: 28px;
          display: flex;
          align-items: center;
          justify-content: center;
          border-radius: 6px;
          background: var(--el-fill-color-extra-light);
          border: none;
          cursor: pointer;
          color: var(--el-text-color-secondary);
          transition: all 0.2s;

          &:hover {
            background: var(--el-color-primary-light-9);
            color: var(--el-color-primary);
          }

          &.danger:hover {
            background: var(--el-color-danger-light-9);
            color: var(--el-color-danger);
          }

          i {
            font-size: 14px;
          }
        }
      }
    }
  }
}

// ── 表格视图 ──────────────────────────────────────────────

.table-view {
  :deep(.el-table) {
    --el-table-row-hover-bg-color: var(--el-color-primary-light-9);
  }

  :deep(.el-table__header-wrapper) {
    background: var(--el-fill-color-extra-light);
  }

  :deep(.el-table__body tr:hover) {
    td {
      background: var(--el-color-primary-light-9) !important;
    }
  }
}

// ── 状态/优先级/严重程度 Pill ────────────────────────────

.status-pill,
.severity-pill,
.priority-pill {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.status-new,
.status-assigned,
.status-reopened {
  background: var(--theme-color-fef3c7);
  color: var(--theme-color-f59e0b);
}

.status-in_progress {
  background: var(--theme-color-f0f9ff);
  color: var(--theme-color-0ea5e9);
}

.status-resolved,
.status-verified {
  background: var(--theme-color-f0fdf4);
  color: var(--theme-color-10b981);
}

.status-closed,
.status-postponed {
  background: var(--theme-color-f1f5f9);
  color: var(--theme-color-64748b);
}

.status-wontfix {
  background: var(--theme-color-fef2f2);
  color: var(--theme-color-d946ef);
}

:deep(.severity-pill) {
  &.severity-critical {
    background: var(--theme-color-fef2f2);
    color: var(--theme-color-d946ef);
  }
  &.severity-major {
    background: var(--theme-color-fef3c7);
    color: var(--theme-color-f59e0b);
  }
  &.severity-moderate {
    background: var(--theme-color-f0f9ff);
    color: var(--theme-color-0ea5e9);
  }
  &.severity-minor,
  &.severity-trivial {
    background: var(--theme-color-f1f5f9);
    color: var(--theme-color-64748b);
  }
}

:deep(.priority-pill) {
  &.priority-urgent {
    background: var(--theme-color-fef2f2);
    color: var(--theme-color-d946ef);
  }
  &.priority-high {
    background: var(--theme-color-fef3c7);
    color: var(--theme-color-f59e0b);
  }
  &.priority-medium {
    background: var(--theme-color-f0fdf4);
    color: var(--theme-color-10b981);
  }
  &.priority-low {
    background: var(--theme-color-f1f5f9);
    color: var(--theme-color-64748b);
  }
}

// ── 表格行操作 ────────────────────────────────────────────

.row-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.bug-key-cell {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 13px;
  color: var(--theme-color-2563eb);
}

.danger-text {
  color: var(--el-color-danger);
}

.muted-text {
  color: var(--el-text-color-secondary);
}

// ── 分页 ──────────────────────────────────────────────────

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  padding: 16px 20px;
  border-top: 1px solid var(--theme-color-f0f0f0);
}

// ── 抽屉 ──────────────────────────────────────────────────

.drawer-header-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;

  .drawer-title-row {
    display: flex;
    align-items: center;

    .drawer-bug-key {
      font-size: 16px;
      font-weight: 600;
      color: var(--theme-text-strong);
      font-family: 'JetBrains Mono', monospace;
    }
  }

  .drawer-action-row {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
}

.detail-tabs {
  :deep(.el-tabs__content) {
    padding: 4px 0 0;
  }
}

.bug-detail {
  padding-bottom: 24px;
}

.bug-detail-title {
  font-size: 17px;
  font-weight: 600;
  color: var(--theme-text-strong);
  line-height: 1.5;
  margin: 0 0 16px;
}

.detail-meta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 24px;
  padding: 14px 16px;
  background: var(--el-fill-color-extra-light);
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  margin-bottom: 16px;

  .meta-item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
  }

  .meta-label {
    color: var(--theme-color-94a3b8);
    min-width: 56px;
    flex-shrink: 0;
  }

  .meta-value {
    color: var(--theme-text-strong);
  }
}

.bug-tags-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 16px;

  .bug-tag {
    background: var(--theme-color-eff6ff);
    color: var(--theme-color-2563eb);
    border-color: var(--theme-color-bfdbfe);
  }
}

.detail-section {
  margin-bottom: 16px;

  &.half {
    flex: 1;
  }

  .section-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--el-text-color-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 6px;
  }

  .section-body {
    font-size: 14px;
    color: var(--theme-text-strong);
    line-height: 1.7;
    background: var(--el-fill-color-extra-light);
    padding: 10px 12px;
    border-radius: 6px;
    border: 1px solid var(--el-border-color-light);

    &.pre-wrap {
      white-space: pre-wrap;
    }

    &.actual {
      border-color: var(--el-color-danger-light-7);
      background: var(--theme-color-fff5f5);
    }
  }
}

.result-row {
  display: flex;
  gap: 16px;
}

// ── 历史记录 ──────────────────────────────────────────────

.history-panel {
  padding: 8px 0;
  min-height: 200px;

  .history-item {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
    font-size: 14px;

    .h-operator {
      font-weight: 500;
      color: var(--theme-text-strong);
    }

    .h-action {
      color: var(--el-text-color-regular);
    }

    .h-change {
      font-size: 12px;
      font-family: monospace;
      color: var(--theme-color-2563eb);
      background: var(--theme-color-eff6ff);
      padding: 1px 6px;
      border-radius: 4px;
    }

    .h-comment {
      width: 100%;
      margin: 4px 0 0;
      color: var(--theme-color-94a3b8);
      font-style: italic;
      font-size: 13px;
    }
  }
}

// ── AI 分析 ───────────────────────────────────────────────

.ai-panel {
  padding: 4px 0 24px;

  .ai-trigger-bar {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 20px;

    .ai-tip {
      font-size: 13px;
      color: var(--theme-color-94a3b8);
    }
  }

  .ai-status-row {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;

    .ai-time {
      font-size: 13px;
      color: var(--theme-color-94a3b8);
    }
  }

  .ai-block-title {
    font-size: 12px;
    font-weight: 600;
    color: var(--el-text-color-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin: 20px 0 8px;
  }

  .ai-json {
    background: var(--el-fill-color-extra-light);
    border: 1px solid var(--el-border-color-light);
    border-radius: 6px;
    padding: 12px;
    font-size: 12px;
    font-family: 'JetBrains Mono', monospace;
    color: var(--theme-text-strong);
    white-space: pre-wrap;
    word-break: break-all;
    max-height: 200px;
    overflow-y: auto;
    margin: 0;
  }

  .similar-bug-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 12px;
    background: var(--el-fill-color-extra-light);
    border: 1px solid var(--el-border-color-light);
    border-radius: 6px;
    margin-bottom: 6px;
    font-size: 13px;

    .sim-key {
      font-family: monospace;
      font-weight: 500;
      color: var(--theme-color-2563eb);
      min-width: 140px;
    }

    .sim-title {
      flex: 1;
      color: var(--theme-text-strong);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .sim-score {
      color: var(--theme-color-94a3b8);
      white-space: nowrap;
    }
  }
}

// ── 对话框表单提示 ────────────────────────────────────────

.form-tip {
  font-size: 12px;
  color: var(--el-color-danger);
  margin-top: 4px;
}

.resolve-hint {
  text-align: left;
  font-size: 14px;
  color: var(--el-text-color-regular);
  line-height: 1.8;

  p { margin: 4px 0; }

  ul {
    margin: 6px 0 0 16px;
    padding: 0;

    li { margin-bottom: 4px; }
  }
}

// ── 成员选项 ──────────────────────────────────────────────

.member-option {
  display: flex;
  align-items: center;
  gap: 8px;

  .member-name {
    font-weight: 500;
    color: var(--theme-text-strong);
  }

  .member-username {
    font-size: 12px;
    color: var(--theme-color-94a3b8);
    flex: 1;
  }

  .member-role {
    font-size: 11px;
    flex-shrink: 0;
  }
}
</style>
