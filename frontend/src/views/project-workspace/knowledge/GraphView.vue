<template>
  <div class="graph-page">
    <!-- 左侧面板 -->
    <div class="side-panel">
      <div class="search-section">
        <el-select
          v-model="selectedLabel"
          filterable
          remote
          :remote-method="handleSearchLabels"
          placeholder="搜索实体名称..."
          size="default"
          class="full-select"
          @change="handleExploreNode"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
          <el-option v-for="label in labelOptions" :key="label" :label="label" :value="label" />
        </el-select>
      </div>

      <div class="params-section">
        <div class="section-title">参数配置</div>
        <div class="param-row">
          <span class="param-name">查询深度</span>
          <el-input-number
            v-model="graphParams.max_depth"
            :min="1"
            :max="3"
            size="small"
            style="width: 100px"
          />
        </div>
        <div class="param-row">
          <span class="param-name">最大节点</span>
          <el-input-number
            v-model="graphParams.max_nodes"
            :min="10"
            :max="500"
            :step="50"
            size="small"
            style="width: 100px"
          />
        </div>
        <el-button
          size="small"
          type="primary"
          plain
          style="width: 100%; margin-top: 6px"
          :loading="exploring"
          @click="handleExploreNode(selectedLabel || '*')"
        >
          查询图谱
        </el-button>
      </div>

      <div class="labels-section">
        <div class="section-title">热门实体</div>
        <div v-if="popularLabels.length" class="label-list">
          <div
            v-for="label in popularLabels"
            :key="label"
            class="label-chip"
            :class="{ active: selectedLabel === label }"
            @click="selectedLabel = label; handleExploreNode(label)"
          >
            {{ label }}
          </div>
        </div>
        <div v-else class="label-empty">暂无实体（先在「项目文档」提取图谱）</div>
        <el-button size="small" text style="margin-top: 6px" @click="loadPopularLabels">
          刷新标签
        </el-button>
      </div>

      <div v-if="graphData" class="info-section">
        <div class="section-title">图谱信息</div>
        <div class="info-row"><span>起始节点</span><span class="info-val">{{ currentLabel === '*' ? '全部图谱' : currentLabel }}</span></div>
        <div class="info-row"><span>节点数</span><span class="info-val">{{ nodeCount }}</span></div>
        <div class="info-row"><span>边数</span><span class="info-val">{{ edgeCount }}</span></div>
        <div v-if="graphData.is_truncated" class="info-row">
          <span>预算截断</span>
          <span class="info-val truncated-val">已截断</span>
        </div>
      </div>
    </div>

    <!-- 右侧主区 -->
    <div class="graph-main">
      <div class="graph-toolbar">
        <div class="toolbar-left">
          <el-radio-group v-model="viewMode" size="small" @change="renderCurrentGraph">
            <el-radio-button value="force">力导向图</el-radio-button>
            <el-radio-button value="circular">环形图</el-radio-button>
            <el-radio-button value="tree">树形图</el-radio-button>
          </el-radio-group>
        </div>
        <div class="toolbar-right">
          <span v-if="graphData?.is_truncated" class="truncated-tag">
            超出预算已截断（≤{{ graphParams.max_nodes }} 节点）
          </span>
        </div>
      </div>

      <div class="chart-container">
        <div v-if="!hasGraph" v-loading="exploring" class="chart-empty">
          <template v-if="!exploring">
            <el-icon :size="40"><Share /></el-icon>
            <h3>知识图谱可视化</h3>
            <p>本项目还没有图谱数据；图谱从项目文档自动提取生成</p>
            <el-button size="small" type="primary" plain @click="goDocuments">
              去「项目文档」提取图谱
            </el-button>
          </template>
        </div>
        <div v-else ref="chartRef" class="chart-box"></div>
      </div>

      <!-- 节点详情面板 -->
      <div v-if="detail" class="detail-panel">
        <div class="detail-header">
          <div class="detail-title">
            {{ detail.name }}
            <span v-if="detail.human_edited" class="edited-badge" title="人工编辑保护位已置位">已修编</span>
          </div>
          <button class="close-btn" @click="closeDetail">✕</button>
        </div>
        <div v-loading="detailLoading" class="detail-body">
          <template v-if="panelMode === 'view'">
            <div class="detail-field">
              <div class="field-label">实体类型</div>
              <div class="field-value">
                <span class="type-pill" :style="{ background: typeColor(detail.entity_type) }" />
                {{ entityTypeLabel(detail.entity_type) }}
              </div>
            </div>
            <div class="detail-field">
              <div class="field-label">描述</div>
              <div class="field-value" :class="{ 'field-empty': !detail.description }">
                {{ detail.description || '-' }}
              </div>
            </div>
            <div class="detail-field">
              <div class="field-label">引用 / 文档数</div>
              <div class="field-value">{{ detail.ref_count }} 次 · {{ detail.doc_count }} 份文档</div>
            </div>

            <div class="related-section">
              <div class="field-label">来源出处（{{ detail.mentions.length }}）</div>
              <div v-if="detail.mentions.length" class="mention-list">
                <div v-for="(m, mi) in detail.mentions" :key="mi" class="mention-item">
                  <div class="mention-doc">{{ m.doc_name }}</div>
                  <div v-if="m.heading_path" class="mention-crumb">{{ m.heading_path }}</div>
                </div>
              </div>
              <div v-else class="field-value field-empty">暂无出处记录</div>
            </div>

            <div class="related-section">
              <div class="field-label">关联关系（{{ detail.relations.length }}）</div>
              <div v-if="detail.relations.length" class="related-list">
                <div
                  v-for="rel in detail.relations"
                  :key="rel.id"
                  class="related-node-item"
                  @click="handleClickRelatedNode(rel)"
                >
                  <div class="related-node-main">
                    <span class="related-node-direction" :class="rel.source === detail.id ? 'out' : 'in'">
                      {{ rel.source === detail.id ? '→' : '←' }}
                    </span>
                    <span class="related-node-name">
                      {{ rel.source === detail.id ? rel.target_name : rel.source_name }}
                    </span>
                  </div>
                  <div v-if="rel.keywords" class="related-node-relation">{{ rel.keywords }}</div>
                </div>
              </div>
              <div v-else class="field-value field-empty">暂无关联关系</div>
            </div>

            <div class="detail-actions">
              <el-button v-permission="'knowledge:manage'" size="small" type="primary" plain @click="startEditNode">编辑</el-button>
              <el-button v-permission="'knowledge:manage'" size="small" plain @click="startMerge">合并</el-button>
              <el-button v-permission="'knowledge:manage'" size="small" type="danger" plain @click="handleDeleteEntity">删除</el-button>
            </div>
          </template>

          <template v-else-if="panelMode === 'edit'">
            <div class="edit-field">
              <div class="field-label">实体名（改名将保留旧名重定向）</div>
              <el-input v-model="editForm.name" placeholder="实体名" />
            </div>
            <div class="edit-field">
              <div class="field-label">实体类型</div>
              <el-select v-model="editForm.entity_type" class="full-select">
                <el-option
                  v-for="t in ENTITY_TYPE_OPTIONS"
                  :key="t.value"
                  :label="t.label"
                  :value="t.value"
                />
              </el-select>
            </div>
            <div class="edit-field">
              <div class="field-label">描述</div>
              <el-input
                v-model="editForm.description"
                type="textarea"
                :rows="4"
                placeholder="实体描述..."
              />
            </div>
            <div class="detail-actions">
              <el-button size="small" @click="panelMode = 'view'">取消</el-button>
              <el-button
                size="small"
                type="primary"
                :loading="savingNode"
                @click="handleSaveNode"
              >
                保存
              </el-button>
            </div>
          </template>

          <template v-else>
            <div class="edit-field">
              <div class="field-label">将「{{ detail.name }}」合并到…</div>
              <el-select
                v-model="mergeTargetId"
                filterable
                remote
                :remote-method="handleSearchMergeTarget"
                :loading="mergeSearching"
                placeholder="搜索目标实体"
                class="full-select"
              >
                <el-option
                  v-for="opt in mergeOptions"
                  :key="opt.id"
                  :label="`${opt.name}（${entityTypeLabel(opt.entity_type)} · 引用 ${opt.ref_count}）`"
                  :value="opt.id"
                  :disabled="opt.id === detail.id"
                />
              </el-select>
              <div class="merge-hint">
                合并后本实体的出处与关系将并入目标实体，旧名保留重定向，后续自动抽取不再分裂。
              </div>
            </div>
            <div class="detail-actions">
              <el-button size="small" @click="panelMode = 'view'">取消</el-button>
              <el-button
                size="small"
                type="primary"
                :disabled="!mergeTargetId"
                :loading="merging"
                @click="handleMerge"
              >
                确认合并
              </el-button>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">import { ref, reactive, computed, nextTick, onMounted, onUnmounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import * as echarts from 'echarts';
