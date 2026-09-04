import { apiClient } from './client'
import type { ApiResponse, PaginatedData } from './types'

export interface DecisionPoint {
  id: string
  game_id: string
  round_number: number
  player_id: string
  hand_cards: string[]
  opponent_hands: Record<string, number> | null
  last_action: {
    player: string
    action_type: string
    cards: string[]
  } | null
  game_phase: string
  legal_actions?: Array<{
    action_type: string
    cards?: string[]
  }>
  chosen_action: {
    action_type: string
    cards: string[]
  }
  thinking: string | null
  outcome: string | null
  quality_score: number
  train_usable: boolean
  train_usable_reason?: string
  parser_ok?: boolean | null
  win_probability?: {
    probability: number
    confidence: string
    reasoning?: string
    factors?: string[]
  } | null
  hand_analysis?: {
    bomb_count: number
    rocket: boolean
    strength_score: number
  } | null
  created_at: string
}

export interface DecisionStats {
  total: number
  avg_quality: number
  min_quality: number
  max_quality: number
  outcome_counts: Record<string, number>
  phase_counts: Record<string, number>
  train_usable_count?: number
  not_usable_count?: number
  usable_rate?: number
  not_usable_reason_counts?: Record<string, number>
}

export interface ExportResult {
  filepath: string
  count: number
}

export interface DecisionExportParams {
  game_id?: string
  experiment_id?: string
  player_id?: string
  min_quality?: number
  outcome?: string
  game_phase?: string
  train_usable?: boolean
  train_usable_only?: boolean
  include_thinking?: boolean
}

export const decisionApi = {
  list: (params?: {
    game_id?: string
    experiment_id?: string
    player_id?: string
    min_quality?: number
    max_quality?: number
    game_phase?: string
    outcome?: string
    train_usable?: boolean
    page?: number
    page_size?: number
  }) =>
    apiClient.get<never, ApiResponse<PaginatedData<DecisionPoint>>>('/api/v1/decision-points', {
      params,
    }),

  get: (id: string) =>
    apiClient.get<never, ApiResponse<DecisionPoint>>(`/api/v1/decision-points/${id}`),

  stats: (params?: { experiment_id?: string }) =>
    apiClient.get<never, ApiResponse<DecisionStats>>('/api/v1/decision-points/stats', {
      params,
    }),

  export: (params?: DecisionExportParams) =>
    apiClient.post<never, ApiResponse<ExportResult>>('/api/v1/decision-points/export', params),
}
