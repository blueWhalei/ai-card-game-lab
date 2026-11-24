import { apiClient } from './client'
import type { ApiResponse } from './types'
import type { Experiment } from './experimentApi'

export interface Study {
  id: string
  title: string
  question: string
  created_at: string
  updated_at: string
}
export interface StudySummary extends Study {
  run_count: number
  last_activity_at: string
}
export interface StudyDetail extends Study {
  runs: Experiment[]
  comparisons: { id: string; title: string; created_at: string; revision_count: number }[]
}
export type OperationFilter = 'all' | 'active' | 'attention'
export interface RecordedTokenUsage {
  value: number | null
  recorded_count: number
  missing_count: number
  invalid_count: number
  overflow: boolean
}
export interface StudyOperations {
  study_id: string
  state: OperationFilter
  page: number
  page_size: number
  total: number
  read_at: string
  items: {
    id: string
    name: string
    target_games: number
    game_count: number
    states: Record<
      | 'waiting'
      | 'running'
      | 'paused'
      | 'finished'
      | 'failed'
      | 'interrupted'
      | 'cancelled'
      | 'unknown',
      number
    >
    no_bid_count: number
    trace_count: number
    usage: Record<'prompt_tokens' | 'completion_tokens' | 'total_tokens', RecordedTokenUsage>
  }[]
}
export const studyApi = {
  operations: (id: string, state: OperationFilter, page: number) =>
    apiClient.get<never, ApiResponse<StudyOperations>>(
      `/api/v1/studies/${encodeURIComponent(id)}/operations`,
      { params: { state, page } },
    ),
  list: (offset = 0) =>
    apiClient.get<never, ApiResponse<StudySummary[]>>('/api/v1/studies', {
      params: { limit: 50, offset },
    }),
  create: (title: string, question: string) =>
    apiClient.post<never, ApiResponse<Study>>('/api/v1/studies', { title, question }),
  get: (id: string) =>
    apiClient.get<never, ApiResponse<StudyDetail>>(`/api/v1/studies/${encodeURIComponent(id)}`),
  attach: (id: string, experimentId: string) =>
    apiClient.post<never, ApiResponse<{ attached: boolean }>>(
      `/api/v1/studies/${encodeURIComponent(id)}/runs`,
      { experiment_id: experimentId },
    ),
}