import { Search, Share } from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { knowledgeGraphApi } from '@/api/knowledge';
import type { KbEntityDetail, KbEntityRelationItem, KbGraphNode, KbSubgraphData, } from '@/types/knowledge';
const route = useRoute();
const router = useRouter();
const projectId = computed(() => Number(route.params.id));
// ===== 实体类型词表（与后端 KbEntityType 对齐，10 类封顶） =====
const ENTITY_TYPE_OPTIONS: {
    value: string;
    label: string;
}[] = [
    { value: 'system', label: '系统/服务' },
    { value: 'module', label: '模块/组件' },
    { value: 'page', label: '页面/界面' },
    { value: 'role', label: '角色' },
    { value: 'business_rule', label: '业务规则' },
    { value: 'data_object', label: '数据对象' },
    { value: 'config', label: '配置项' },
    { value: 'term', label: '术语' },
    { value: 'metric', label: '指标/阈值' }
];
const entityTypeLabel = (t: string): string => ENTITY_TYPE_OPTIONS.find((o) => o.value === t)?.label || t || '术语';
/** 读设计 token（文字/背景随主题)；类型色板量大于语义 token 数，超出部分固定
 *  hex（浅/深两主题均有足够对比，与 ECharts 系列色硬编码的仓库先例一致） */
