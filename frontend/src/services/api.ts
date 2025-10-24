import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'
const API_KEY = import.meta.env.VITE_API_KEY || 'patscore-8f3k9d2m5p7r'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Authorization': `Bearer ${API_KEY}`,
    'Content-Type': 'application/json',
  },
})

export interface RecordSummary {
  id: string
  patent_id: string
  title: string
  abstract?: string
  relevance?: string
  score?: number
  subsystem?: string[]
  sha1: string
  updated_at?: string
}

export interface ListRecordsResponse {
  total: number
  offset: number
  limit: number
  records: RecordSummary[]
}

export interface ScoreRequest {
  title: string
  abstract: string
  record_id?: string
  mapping?: Record<string, string[]>
  mode?: 'llm' | 'keyword'
}

export interface ScoreResponse {
  relevance: string
  score: number
  subsystem: string[]
  sha1: string
  provenance: {
    method: string
    prompt_version?: string
    scored_at?: string
  }
}

export const patentApi = {
  listRecords: async (params?: {
    limit?: number
    offset?: number
    q?: string
    relevance?: string
    subsystem?: string
  }): Promise<ListRecordsResponse> => {
    const response = await api.get<ListRecordsResponse>('/records', { params })
    return response.data
  },

  getRecord: async (id: string): Promise<RecordSummary> => {
    const response = await api.get<RecordSummary>(`/records/${id}`)
    return response.data
  },

  scoreRecord: async (request: ScoreRequest): Promise<ScoreResponse> => {
    const response = await api.post<ScoreResponse>('/score', request)
    return response.data
  },

  healthCheck: async (): Promise<{ ok: boolean; version: string }> => {
    const response = await api.get('/health')
    return response.data
  },
}

export default api
