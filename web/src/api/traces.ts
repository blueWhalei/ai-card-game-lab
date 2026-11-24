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
  response_time_ms?: unknown
  parser_ok?: unknown
}

export interface AggregatedMetrics {
  total_traces: number
  response_time_count: number
  avg_response_time_ms: number | null
  min_response_time_ms: number | null
  max_response_time_ms: number | null
  parser_success_count: number
  parser_evaluated_count: number
}

export interface TraceFilters {
  game_id?: string
  experiment_id?: string
  player_id?: string
  model?: string
  parser_ok?: boolean
  start_time?: string
  end_time?: string
}

export const tracesApi = {
  list: (params?: TraceFilters & { page?: number; page_size?: number }) =>
    apiClient.get<never, ApiResponse<PaginatedData<Trace>>>('/api/v1/traces', { params }),

  get: (traceId: string, params?: TraceFilters) =>
    apiClient.get<never, ApiResponse<Trace>>(`/api/v1/traces/${encodeURIComponent(traceId)}`, {
      params,
    }),

  metrics: (params?: TraceFilters) =>
    apiClient.get<never, ApiResponse<AggregatedMetrics>>('/api/v1/traces/metrics', { params }),
}