const cssVar = (name: string, fallback: string): string => {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fallback;
};
const TYPE_COLOR_FALLBACK: Record<string, string> = {
    system: '#7c3aed',
    module: '#6366f1',
    page: '#14b8a6',
    role: '#f59e0b',
    business_rule: '#ef4444',
    data_object: '#10b981',
    config: '#64748b',
    term: '#a5b4fc',
    metric: '#ec4899'
};
const typeColor = (t: string): string => {
    if (t === 'system')
        return cssVar('--brand-600', TYPE_COLOR_FALLBACK.system);
    return TYPE_COLOR_FALLBACK[t] || TYPE_COLOR_FALLBACK.term;
};
// ===== 状态 =====
const selectedLabel = ref('');
const labelOptions = ref<string[]>([]);
const popularLabels = ref<string[]>([]);
const graphData = ref<KbSubgraphData | null>(null);
const currentLabel = ref('');
const nodeCount = ref(0);
const edgeCount = ref(0);
const viewMode = ref<'force' | 'circular' | 'tree'>('force');
const exploring = ref(false);
const graphParams = reactive({
    max_depth: 3,
    // 默认取满预算上限：进页自动加载「全部图谱」，当前量级（数百实体）一次装下
    max_nodes: 500,
});
/** 有可渲染的图数据（加载过但为空 → 显示「去提取」空态） */
const hasGraph = computed(() => !!graphData.value && graphData.value.nodes.length > 0);
const chartRef = ref<HTMLElement>();
let chartInstance: echarts.ECharts | null = null;
// 节点索引（ECharts 以 name 为键；name 在项目内经 name_norm 唯一约束保证不撞）
const nodeByName = new Map<string, KbGraphNode>();
const nodeById = new Map<number, KbGraphNode>();
// ===== 详情面板 =====
const detail = ref<KbEntityDetail | null>(null);
const detailLoading = ref(false);
const panelMode = ref<'view' | 'edit' | 'merge'>('view');
const savingNode = ref(false);
const editForm = reactive({ name: '', entity_type: 'term', description: '' });
const mergeTargetId = ref<number | null>(null);
const mergeOptions = ref<KbGraphNode[]>([]);
const mergeSearching = ref(false);
const merging = ref(false);
const closeDetail = () => {
    detail.value = null;
    panelMode.value = 'view';
};
const openDetail = async (entityId: number) => {
    detailLoading.value = true;
    panelMode.value = 'view';
    try {
        const res = await knowledgeGraphApi.entityDetail(projectId.value, entityId);
        detail.value = res.data;
    }
    catch (err) {
        console.error('加载实体详情失败', err);
    }
    finally {
        detailLoading.value = false;
    }
};
// ===== 标签 =====
const handleSearchLabels = async (q: string) => {
    if (!q)
        return;
    try {
        const res = await knowledgeGraphApi.searchLabels(projectId.value, q);
        labelOptions.value = res.data?.labels || [];
    }
    catch {
        /* ignore */
    }
};
const loadPopularLabels = async () => {
    try {
        const res = await knowledgeGraphApi.popularLabels(projectId.value, 80);
        popularLabels.value = res.data?.labels || [];
    }
    catch {
        /* ignore */
    }
};
const goDocuments = () => {
    router.push(`/project-workspace/${projectId.value}/knowledge/documents`);
};
// ===== 图谱查询 =====
const handleExploreNode = async (label: string, silent = false) => {
    if (!label)
        return;
    currentLabel.value = label;
    exploring.value = true;
    try {
        const res = await knowledgeGraphApi.getGraph(projectId.value, {
            label,
            max_depth: graphParams.max_depth,
            max_nodes: graphParams.max_nodes,
        });
        graphData.value = res.data;
        if (!res.data.nodes.length && !silent) {
            ElMessage.info('未找到匹配的实体子图');
        }
        await nextTick();
        renderCurrentGraph();
    }
    catch (e) {
        console.error('查询图谱失败', e);
    }
    finally {
        exploring.value = false;
    }
};
/** 进页自动加载全量图谱（label='*' 后端整图直出；库为空时静默落空态） */
const loadFullGraph = () => handleExploreNode('*', true);
// ===== echarts 数据转换 =====
interface EchartsNode {
    name: string;
    entityId: number;
    symbolSize?: number;
    itemStyle?: object;
    label?: object;
    category?: number;
    // 力导向初始坐标（类型扇区播种，circular/tree 布局忽略）
    x?: number;
    y?: number;
}
interface EchartsLink {
    source: string;
    target: string;
    value?: number;
    keywords?: string;
    lineStyle?: object;
}
const buildEchartsData = () => {
    const data = graphData.value;
    if (!data) {
        return {
            nodes: [] as EchartsNode[],
            links: [] as EchartsLink[],
            categories: [] as {
                name: string;
                itemStyle?: object;
            }[],
        };
    }
    nodeByName.clear();
    nodeById.clear();
    data.nodes.forEach((n) => {
        nodeByName.set(n.name, n);
        nodeById.set(n.id, n);
    });
    nodeCount.value = data.nodes.length;
    edgeCount.value = data.edges.length;
    const textColor = cssVar('--text-primary', '#333');
    // 节点按（类型 → ref_count 降序）排序：环形图同类相邻成弧段（跨类边一眼可辨），
    // 类目/图例顺序稳定；力导向按此序做扇区播种
    const sortedRaw = [...data.nodes].sort((a, b) => a.entity_type === b.entity_type
        ? b.ref_count - a.ref_count
        : a.entity_type.localeCompare(b.entity_type));
    const presentTypes = [...new Set(sortedRaw.map((n) => n.entity_type))];
    const catIndex = new Map(presentTypes.map((t, i) => [t, i]));
    const categories = presentTypes.map((t) => ({
        name: entityTypeLabel(t),
        itemStyle: { color: typeColor(t) },
    }));
    // 常显标签动态阈值：节点多时只标注最重要的 ~60 个，其余 hover 查看（防满屏文字）
    const refsDesc = sortedRaw.map((n) => n.ref_count).sort((a, b) => b - a);
    const labelFloor = Math.max(2, refsDesc[Math.min(59, refsDesc.length - 1)] ?? 0);
    // 类型扇区播种：每个类型占一段圆弧，节点从各自扇区出发做力导向 →
    // 同类自然聚簇（颜色成片），比随机初始位置更符合「按类型读图」的方式
    const sectorSpan = (Math.PI * 2) / Math.max(1, presentTypes.length);
    const typeCursor = new Map<string, number>();
    const nodes: EchartsNode[] = sortedRaw.map((n) => {
        const isCenter = n.name === currentLabel.value;
        const size = isCenter ? 42 : Math.min(38, Math.max(14, 12 + n.ref_count * 3));
        const k = typeCursor.get(n.entity_type) ?? 0;
        typeCursor.set(n.entity_type, k + 1);
        const angle = (catIndex.get(n.entity_type) ?? 0) * sectorSpan +
            sectorSpan * (0.15 + 0.7 * (((k * 7) % 13) / 13));
        const radius = 160 + ((k * 37) % 240);
        return {
            name: n.name,
            entityId: n.id,
            symbolSize: size,
            category: catIndex.get(n.entity_type),
            x: Math.cos(angle) * radius,
            y: Math.sin(angle) * radius,
            itemStyle: { color: typeColor(n.entity_type) },
            label: {
                show: isCenter || n.ref_count >= labelFloor,
                fontSize: isCenter ? 13 : 11,
                color: textColor,
            },
        };
    });
    const links: EchartsLink[] = data.edges
        .filter((e) => nodeById.has(e.source) && nodeById.has(e.target))
        .map((e) => ({
        source: nodeById.get(e.source)!.name,
        target: nodeById.get(e.target)!.name,
        value: e.weight,
        keywords: e.keywords,
        lineStyle: { width: Math.min(4, 0.8 + e.weight * 0.6) },
    }));
    return { nodes, links, categories };
};
// ===== 渲染 =====
const getOrCreateChart = () => {
    if (!chartRef.value)
        return null;
    // 空态 ↔ 图表的 v-if 切换会换掉容器 DOM，旧实例绑着已卸载的节点必须重建
    if (chartInstance && chartInstance.getDom() !== chartRef.value) {
        chartInstance.dispose();
        chartInstance = null;
    }
    if (!chartInstance) {
        chartInstance = echarts.init(chartRef.value);
        chartInstance.on('click', (params: {
            dataType?: string;
            data?: {
                entityId?: number;
            };
        }) => {
            if (params.dataType === 'node' && params.data?.entityId) {
                openDetail(params.data.entityId);
            }
        });
        chartInstance.getZr().on('click', (params: {
            target?: unknown;
        }) => {
            if (params.target === undefined) {
                closeDetail();
            }
        });
    }
    return chartInstance;
};
const renderCurrentGraph = async () => {
    await nextTick();
    const chart = getOrCreateChart();
    if (!chart)
        return;
    const { nodes, links, categories } = buildEchartsData();
    if (nodes.length === 0) {
        chart.clear();
        return;
    }
    const textColor = cssVar('--text-primary', '#333');
    const secondaryColor = cssVar('--text-secondary', '#6b7280');
    const edgeColor = cssVar('--border-base', '#d0d5dd');
    type GraphSeries = {
        type: 'graph';
        data: EchartsNode[];
        links: EchartsLink[];
        categories: {
            name: string;
        }[];
        layout?: string;
        force?: object;
        circular?: object;
        roam: boolean;
        draggable: boolean;
        label: object;
        lineStyle: object;
        emphasis: object;
        itemStyle: object;
    };
    const baseSeries: GraphSeries = {
        type: 'graph',
        data: nodes,
        links,
        categories,
        roam: true,
        draggable: true,
        label: { position: 'bottom' },
        lineStyle: { color: edgeColor, width: 1, curveness: 0.1 },
        emphasis: {
            focus: 'adjacency',
            lineStyle: { width: 3 },
            label: { fontSize: 14, fontWeight: 'bold' },
        },
        itemStyle: { borderColor: cssVar('--bg-card', '#fff'), borderWidth: 1 },
    };
    if (viewMode.value === 'tree') {
        // 全量模式没有选中中心：以全图最大枢纽（ref_count 最高）为根展开
        const hubName = [...nodeByName.values()].sort((a, b) => b.ref_count - a.ref_count)[0]?.name;
        const rootName = nodeByName.has(currentLabel.value)
            ? currentLabel.value
            : hubName || nodes[0]?.name;
        const treeData = buildTreeData(links, rootName);
        chart.setOption({
            tooltip: { trigger: 'item' },
            series: [
                {
                    type: 'tree',
                    data: treeData,
                    roam: true,
                    symbol: 'circle',
                    symbolSize: 14,
                    initialTreeDepth: graphParams.max_depth,
                    label: {
                        position: 'bottom',
                        verticalAlign: 'middle',
                        fontSize: 11,
                        color: textColor,
                    },
                    leaves: { label: { position: 'bottom' } },
                    lineStyle: { color: edgeColor, width: 1.5, curveness: 0.5 },
                    emphasis: { focus: 'descendant' },
                    itemStyle: {
                        color: cssVar('--brand-500', '#6366f1'),
                        borderColor: cssVar('--bg-card', '#fff'),
                        borderWidth: 1.5,
                    },
                },
            ],
        }, true);
        return;
    }
    if (viewMode.value === 'force') {
        baseSeries.layout = 'force';
        // 参数随规模自适应：全量图（数百节点）斥力收小、向心力加大防散场；
        // 大图关掉布局动画（一次性排完），力导向迭代动画在 300+ 节点上很烧 CPU
        const n = nodes.length;
        baseSeries.force = {
            repulsion: n > 250 ? 120 : n > 120 ? 200 : 300,
            edgeLength: n > 250 ? [40, 120] : [80, 200],
            gravity: n > 250 ? 0.12 : 0.05,
            friction: 0.6,
            layoutAnimation: n <= 250,
        };
    }
    else if (viewMode.value === 'circular') {
        baseSeries.layout = 'circular';
        baseSeries.circular = { rotateLabel: true };
    }
    chart.setOption({
        tooltip: {
            trigger: 'item',
            formatter: (params: {
                dataType?: string;
                name?: string;
                data?: {
                    source?: string;
                    target?: string;
                    keywords?: string;
                };
            }) => {
                if (params.dataType === 'node') {
                    const n = nodeByName.get(params.name || '');
                    if (!n)
                        return params.name || '';
                    return (`<b>${n.name}</b><br/>` +
                        `类型：${entityTypeLabel(n.entity_type)}<br/>` +
                        `引用：${n.ref_count} 次 · ${n.doc_count} 份文档`);
                }
                if (params.dataType === 'edge') {
                    const kw = params.data?.keywords;
                    return (`${params.data?.source} → ${params.data?.target}` +
                        (kw ? `<br/>${kw}` : ''));
                }
                return params.name || '';
            },
        },
        legend: {
            data: categories.map((c) => c.name),
            bottom: 10,
            textStyle: { fontSize: 12, color: secondaryColor },
        },
        animationDuration: 800,
        animationEasingUpdate: 'quinticInOut',
        series: [baseSeries],
    }, true);
};
interface TreeNode {
    name: string;
    children?: TreeNode[];
    itemStyle?: object;
    label?: object;
}
const buildTreeData = (links: EchartsLink[], rootName: string): TreeNode[] => {
    if (!rootName)
        return [];
    const childrenMap = new Map<string, string[]>();
    links.forEach((l) => {
        if (!childrenMap.has(l.source))
            childrenMap.set(l.source, []);
        childrenMap.get(l.source)!.push(l.target);
        if (!childrenMap.has(l.target))
            childrenMap.set(l.target, []);
        childrenMap.get(l.target)!.push(l.source);
    });
    const visited = new Set<string>();
    const centerColor = cssVar('--brand-600', '#7c3aed');
    const nodeColor = cssVar('--brand-500', '#6366f1');
    const buildNode = (name: string): TreeNode => {
        visited.add(name);
        const children = childrenMap.get(name) || [];
        const childNodes: TreeNode[] = [];
        children.forEach((child) => {
            if (!visited.has(child)) {
                childNodes.push(buildNode(child));
            }
        });
        return {
            name,
            children: childNodes.length > 0 ? childNodes : undefined,
            itemStyle: { color: name === rootName ? centerColor : nodeColor },
            label: { fontSize: name === rootName ? 13 : 11 },
        };
    };
    return [buildNode(rootName)];
};
// ===== 详情面板操作 =====
const handleClickRelatedNode = (rel: KbEntityRelationItem) => {
    if (!detail.value)
        return;
    const peerId = rel.source === detail.value.id ? rel.target : rel.source;
    openDetail(peerId);
    const peer = nodeById.get(peerId);
    if (peer && chartInstance) {
        chartInstance.dispatchAction({ type: 'highlight', name: peer.name });
    }
};
const startEditNode = () => {
    if (!detail.value)
        return;
    editForm.name = detail.value.name;
    editForm.entity_type = detail.value.entity_type;
    editForm.description = detail.value.description || '';
    panelMode.value = 'edit';
};
const handleSaveNode = async () => {
    if (!detail.value)
        return;
    savingNode.value = true;
    try {
        await knowledgeGraphApi.updateEntity(projectId.value, detail.value.id, {
            name: editForm.name.trim(),
            entity_type: editForm.entity_type,
            description: editForm.description,
        });
        ElMessage.success('保存成功');
        panelMode.value = 'view';
        await openDetail(detail.value.id);
        if (currentLabel.value)
            await handleExploreNode(currentLabel.value);
    }
    catch (e) {
        console.error('保存实体失败', e);
    }
    finally {
        savingNode.value = false;
    }
};
const handleDeleteEntity = async () => {
    if (!detail.value)
        return;
    try {
        await ElMessageBox.confirm(`确定要删除实体「${detail.value.name}」吗？将同时删除其全部关联关系（软删墓碑，自动抽取不会复活）。`, '删除确认', { type: 'warning' });
    }
    catch {
        return;
    }
    try {
        await knowledgeGraphApi.deleteEntity(projectId.value, detail.value.id);
        ElMessage.success('删除成功');
        closeDetail();
        if (currentLabel.value)
            await handleExploreNode(currentLabel.value);
        loadPopularLabels();
    }
    catch (e) {
        console.error('删除实体失败', e);
    }
};
const startMerge = () => {
    mergeTargetId.value = null;
    mergeOptions.value = [];
    panelMode.value = 'merge';
};
const handleSearchMergeTarget = async (q: string) => {
    if (!q)
        return;
    mergeSearching.value = true;
    try {
        const res = await knowledgeGraphApi.searchEntities(projectId.value, q);
        mergeOptions.value = res.data || [];
    }
    catch {
        /* ignore */
    }
    finally {
        mergeSearching.value = false;
    }
};
const handleMerge = async () => {
    if (!detail.value || !mergeTargetId.value)
        return;
    merging.value = true;
    try {
        const res = await knowledgeGraphApi.mergeEntities(projectId.value, {
            source_id: detail.value.id,
            target_id: mergeTargetId.value,
        });
        ElMessage.success('合并完成');
        panelMode.value = 'view';
        await openDetail(res.data.id);
        if (currentLabel.value)
            await handleExploreNode(currentLabel.value);
        loadPopularLabels();
    }
    catch (e) {
        console.error('合并实体失败', e);
    }
    finally {
        merging.value = false;
    }
};
// ===== 生命周期 =====
const handleResize = () => {
    chartInstance?.resize();
};
onMounted(() => {
    loadPopularLabels();
    loadFullGraph();
    window.addEventListener('resize', handleResize);
});
onUnmounted(() => {
    window.removeEventListener('resize', handleResize);
    if (chartInstance) {
        chartInstance.dispose();
        chartInstance = null;
    }
});
</script>

