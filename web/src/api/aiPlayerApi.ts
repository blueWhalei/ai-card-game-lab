import { apiClient } from './client'
import type { ApiResponse } from './types'

export interface AIPlayer {
  id: string
  name: string
  description: string
  avatar: string
  model_config: {
    provider: string
    model_name: string
    temperature: number
    top_p: number
    max_tokens: number
  }
}

export interface AIPlayerStats {
  player_id: string
  games_played: number
  wins: number
  losses: number
  win_rate: number
  last_game_id: string | null
  last_game_at: string | null
}

export interface CreateAIPlayerRequest {
  id: string
  name: string
  description?: string
  avatar?: string
  model_config_data: {
    provider: string
    model_name: string
    temperature: number
    top_p: number
    max_tokens: number
  }
}

export interface UpdateAIPlayerRequest {
  name?: string
  description?: string
  avatar?: string
  model_config_data?: {
    provider: string
    model_name: string
    temperature: number
    top_p: number
    max_tokens: number
  }
}

export const aiPlayerApi = {
  list: () => apiClient.get<never, ApiResponse<AIPlayer[]>>('/api/v1/ai-players'),

  get: (id: string) => apiClient.get<never, ApiResponse<AIPlayer>>(`/api/v1/ai-players/${id}`),

  create: (data: CreateAIPlayerRequest) =>
    apiClient.post<never, ApiResponse<AIPlayer>>('/api/v1/ai-players', data),

  update: (id: string, data: UpdateAIPlayerRequest) =>
    apiClient.put<never, ApiResponse<AIPlayer>>(`/api/v1/ai-players/${id}`, data),

  delete: (id: string) => apiClient.delete(`/api/v1/ai-players/${id}`),

  getStats: (id: string) =>
    apiClient.get<never, ApiResponse<AIPlayerStats>>(`/api/v1/ai-players/${id}/stats`),

  getAllStats: () => apiClient.get<never, ApiResponse<AIPlayerStats[]>>('/api/v1/ai-players/stats'),
}
