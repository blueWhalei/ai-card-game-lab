import { apiClient } from './client'
import type { ApiResponse } from './types'
import type { GameItem } from './gameApi'
import { tt } from '@/i18n'

export type ExperimentStatus =
  | 'pending_collect'
  | 'collecting'
  | 'ready_review'
  | 'ready_more'

export interface ExperimentPlayerStat {
  player_id: string
  wins: number
  win_rate: number
  train_usable_decisions: number
  avg_response_time_ms: number
  trace_count: number
}

export interface ExperimentSummary {
  status: ExperimentStatus
  target_games: number
  total_games: number
  active_games: number
  finished_games: number
  games_with_winner: number
  train_usable_decisions: number
  avg_rounds: number
  wins_by_config: Record<string, number>
  player_stats: ExperimentPlayerStat[]
  latest_game_id: string | null
}

export interface Experiment {
  id: string
  name: string
  notes: string
  game_type: string
  player_ids: string[]
  target_games: number
  created_at: string
  updated_at: string
  summary: ExperimentSummary
  games?: GameItem[]
}

export interface CreateExperimentRequest {
  name: string
  notes?: string
  game_type?: string
  player_ids: string[]
  target_games: number
}

export interface CollectExperimentRequest {
  count: number
}

export interface CollectExperimentResult {
  game_ids: string[]
  count: number
}

export interface ExperimentComparePlayerStat {
  player_id: string
  wins: number
  win_rate: number
  win_rate_ci: [number, number]
  train_usable_decisions: number
  avg_response_time_ms: number
  trace_count: number
}

export interface ExperimentCompareRow {
  id: string
  name: string
  notes: string
  game_type: string
  player_ids: string[]
  finished_games: number
  games_with_winner: number
  avg_rounds: number
  avg_response_time_ms: number
  total_tokens: number
  avg_tokens_per_round: number
  train_usable_rate: number
  train_usable_n: number
  decision_count: number
  parser_success_rate: number
  parser_n: number
  player_stats: ExperimentComparePlayerStat[]
}

export interface ExperimentCompareResult {
  experiments: ExperimentCompareRow[]
}

export const experimentApi = {
  list: () => apiClient.get<never, ApiResponse<Experiment[]>>('/api/v1/experiments'),

  get: (id: string) =>
    apiClient.get<never, ApiResponse<Experiment>>(`/api/v1/experiments/${id}`),

  create: (data: CreateExperimentRequest) =>
    apiClient.post<never, ApiResponse<Experiment>>('/api/v1/experiments', data),

  collect: (id: string, data: CollectExperimentRequest) =>
    apiClient.post<never, ApiResponse<CollectExperimentResult>>(
      `/api/v1/experiments/${id}/collect`,
      data,
    ),

  compare: (ids: string[]) =>
    apiClient.get<never, ApiResponse<ExperimentCompareResult>>(
      '/api/v1/experiments/compare',
      { params: { ids: ids.join(',') } },
    ),
}

export const EXPERIMENT_STATUS_VARIANT: Record<
  ExperimentStatus,
  'muted' | 'accent' | 'success' | 'warning'
> = {
  pending_collect: 'muted',
  collecting: 'accent',
  ready_review: 'success',
  ready_more: 'warning',
}

export function experimentStatusLabel(status: ExperimentStatus): string {
  return tt(`experiment.status.${status}`)
}