<style scoped>
.graph-page {
  display: flex;
  height: 100%;
  padding: 0;
}

/* 左侧 */
.side-panel {
  width: 260px;
  flex-shrink: 0;
  border-right: 1px solid var(--el-border-color-lighter);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  background: var(--el-bg-color);
}

.search-section {
  padding: 14px;
  border-bottom: 1px solid var(--el-border-color-light);
}

.full-select {
  width: 100%;
}

.params-section {
  padding: 14px;
  border-bottom: 1px solid var(--el-border-color-light);
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 10px;
}

.param-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.param-name {
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.labels-section {
  padding: 14px;
  border-bottom: 1px solid var(--el-border-color-light);
  flex: 1;
  overflow-y: auto;
}

.label-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 4px;
}

.label-chip {
  padding: 3px 10px;
  border: 1px solid var(--el-border-color);
  border-radius: 12px;
  font-size: 12px;
  color: var(--el-text-color-regular);
  cursor: pointer;
  transition: all 0.2s;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.label-chip:hover {
  border-color: var(--el-color-primary);
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.label-chip.active {
  border-color: var(--el-color-primary);
  color: var(--theme-white);
  background: var(--el-color-primary);
}

.label-empty {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  text-align: center;
  padding: 10px;
}

.info-section {
  padding: 14px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  padding: 3px 0;
  color: var(--el-text-color-secondary);
}

.info-val {
  color: var(--el-text-color-primary);
  font-weight: 500;
}

/* 右侧主区 */
.graph-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  position: relative;
}

.graph-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 14px;
  border-bottom: 1px solid var(--el-border-color-light);
  background: var(--el-fill-color-blank);
}

