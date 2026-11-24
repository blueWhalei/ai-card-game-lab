import { apiClient } from './client'
import type { ApiResponse } from './types'
import type { ExperimentPack } from './experimentApi'

export type PlayerPolicyKind = 'llm' | 'tool_loop' | 'search' | 'heuristic' | 'random' | 'first'

export interface ExperimentConfig {
  id: string
  name: string
  notes: string
  policy_kind: PlayerPolicyKind
  model_config: {
    provider: string
    model_name: string
    temperature: number
    top_p: number
    max_tokens: number
  }
}

export interface SeatModelCheck {
  player_id: string
  provider: string
  model: string
  setting: string
  status:
    | 'configured'
    | 'invalid_model'
    | 'unknown_provider'
    | 'invalid_url'
    | 'missing_key'
    | 'listed'
    | 'not_listed'
    | 'access_denied'
    | 'unreachable'
    | 'catalog_unavailable'
}

export interface ExperimentConfigStats {
  config_id: string
  decided_games: number
  wins: number
  losses: number
  win_rate: number | null
  last_game_id: string | null
  last_game_at: string | null
}

export interface CreateExperimentConfigRequest {
  id: string
  name: string
  notes?: string
  policy_kind?: PlayerPolicyKind
  model_config_data?: {
    provider: string
    model_name: string
    temperature: number
    top_p: number
    max_tokens: number
  } | null
}

export interface UpdateExperimentConfigRequest {
  name?: string
  notes?: string
  policy_kind?: PlayerPolicyKind
  model_config_data?: {
    provider: string
    model_name: string
    temperature: number
    top_p: number
    max_tokens: number
  } | null
}

export const experimentConfigApi = {
  readiness: (player_ids: string[], check_connection = false) =>
    apiClient.post<never, ApiResponse<{ checks: SeatModelCheck[]; config_file: string }>>(
      '/api/v1/experiment-configs/readiness',
      { player_ids, check_connection },
    ),

  list: () => apiClient.get<never, ApiResponse<ExperimentConfig[]>>('/api/v1/experiment-configs'),

  get: (id: string) =>
    apiClient.get<never, ApiResponse<ExperimentConfig>>(`/api/v1/experiment-configs/${id}`),

  create: (data: CreateExperimentConfigRequest) =>
    apiClient.post<never, ApiResponse<ExperimentConfig>>('/api/v1/experiment-configs', data),

  update: (id: string, data: UpdateExperimentConfigRequest) =>
    apiClient.put<never, ApiResponse<ExperimentConfig>>(`/api/v1/experiment-configs/${id}`, data),

  delete: (id: string) => apiClient.delete('/api/v1/experiment-configs', { params: { id } }),

  getAllStats: () =>
    apiClient.get<never, ApiResponse<ExperimentConfigStats[]>>('/api/v1/experiment-configs/stats'),

  exportPack: (ids?: string[]) =>
    apiClient.get<never, ApiResponse<ExperimentPack>>('/api/v1/experiment-configs/export', {
      params: ids?.length ? { ids: ids.join(',') } : undefined,
    }),

  importPack: (pack: unknown) =>
    apiClient.post<
      never,
      ApiResponse<{
        kind: string
        players_created: string[]
        players_reused: string[]
        requirements?: { providers: string[]; ollama_tags: string[] }
      }>
    >('/api/v1/experiment-configs/import', pack),
}
