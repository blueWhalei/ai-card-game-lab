import { apiClient } from './client'
import type { ApiResponse } from './types'

export interface ExperimentConfig {
  id: string
  name: string
  notes: string
  model_config: {
    provider: string
    model_name: string
    temperature: number
    top_p: number
    max_tokens: number
  }
}

export interface ExperimentConfigStats {
  config_id: string
  games_played: number
  wins: number
  losses: number
  win_rate: number
  last_game_id: string | null
  last_game_at: string | null
}

export interface CreateExperimentConfigRequest {
  id: string
  name: string
  notes?: string
  model_config_data: {
    provider: string
    model_name: string
    temperature: number
    top_p: number
    max_tokens: number
  }
}

export interface UpdateExperimentConfigRequest {
  name?: string
  notes?: string
  model_config_data?: {
    provider: string
    model_name: string
    temperature: number
    top_p: number
    max_tokens: number
  }
}

export const experimentConfigApi = {
  list: () =>
    apiClient.get<never, ApiResponse<ExperimentConfig[]>>('/api/v1/experiment-configs'),

  get: (id: string) =>
    apiClient.get<never, ApiResponse<ExperimentConfig>>(`/api/v1/experiment-configs/${id}`),

  create: (data: CreateExperimentConfigRequest) =>
    apiClient.post<never, ApiResponse<ExperimentConfig>>('/api/v1/experiment-configs', data),

  update: (id: string, data: UpdateExperimentConfigRequest) =>
    apiClient.put<never, ApiResponse<ExperimentConfig>>(`/api/v1/experiment-configs/${id}`, data),

  delete: (id: string) =>
    apiClient.delete('/api/v1/experiment-configs', { params: { id } }),

  getStats: (id: string) =>
    apiClient.get<never, ApiResponse<ExperimentConfigStats>>(
      `/api/v1/experiment-configs/${id}/stats`,
    ),

  getAllStats: () =>
    apiClient.get<never, ApiResponse<ExperimentConfigStats[]>>('/api/v1/experiment-configs/stats'),
}