.chart-container {
  flex: 1;
  position: relative;
  overflow: hidden;
}

.chart-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 10px;
  color: var(--el-text-color-placeholder);
}

.chart-empty h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-secondary);
  margin: 0;
}

.chart-empty p {
  font-size: 13px;
  margin: 0;
}

.chart-box {
  width: 100%;
  height: 100%;
}

/* 玻璃拟态详情面板 */
.detail-panel {
  position: absolute;
  top: 0;
  right: 0;
  width: 320px;
  height: 100%;
  background: rgba(var(--theme-rgb-white), 0.85);
  backdrop-filter: blur(16px) saturate(180%);
  -webkit-backdrop-filter: blur(16px) saturate(180%);
  border-left: 1px solid var(--el-border-color);
  box-shadow: -4px 0 24px rgba(var(--theme-rgb-black), 0.08);
  display: flex;
  flex-direction: column;
  z-index: 10;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 18px;
  border-bottom: 1px solid var(--el-border-color-light);
}

.detail-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.close-btn {
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 6px;
  background: var(--theme-transparent);
  color: var(--el-text-color-placeholder);
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  flex-shrink: 0;
  margin-left: 8px;
}

.close-btn:hover {
  background: var(--el-fill-color-light);
  color: var(--el-text-color-primary);
}

