import { apiClient } from './client'
import type { ApiResponse } from './types'

export interface DataStats {
  total_games: number
  total_rounds: number
  games_by_type: Record<string, number>
  models_usage: Record<string, number>
  avg_response_time_ms: number
  // Token 用量
  total_tokens: number
  total_prompt_tokens: number
  total_completion_tokens: number
  tokens_by_model: Record<string, number>
  // 对局质量
  avg_game_rounds: number
  games_with_winner: number
  wins_by_role: Record<string, number>
  // AI 表现
  ai_win_rates: ModelWinRate[]
  // 响应时间
  p50_response_ms: number
  p95_response_ms: number
  response_time_by_model: Record<string, number>
}

export interface ModelWinRate {
  model: string
  games: number
  wins: number
  win_rate: number
}

/** How a dataset was carved out of the decision points, echoed back for display. */
export interface DatasetFilters {
  source?: string
  format?: string
  train_usable?: boolean | null
  train_usable_only?: boolean
  max_ev_loss?: number | null
  include_thinking?: boolean
  game_id?: string | null
  experiment_id?: string | null
  player_id?: string | null
  min_quality?: number | null
  outcome?: string | null
  game_phase?: string | null
  eval_ratio?: number
  eval_sample_count?: number
  eval_game_ids?: string[]
  eval_file_path?: string
}

export interface CreateDatasetFromDecisionsRequest {
  name: string
  game_type?: string
  game_id?: string | null
  experiment_id?: string | null
  player_id?: string | null
  min_quality?: number | null
  outcome?: string | null
  game_phase?: string | null
  train_usable?: boolean | null
  train_usable_only?: boolean
  include_thinking?: boolean
  eval_ratio?: number
}

export interface DatasetItem {
  id: string
  name: string
  game_type: string
  filters: DatasetFilters
  sample_count: number
  file_path: string
  created_at: string
}

export const dataApi = {
  stats: (params?: { experiment_id?: string }) =>
    apiClient.get<never, ApiResponse<DataStats>>('/api/v1/data/stats', { params }),

  listDatasets: () => apiClient.get<never, ApiResponse<DatasetItem[]>>('/api/v1/datasets'),

  createDatasetFromDecisions: (data: CreateDatasetFromDecisionsRequest) =>
    apiClient.post<never, ApiResponse<DatasetItem>>('/api/v1/datasets/from-decisions', data),

  deleteDataset: (id: string) => apiClient.delete(`/api/v1/datasets/${id}`),
}
