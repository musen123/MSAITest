/**
 * 测试数据中心 API（AI 造数：文件资产 + 数据集）
 */

import { request } from '../request'

export type PageData<T> = {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

// ==================== 文件资产 ====================

export interface TestFileAsset {
  id: number
  project_id: number
  name: string
  file_name: string
  storage_key: string
  mime: string | null
  size_bytes: number | null
  source: string // manual | ai
  spec: string | null
  ai_task_id: number | null
  created_at: string | null
  updated_at: string | null
  url: string | null
}

export interface TestFileAssetUpdate {
  name?: string
  spec?: string
}

// ==================== 数据集 ====================

export interface TestDatasetColumn {
  name: string
  desc?: string | null
  kind: string // identity | secret | synthetic
}

export interface TestDataset {
  id: number
  project_id: number
  name: string
  description: string | null
  columns: TestDatasetColumn[] | null
  rows?: Record<string, string>[] | null
  row_count: number
  source: string // manual | csv | ai
  ai_task_id: number | null
  created_at: string | null
  updated_at: string | null
}

export interface TestDatasetCreate {
  name: string
  description?: string
  columns?: TestDatasetColumn[]
  rows?: Record<string, string>[]
  source?: string
}

export interface TestDatasetUpdate {
  name?: string
  description?: string
  columns?: TestDatasetColumn[]
  rows?: Record<string, string>[]
}

// ==================== API ====================

class TestDataApi {
  // ---------- 文件资产 ----------
  listFiles(
    projectId: number,
    params?: { keyword?: string; source?: string; page?: number; page_size?: number }
  ) {
    return request.get<PageData<TestFileAsset>>(`/projects/${projectId}/test-files`, { params })
  }

  getFile(projectId: number, assetId: number) {
    return request.get<TestFileAsset>(`/projects/${projectId}/test-files/${assetId}`)
  }

  uploadFile(projectId: number, form: FormData) {
    return request.post<TestFileAsset>(`/projects/${projectId}/test-files`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  }

  updateFile(projectId: number, assetId: number, data: TestFileAssetUpdate) {
    return request.put<TestFileAsset>(`/projects/${projectId}/test-files/${assetId}`, data)
  }

  deleteFile(projectId: number, assetId: number) {
    return request.delete<{ message: string }>(`/projects/${projectId}/test-files/${assetId}`)
  }

  // ---------- 数据集 ----------
  listDatasets(
    projectId: number,
    params?: { keyword?: string; page?: number; page_size?: number }
  ) {
    return request.get<PageData<TestDataset>>(`/projects/${projectId}/test-datasets`, { params })
  }

  getDataset(projectId: number, datasetId: number) {
    return request.get<TestDataset>(`/projects/${projectId}/test-datasets/${datasetId}`)
  }

  createDataset(projectId: number, data: TestDatasetCreate) {
    return request.post<TestDataset>(`/projects/${projectId}/test-datasets`, data)
  }

  updateDataset(projectId: number, datasetId: number, data: TestDatasetUpdate) {
    return request.put<TestDataset>(`/projects/${projectId}/test-datasets/${datasetId}`, data)
  }

  deleteDataset(projectId: number, datasetId: number) {
    return request.delete<{ message: string }>(`/projects/${projectId}/test-datasets/${datasetId}`)
  }
}

export const testDataApi = new TestDataApi()