.detail-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.detail-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.field-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--el-text-color-placeholder);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.field-value {
  font-size: 13px;
  color: var(--el-text-color-primary);
  line-height: 1.6;
  word-break: break-all;
}

.field-value.field-empty {
  color: var(--el-text-color-placeholder);
}

.detail-actions {
  display: flex;
  gap: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--el-border-color-light);
}

.edit-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 4px;
}

/* 关联节点 */
.related-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.related-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 280px;
  overflow-y: auto;
  padding-right: 2px;
}

.related-list::-webkit-scrollbar {
  width: 4px;
}

.related-list::-webkit-scrollbar-thumb {
  background: var(--el-border-color);
  border-radius: 4px;
}

.related-node-item {
  padding: 8px 10px;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  background: var(--theme-color-fafbff);
}

.related-node-item:hover {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  box-shadow: 0 2px 8px rgba(var(--theme-rgb-primary), 0.08);
}

.related-node-main {
  display: flex;
  align-items: center;
  gap: 6px;
}

.related-node-direction {
  font-size: 14px;
  font-weight: 700;
  flex-shrink: 0;
  width: 18px;
  text-align: center;
}

.related-node-direction.out {
  color: var(--el-color-primary);
}

.related-node-direction.in {
  color: var(--theme-color-6366f1);
}

