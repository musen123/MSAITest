<template>
  <div class="sched-page">
    <AppPageHeader
      icon="i-solar-alarm-bold"
      title="定时任务"
      description="按 cron 或固定间隔定时执行测试任务，派发记录可回溯到任务中心"
      :breadcrumbs="['项目工作区', '定时任务']"
    >
      <template #actions>
        <el-button v-permission="'scheduler:create'" type="primary" @click="openCreate">
          <i class="i-solar-add-circle-bold btn-icon" />
          新建定时任务
        </el-button>
      </template>
    </AppPageHeader>

    <AppSectionCard padless>
      <div class="view-bar">
        <div class="view-left">
          <el-select
            v-model="query.job_type"
            placeholder="全部类型"
            clearable
            size="small"
            style="width: 130px"
            @change="handleSearch"
          >
            <el-option
              v-for="(m, k) in JOB_TYPE_META"
              :key="k"
              :label="m.label"
              :value="k"
            />
          </el-select>
          <el-select
            v-model="query.enabled"
            placeholder="全部状态"
            clearable
            size="small"
            style="width: 110px"
            @change="handleSearch"
          >
            <el-option label="已启用" :value="true" />
            <el-option label="已停用" :value="false" />
          </el-select>
          <el-input
            v-model="query.keyword"
            placeholder="搜索名称"
            clearable
            size="small"
            style="width: 180px"
            @keyup.enter="handleSearch"
            @clear="handleSearch"
          >
            <template #prefix><i class="i-solar-magnifer-linear" /></template>
          </el-input>
        </div>
        <span class="result-hint">共 {{ total }} 条</span>
      </div>

      <el-table v-loading="loading" :data="jobs" style="width: 100%">
        <el-table-column label="计划" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="job-cell">
              <span class="job-icon" :class="`jt-${JOB_TYPE_META[row.job_type as ScheduledJobType]?.color}`">
                <i :class="JOB_TYPE_META[row.job_type as ScheduledJobType]?.icon" />
              </span>
              <div class="job-text">
                <span class="job-name">{{ row.name }}</span>
                <span class="job-sub">
                  {{ JOB_TYPE_META[row.job_type as ScheduledJobType]?.label }}
                  · {{ row.target_name || `#${row.target_id}` }}
                </span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="调度规则" width="170">
          <template #default="{ row }">
            <code class="cron-code">{{ scheduleText(row) }}</code>
          </template>
        </el-table-column>
        <el-table-column label="下次运行" width="150">
          <template #default="{ row }">
            <span v-if="row.enabled && row.next_run_at" class="next-run">
              {{ utcToLocal(row.next_run_at) }}
            </span>
            <span v-else class="muted-text">已停用</span>
          </template>
        </el-table-column>
        <el-table-column label="上次派发" width="200">
          <template #default="{ row }">
            <template v-if="row.last_run_at">
              <span class="run-status" :class="`rs-${row.last_status}`">
                {{ lastStatusLabel(row.last_status) }}
              </span>
              <span class="muted-text run-time">{{ utcToLocal(row.last_run_at) }}</span>
            </template>
            <span v-else class="muted-text">从未运行</span>
          </template>
        </el-table-column>
        <el-table-column label="累计" width="70" align="center">
          <template #default="{ row }">{{ row.total_runs }}</template>
        </el-table-column>
        <el-table-column label="启用" width="80" align="center">
          <template #default="{ row }">
            <el-switch
              v-permission.disable="'scheduler:execute'"
              :model-value="row.enabled"
              @change="handleToggle(row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <div class="row-actions">
              <el-tooltip v-permission="'scheduler:execute'" content="立即执行一次" placement="top">
                <el-button type="primary" plain size="small" @click="handleRunNow(row)">
                  <i class="i-solar-play-bold btn-icon-sm" />
                </el-button>
              </el-tooltip>
              <el-button size="small" @click="openRuns(row)">
                <i class="i-solar-history-bold btn-icon-sm" />记录
              </el-button>
              <el-button v-permission="'scheduler:edit'" size="small" @click="openEdit(row)">
                <i class="i-solar-pen-linear btn-icon-sm" />编辑
              </el-button>
              <el-popconfirm
                v-permission="'scheduler:delete'"
                :title="`确定删除定时任务「${row.name}」?`"
                confirm-button-text="删除"
                cancel-button-text="取消"
                @confirm="handleDelete(row)"
              >
                <template #reference>
                  <el-button type="danger" plain size="small">
                    <i class="i-solar-trash-bin-trash-linear btn-icon-sm" />
                  </el-button>
                </template>
              </el-popconfirm>
            </div>
          </template>
        </el-table-column>
        <template #empty>
          <AppEmpty
            v-if="!loading"
            scene="data"
            description="还没有定时任务，创建一个让测试自动跑起来"
          >
            <template #actions>
              <el-button v-permission="'scheduler:create'" type="primary" @click="openCreate">
                <i class="i-solar-add-circle-bold btn-icon" />
                新建定时任务
              </el-button>
            </template>
          </AppEmpty>
        </template>
      </el-table>

      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.page_size"
          :page-sizes="[10, 20, 50]"
          :total="total"
          layout="total, sizes, prev, pager, next"
          background
          @size-change="loadData"
          @current-change="loadData"
        />
      </div>
    </AppSectionCard>

    <!-- 新建/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingJob ? '编辑定时任务' : '新建定时任务'"
      width="640px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="formRules"
        label-width="92px"
        label-position="left"
      >
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" maxlength="100" placeholder="如：每日回归测试" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" maxlength="500" placeholder="可选" />
        </el-form-item>
        <el-form-item label="执行对象" prop="job_type">
          <el-radio-group v-model="form.job_type" @change="onJobTypeChange">
            <el-radio-button
              v-for="(m, k) in JOB_TYPE_META"
              :key="k"
              :value="k"
            >{{ m.label }}</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item :label="targetLabel" prop="target_id">
          <el-select
            v-model="form.target_id"
            filterable
            :loading="targetLoading"
            :placeholder="`选择${targetLabel}`"
            style="width: 100%"
          >
            <el-option
              v-for="t in targetOptions"
              :key="t.id"
              :label="t.name"
              :value="t.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item
          v-if="!isAppJob"
          label="测试环境"
          :prop="envRequired ? 'environment_id' : ''"
        >
          <el-select
            v-model="form.environment_id"
            clearable
            :placeholder="envRequired ? '必选' : '可选（用例自带配置时可不选）'"
            style="width: 100%"
          >
            <el-option
              v-for="e in environments"
              :key="e.id"
              :label="`${e.name}（${e.base_url}）`"
              :value="e.id"
            />
          </el-select>
        </el-form-item>
        
        <el-form-item v-if="isAppJob" label="执行设备">
          <el-select
            v-model="form.device_udid"
            clearable
            filterable
            placeholder="可选（缺省用套件默认设备）"
            style="width: 100%"
          >
            <el-option
              v-for="d in appDevices"
              :key="d.udid"
              :label="`${d.model || d.serial}（${d.udid}）`"
              :value="d.udid"
            />
          </el-select>
        </el-form-item>

        <el-divider content-position="left">调度规则</el-divider>

        <el-form-item label="调度方式">
          <el-radio-group v-model="form.schedule_type">
            <el-radio-button value="cron">cron 表达式</el-radio-button>
            <el-radio-button value="interval">固定间隔</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <template v-if="form.schedule_type === 'cron'">
          <el-form-item label="常用预设">
            <div class="preset-row">
              <button
                v-for="p in CRON_PRESETS"
                :key="p.value"
                type="button"
                class="preset-chip"
                :class="{ active: form.cron_expr === p.value }"
                @click="applyPreset(p.value)"
              >{{ p.label }}</button>
            </div>
          </el-form-item>
          <el-form-item label="表达式" prop="cron_expr">
            <el-input
              v-model="form.cron_expr"
              placeholder="分 时 日 月 周，如 0 2 * * *"
              @change="previewCron"
            >
              <template #append>
                <el-button @click="previewCron">预览</el-button>
              </template>
            </el-input>
            <div v-if="cronPreview.length" class="cron-preview">
              <i class="i-solar-clock-circle-linear" />
              即将运行：{{ cronPreview.join('　') }}
            </div>
            <div v-else-if="cronInvalid" class="cron-preview is-error">
              <i class="i-solar-danger-circle-linear" />
              表达式无效
            </div>
          </el-form-item>
        </template>
        <el-form-item v-else label="间隔" prop="interval_seconds">
          <el-input-number
            v-model="form.interval_seconds"
            :min="60"
            :step="60"
            :max="2592000"
          />
          <span class="interval-hint">秒（最小 60）≈ {{ intervalText }}</span>
        </el-form-item>

        <el-form-item label="并行策略">
          <el-switch
            v-model="form.allow_overlap"
            active-text="允许并行"
            inactive-text="上次未完成则跳过"
          />
        </el-form-item>
        <el-form-item label="立即启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">
          {{ editingJob ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 派发记录抽屉 -->
    <el-drawer
      v-model="runsVisible"
      :title="`派发记录：${runsJob?.name || ''}`"
      size="520px"
    >
      <el-table v-loading="runsLoading" :data="runs" size="small">
        <el-table-column label="派发时间" width="150">
          <template #default="{ row }">{{ utcToLocal(row.fired_at) }}</template>
        </el-table-column>
        <el-table-column label="派发结果" width="100">
          <template #default="{ row }">
            <span class="run-status" :class="`rs-${row.status}`">
              {{ lastStatusLabel(row.status) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="执行状态" width="90">
          <template #default="{ row }">
            <span v-if="row.task_status" class="run-status" :class="`ts-${row.task_status}`">
              {{ taskStatusLabel(row.task_status) }}
            </span>
            <span v-else class="muted-text">—</span>
          </template>
        </el-table-column>
        <el-table-column label="详情" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">
            <el-button
              v-if="row.ai_task_id"
              link
              type="primary"
              size="small"
              @click="goTask(row.ai_task_id)"
            >查看任务 #{{ row.ai_task_id }}</el-button>
            <span v-else class="muted-text">{{ row.note || '—' }}</span>
          </template>
        </el-table-column>
        <template #empty>
          <AppEmpty v-if="!runsLoading" scene="data" description="暂无派发记录" />
        </template>
      </el-table>
      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="runsQuery.page"
          :page-size="runsQuery.page_size"
          :total="runsTotal"
          layout="total, prev, pager, next"
          small
          background
          @current-change="loadRuns"
        />
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">import { ref, reactive, computed, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage, type FormInstance, type FormRules } from 'element-plus';
import { AppPageHeader, AppSectionCard, AppEmpty } from '@/components/common';
import { scheduledJobApi, JOB_TYPE_META, CRON_PRESETS, type ScheduledJob, type ScheduledJobRun, type ScheduledJobType, } from '@/api/scheduled-jobs';
import { environmentApi, type Environment } from '@/api/environments';
import { appTestApi } from '@/api/appTest';
import { appDeviceApi, type AppDevice } from '@/api/appDevice';
const route = useRoute();
const router = useRouter();
const projectId = computed(() => Number(route.params.id));
// 权限门控改用 v-permission 指令（与后端 scheduled_jobs 端点的 require_permission 同口径）
// ── 列表 ──
const loading = ref(false);
const jobs = ref<ScheduledJob[]>([]);
const total = ref(0);
const query = reactive({
    job_type: '' as '' | ScheduledJobType,
    enabled: undefined as boolean | undefined,
    keyword: '',
    page: 1,
    page_size: 20,
});
async function loadData() {
    loading.value = true;
    try {
        const params: Record<string, unknown> = {
            page: query.page,
            page_size: query.page_size,
        };
        if (query.job_type)
            params.job_type = query.job_type;
        if (query.enabled !== undefined)
            params.enabled = query.enabled;
        if (query.keyword)
            params.keyword = query.keyword;
        const res = await scheduledJobApi.list(projectId.value, params);
        jobs.value = res.data.items;
        total.value = res.data.total;
    }
    catch (err) {
        console.error(err);
    }
    finally {
        loading.value = false;
    }
}
function handleSearch() {
    query.page = 1;
    loadData();
}
onMounted(() => {
    loadData();
    loadEnvironments();
});
// ── 展示工具 ──
/** 后端时间为 UTC naive，补 Z 后按本地时区显示 */
function utcToLocal(s?: string | null): string {
    if (!s)
        return '—';
    const d = new Date(s.endsWith('Z') ? s : `${s}Z`);
    const p = (n: number) => String(n).padStart(2, '0');
    return `${d.getMonth() + 1}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}
function scheduleText(row: ScheduledJob): string {
    if (row.schedule_type === 'interval') {
        return `每 ${intervalLabel(row.interval_seconds || 0)}`;
    }
    const preset = CRON_PRESETS.find((c) => c.value === row.cron_expr);
    return preset ? preset.label : row.cron_expr || '—';
}
function intervalLabel(s: number): string {
    if (s < 3600)
        return `${Math.round(s / 60)} 分钟`;
    if (s < 86400)
        return `${Math.round((s / 3600) * 10) / 10} 小时`;
    return `${Math.round((s / 86400) * 10) / 10} 天`;
}
function lastStatusLabel(s?: string | null): string {
    return ({
        dispatched: '已派发',
        skipped_overlap: '跳过',
        failed: '失败',
    } as Record<string, string>)[s || ''] || s || '—';
}
function taskStatusLabel(s: string): string {
    return ({
        pending: '排队中',
        running: '运行中',
        succeeded: '成功',
        failed: '失败',
        canceled: '已取消',
    } as Record<string, string>)[s] || s;
}
// ── 行操作 ──
async function handleToggle(row: ScheduledJob) {
    try {
        const res = await scheduledJobApi.toggle(projectId.value, row.id);
        ElMessage.success(res.data.enabled ? '已启用' : '已停用');
        loadData();
    }
    catch (err) {
        console.error(err);
    }
}
async function handleRunNow(row: ScheduledJob) {
    try {
        const res = await scheduledJobApi.runNow(projectId.value, row.id);
        ElMessage.success(`已触发执行（任务 #${res.data.ai_task_id}）`);
        loadData();
    }
    catch (err) {
        console.error(err);
    }
}
async function handleDelete(row: ScheduledJob) {
    try {
        await scheduledJobApi.remove(projectId.value, row.id);
        ElMessage.success('已删除');
        if (jobs.value.length === 1 && query.page > 1)
            query.page -= 1;
        loadData();
    }
    catch (err) {
        console.error(err);
    }
}
// ── 新建 / 编辑 ──
const dialogVisible = ref(false);
const submitting = ref(false);
const editingJob = ref<ScheduledJob | null>(null);
const formRef = ref<FormInstance>();
const form = reactive({
    name: '',
    description: '',
    job_type: 'app_suite' as ScheduledJobType,
    target_id: undefined as number | undefined,
    environment_id: undefined as number | undefined,
    run_mode: '',
    device_udid: '',
    schedule_type: 'cron' as 'cron' | 'interval',
    cron_expr: '0 2 * * *',
    interval_seconds: 3600,
    allow_overlap: false,
    enabled: true,
});
const formRules: FormRules = {
    name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
    target_id: [{ required: true, message: '请选择执行对象', trigger: 'change' }],
    environment_id: [
        { required: true, message: '请选择测试环境', trigger: 'change' },
    ],
    cron_expr: [{ required: true, message: '请输入 cron 表达式', trigger: 'blur' }],
    interval_seconds: [{ required: true, message: '请输入间隔', trigger: 'blur' }],
};
const targetLabel = computed(() => JOB_TYPE_META[form.job_type]?.label || '执行对象');
// 压测必须指定执行环境（base_url 来源）；API 任务亦必选
const envRequired = computed(() => false);
// run_mode（回放/Agent）为 Web 专属
const isWebJob = computed(() => false);
// App 套件跑真机：不用测试环境，改配执行设备（可选，缺省用套件默认设备）
const isAppJob = computed(() => form.job_type === 'app_suite');
const intervalText = computed(() => intervalLabel(form.interval_seconds || 0));
function openCreate() {
    editingJob.value = null;
    Object.assign(form, {
        name: '',
        description: '',
        job_type: 'app_suite',
        target_id: undefined,
        environment_id: undefined,
        run_mode: '',
        device_udid: '',
        schedule_type: 'cron',
        cron_expr: '0 2 * * *',
        interval_seconds: 3600,
        allow_overlap: false,
        enabled: true,
    });
    cronPreview.value = [];
    cronInvalid.value = false;
    dialogVisible.value = true;
    loadTargets();
}
function openEdit(row: ScheduledJob) {
    editingJob.value = row;
    Object.assign(form, {
        name: row.name,
        description: row.description || '',
        job_type: row.job_type,
        target_id: row.target_id,
        environment_id: row.params?.environment_id ?? undefined,
        run_mode: row.params?.run_mode || '',
        device_udid: row.params?.device_udid || '',
        schedule_type: row.schedule_type,
        cron_expr: row.cron_expr || '0 2 * * *',
        interval_seconds: row.interval_seconds || 3600,
        allow_overlap: row.allow_overlap,
        enabled: row.enabled,
    });
    cronPreview.value = [];
    cronInvalid.value = false;
    dialogVisible.value = true;
    loadTargets();
    if (form.schedule_type === 'cron')
        previewCron();
}
async function handleSubmit() {
    if (!formRef.value)
        return;
    const ok = await formRef.value.validate().catch(() => false);
    if (!ok)
        return;
    submitting.value = true;
    try {
        const payload = {
            name: form.name,
            description: form.description || undefined,
            job_type: form.job_type,
            target_id: form.target_id!,
            params: {
                environment_id: form.environment_id ?? null,
                run_mode: form.run_mode || null,
                device_udid: form.device_udid || null,
            },
            schedule_type: form.schedule_type,
            cron_expr: form.schedule_type === 'cron' ? form.cron_expr : null,
            interval_seconds: form.schedule_type === 'interval' ? form.interval_seconds : null,
            enabled: form.enabled,
            allow_overlap: form.allow_overlap,
        };
        if (editingJob.value) {
            await scheduledJobApi.update(projectId.value, editingJob.value.id, payload);
            ElMessage.success('已保存');
        }
        else {
            await scheduledJobApi.create(projectId.value, payload);
            ElMessage.success('已创建');
        }
        dialogVisible.value = false;
        loadData();
    }
    catch (err) {
        console.error(err);
    }
    finally {
        submitting.value = false;
    }
}
// ── 执行对象 / 环境 ──
const targetOptions = ref<{
    id: number;
    name: string;
}[]>([]);
const targetLoading = ref(false);
const environments = ref<Environment[]>([]);
const appDevices = ref<AppDevice[]>([]);
function onJobTypeChange() {
    form.target_id = undefined;
    loadTargets();
}
async function loadTargets() { targetLoading.value = true; targetOptions.value = []; try { const res = await appTestApi.listSuites(projectId.value, { page_size: 100 }); targetOptions.value = res.items.map((item: {id: number; name: string}) => ({id: item.id, name: item.name})); } finally { targetLoading.value = false; } }
async function loadEnvironments() {
    try {
        const res = await environmentApi.getEnvironmentList(projectId.value);
        environments.value = res.data || [];
    }
    catch (err) {
        console.error(err);
    }
}
// ── cron 预设与预览 ──
const cronPreview = ref<string[]>([]);
const cronInvalid = ref(false);
function applyPreset(value: string) {
    form.cron_expr = value;
    previewCron();
}
async function previewCron() {
    if (!form.cron_expr)
        return;
    try {
        const res = await scheduledJobApi.validateCron(projectId.value, form.cron_expr);
        cronInvalid.value = !res.data.valid;
        cronPreview.value = res.data.valid ? res.data.next_runs : [];
    }
    catch (err) {
        console.error(err);
    }
}
// ── 派发记录 ──
const runsVisible = ref(false);
const runsLoading = ref(false);
const runsJob = ref<ScheduledJob | null>(null);
const runs = ref<ScheduledJobRun[]>([]);
const runsTotal = ref(0);
const runsQuery = reactive({ page: 1, page_size: 20 });
function openRuns(row: ScheduledJob) {
    runsJob.value = row;
    runsQuery.page = 1;
    runsVisible.value = true;
    loadRuns();
}
async function loadRuns() {
    if (!runsJob.value)
        return;
    runsLoading.value = true;
    try {
        const res = await scheduledJobApi.listRuns(projectId.value, runsJob.value.id, {
            page: runsQuery.page,
            page_size: runsQuery.page_size,
        });
        runs.value = res.data.items;
        runsTotal.value = res.data.total;
    }
    catch (err) {
        console.error(err);
    }
    finally {
        runsLoading.value = false;
    }
}
function goTask(taskId: number) {
    router.push({
        name: 'AiTaskDetail',
        params: { id: projectId.value, taskId },
    });
}
</script>

<style scoped lang="scss">
.sched-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.btn-icon {
  margin-right: 6px;
  font-size: 16px;
  vertical-align: -3px;
}
.btn-icon-sm {
  margin-right: 4px;
  font-size: 14px;
  vertical-align: -2px;
}

.view-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-5);
  border-bottom: 1px solid var(--border-light);
}
.view-left {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.result-hint {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
}

.job-cell {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}
.job-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  flex-shrink: 0;

  &.jt-info { background: var(--color-info-50); color: var(--color-info-600); }
  &.jt-purple { background: var(--color-purple-50); color: var(--color-purple-600); }
  &.jt-success { background: var(--color-success-50); color: var(--color-success-600); }
  &.jt-primary { background: var(--brand-50); color: var(--brand-600); }
}
.job-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.job-name {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
}
.job-sub {
  font-size: 11px;
  color: var(--text-secondary);
}

.cron-code {
  font-family: var(--font-mono);
  font-size: 12px;
  padding: 2px 8px;
  border-radius: var(--radius-xs);
  background: var(--gray-100);
  color: var(--text-regular);
}
.next-run {
  font-size: var(--font-size-sm);
  color: var(--brand-600);
  font-variant-numeric: tabular-nums;
}
.muted-text {
  color: var(--text-placeholder);
  font-size: var(--font-size-xs);
}
.run-time { margin-left: 6px; }

.run-status {
  display: inline-flex;
  align-items: center;
  padding: 1px 8px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: var(--font-weight-medium);

  &.rs-dispatched { background: var(--color-success-50); color: var(--color-success-600); }
  &.rs-skipped_overlap { background: var(--color-warning-50); color: var(--color-warning-600); }
  &.rs-failed { background: var(--color-danger-50); color: var(--color-danger-600); }
  &.ts-succeeded { background: var(--color-success-50); color: var(--color-success-600); }
  &.ts-failed { background: var(--color-danger-50); color: var(--color-danger-600); }
  &.ts-running { background: var(--brand-50); color: var(--brand-600); }
  &.ts-pending { background: var(--gray-100); color: var(--gray-600); }
  &.ts-canceled { background: var(--color-warning-50); color: var(--color-warning-600); }
}

.row-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;

  :deep(.el-button) {
    margin: 0;
  }
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  padding: var(--space-4) var(--space-4) var(--space-2);
  border-top: 1px solid var(--border-light);
}

/* cron 预设 chips */
.preset-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.preset-chip {
  height: 26px;
  padding: 0 12px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-full);
  background: var(--bg-card);
  font-size: var(--font-size-xs);
  color: var(--text-regular);
  cursor: pointer;
  transition: all 0.15s;

  &:hover {
    border-color: var(--brand-300);
    color: var(--brand-600);
  }
  &.active {
    border-color: var(--brand-500);
    background: var(--brand-50);
    color: var(--brand-600);
    font-weight: var(--font-weight-medium);
  }
}
.cron-preview {
  margin-top: 6px;
  font-size: var(--font-size-xs);
  color: var(--color-success-600);
  display: flex;
  align-items: center;
  gap: 4px;

  &.is-error { color: var(--color-danger-500); }
}
.interval-hint {
  margin-left: var(--space-3);
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
}

:deep(.el-table) {
  --el-table-border-color: var(--border-light);

  th.el-table__cell {
    background: var(--gray-50) !important;
    color: var(--text-secondary) !important;
    font-weight: var(--font-weight-medium);
    font-size: var(--font-size-xs);
  }
  td.el-table__cell {
    padding: 12px 0;
    font-size: var(--font-size-sm);
  }
}
</style>
