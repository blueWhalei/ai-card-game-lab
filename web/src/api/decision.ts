import { apiClient } from './client'

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
  legal_actions: Array<{
    action_type: string
    cards: string[]
  }>
  chosen_action: {
    action_type: string
    cards: string[]
  }
  thinking: string | null
  outcome: string | null
  quality_score: number
  created_at: string
}

export interface DecisionStats {
  total: number
  avg_quality: number
  min_quality: number
  max_quality: number
  outcome_counts: Record<string, number>
  phase_counts: Record<string, number>
}

export interface ExportResult {
  filepath: string
  count: number
}

export const decisionApi = {
  list: (params?: {
    game_id?: string
    player_id?: string
    min_quality?: number
    max_quality?: number
    game_phase?: string
    outcome?: string
    limit?: number
    offset?: number
  }) =>
    apiClient.get<{ data: DecisionPoint[]; message: string }>('/api/v1/decision-points', {
      params,
    }),

  get: (id: string) =>
    apiClient.get<{ data: DecisionPoint }>(`/api/v1/decision-points/${id}`),

  stats: () =>
    apiClient.get<{ data: DecisionStats }>('/api/v1/decision-points/stats'),

  export: (params?: {
    game_id?: string
    min_quality?: number
    outcome?: string
  }) =>
    apiClient.post<{ data: ExportResult; message: string }>('/api/v1/decision-points/export', params),
}
