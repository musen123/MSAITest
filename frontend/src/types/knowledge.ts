/**
 * 项目知识库类型定义（自研版）
 *
 * 对应后端：backend/app/schemas/knowledge/*
 * LightRAG 遗留类型已随 P1b 图谱切换全部移除。
 */
// ─────────────────────────────────────────────────────────────
// KB 元信息
// ─────────────────────────────────────────────────────────────
export interface KnowledgeBaseInfo {
    id: number;
    project_id: number;
    status: string;
    total_documents: number;
    total_chunks: number;
    total_nodes: number;
    total_edges: number;
    project_summary?: string | null;
    error_message?: string | null;
    last_built_at?: string | null;
    created_at: string;
    updated_at: string;
}
// ─────────────────────────────────────────────────────────────
// 文档
// ─────────────────────────────────────────────────────────────
/** 自研分阶段状态机（LightRAG 遗留值已随 P2 状态清理移除） */
export type KbDocumentStatus = 'pending' | 'parsing' | 'chunking' | 'embedding' | 'ready' | 'failed' | 'deleted';
/** 文档类型（契约冻结，检索过滤/分块 profile/图谱抽取共用） */
export type KbDocType = 'requirement' | 'api_doc' | 'design' | 'test_case' | 'bug_review' | 'meeting' | 'other';
/** 图谱抽取状态（与文档主 status 独立——失败隔离） */
export type KbGraphStatus = 'none' | 'pending' | 'extracting' | 'extracted' | 'failed' | 'skipped';
export interface KbDocument {
    id: number;
    project_id: number;
    file_name: string;
    file_size: number;
    file_ext: string;
    doc_type: KbDocType;
    source_type: 'upload' | 'text' | 'func_doc' | 'entity';
    source_id?: number | null;
    storage_key?: string | null;
    version: number;
    validity: 'effective' | 'deprecated';
    parse_mode?: 'raw' | 'llm_normalized' | null;
    truncated: boolean;
    chunk_count: number;
    ai_task_id?: number | null;
    graph_status: KbGraphStatus;
    graph_task_id?: number | null;
    entity_count: number;
    status: KbDocumentStatus;
    error_message?: string | null;
    uploaded_by: number;
    processed_at?: string | null;
    created_at: string;
    updated_at: string;
}
export interface KbDocumentListResponse {
    total: number;
    items: KbDocument[];
    /** 各状态文档数（本地 GROUP BY） */
    status_counts: Record<string, number>;
}
export interface KbUploadResult {
    document: KbDocument;
    ai_task_id: number;
}
export interface KbInsertTextPayload {
    title: string;
    content: string;
    doc_type?: KbDocType;
}
// 检索相关类型（KbSearchHit/KbSearchData/KbSearchPayload）随接口定义在
// api/knowledge.ts —— 自研 /search、/answer SSE、/feedback 三件套。
// ─────────────────────────────────────────────────────────────
// 图谱（自研四表契约：数字 id，节点带类型/引用计数）
// ─────────────────────────────────────────────────────────────
/** 受控实体类型词表（10 类封顶，与后端 KbEntityType 对齐） */
export type KbEntityType = 'system' | 'module' | 'page' | 'role' | 'business_rule' | 'data_object' | 'config' | 'term' | 'metric';
export interface KbGraphNode {
    id: number;
    name: string;
    entity_type: string;
    description?: string | null;
    ref_count: number;
    doc_count: number;
    human_edited: boolean;
}
export interface KbGraphEdge {
    id: number;
    source: number;
    target: number;
    keywords: string;
    description?: string | null;
    weight: number;
    ref_count: number;
    human_edited: boolean;
}
export interface KbSubgraphData {
    nodes: KbGraphNode[];
    edges: KbGraphEdge[];
    is_truncated: boolean;
}
export interface KbEntityMentionItem {
    document_id: number;
    doc_name: string;
    chunk_id?: number | null;
    heading_path: string;
}
export interface KbEntityRelationItem extends KbGraphEdge {
    source_name: string;
    target_name: string;
}
export interface KbEntityDetail extends KbGraphNode {
    created_by?: number | null;
    mentions: KbEntityMentionItem[];
    relations: KbEntityRelationItem[];
}
export interface KbGraphStats {
    total_nodes: number;
    total_edges: number;
    doc_graph_status: Record<string, number>;
}
export interface KbExtractBatchResult {
    dispatched: number;
    remaining: number;
    task_ids: number[];
}
