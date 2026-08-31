import { apiClient } from './client'
import type { ApiResponse, PaginatedData } from './types'

export interface Trace {
  id: string
  game_id: string
  round_number: number
  player_id: string
  model: string
  prompt_version: string
  input_snapshot: Record<string, unknown>
  output_data: Record<string, unknown>
  metrics: TraceMetrics
  created_at: string
  spans?: Span[]
}

export interface Span {
  id: string
  trace_id: string
  span_type: string
  start_time: string
  end_time: string | null
  status: string
  data: Record<string, unknown>
}

export interface TraceMetrics {
  response_time_ms: number
  used_langchain_parser: boolean
}

export interface AggregatedMetrics {
  total_traces: number
  avg_response_time_ms: number
  min_response_time_ms: number
  max_response_time_ms: number
  langchain_success_count: number | null
}

export interface VersionStats {
  version: string
  total_traces: number
  avg_response_time_ms: number
  langchain_success_count: number
  success_rate: number
}

export interface CompareResult {
  version1: VersionStats
  version2: VersionStats
  response_time_diff: number
  success_rate_diff: number
}

export const tracesApi = {
  list: (params?: {
    game_id?: string
    experiment_id?: string
    player_id?: string
    model?: string
    parser_ok?: boolean
    page?: number
    page_size?: number
  }) =>
    apiClient.get<never, ApiResponse<PaginatedData<Trace>>>('/api/v1/traces', { params }),

  get: (traceId: string) =>
    apiClient.get<never, ApiResponse<Trace>>(`/api/v1/traces/${traceId}`),

  metrics: (params?: {
    game_id?: string
    experiment_id?: string
    player_id?: string
    model?: string
    parser_ok?: boolean
    start_time?: string
    end_time?: string
  }) =>
    apiClient.get<never, ApiResponse<AggregatedMetrics>>('/api/v1/traces/metrics', { params }),

  compare: (version1: string, version2: string) =>
    apiClient.get<never, ApiResponse<CompareResult>>('/api/v1/traces/compare', {
      params: { version1, version2 },
    }),
}
