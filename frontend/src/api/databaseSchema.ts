import service from './request'
import type { ApiResponse } from './request'

export interface SchemaColumn {
  name: string
  type: string
  nullable: boolean
  key: string
  comment: string
}
export interface SchemaTable {
  name: string
  comment: string
  columns: SchemaColumn[]
}
export interface DatabaseSchema {
  database: string
  tables: SchemaTable[]
}

export interface TableRowsData {
  columns: string[]
  rows: Record<string, any>[]
  has_more: boolean
}

export const databaseSchemaApi = {
  /** 表结构内省 */
  getSchema(projectId: number, connId: number, refresh = false) {
    return service.get<any, ApiResponse<DatabaseSchema>>(
      `/projects/${projectId}/databases/${connId}/schema`,
      { params: { refresh } },
    )
  },
  /** 分页查看表数据（只读，默认每页 20 条） */
  getTableRows(
    projectId: number,
    connId: number,
    table: string,
    params?: { limit?: number; offset?: number },
  ) {
    return service.get<any, ApiResponse<TableRowsData>>(
      `/projects/${projectId}/databases/${connId}/tables/${encodeURIComponent(table)}/rows`,
      { params },
    )
  },
}