.related-node-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.related-node-relation {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
  padding-left: 24px;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.related-node-type {
  font-size: 10px;
  color: var(--el-color-primary);
  margin-top: 2px;
  padding-left: 24px;
}

/* ====== P1b 自研图谱新增 ====== */
.truncated-tag {
  font-size: 12px;
  color: var(--el-color-warning);
  background: var(--el-color-warning-light-9);
  border: 1px solid var(--el-color-warning-light-5);
  border-radius: 10px;
  padding: 2px 10px;
}

.truncated-val {
  color: var(--el-color-warning);
}

.edited-badge {
  display: inline-block;
  margin-left: 6px;
  padding: 0 6px;
  font-size: 10px;
  line-height: 16px;
  border-radius: 8px;
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  vertical-align: middle;
}

.type-pill {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: baseline;
}

.mention-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 200px;
  overflow-y: auto;
}

.mention-list::-webkit-scrollbar {
  width: 4px;
}

.mention-list::-webkit-scrollbar-thumb {
  background: var(--el-border-color);
  border-radius: 4px;
}

.mention-item {
  padding: 6px 10px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--theme-color-fafbff);
}

.mention-doc {
  font-size: 12px;
  font-weight: 500;
  color: var(--el-text-color-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mention-crumb {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.merge-hint {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
  margin-top: 6px;
}
</style>
