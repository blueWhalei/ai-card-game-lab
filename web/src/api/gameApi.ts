import { apiClient } from './client'
import type { ApiResponse, PaginatedData } from './types'

export interface CreateGameRequest {
  game_type: string
  player_ids: string[]
  mode?: string
}

export interface BatchCreateRequest {
  game_type: string
  player_ids: string[]
  count: number
}

export interface GameItem {
  id: string
  game_type: string
  status: string
  player_ids: string[]
  data_file: string
  winner_id: string | null
  winner_role: string | null
  total_rounds: number | null
  created_at: string
  finished_at: string | null
  metadata: Record<string, unknown> | null
  experiment_id?: string | null
}

export interface ReplayData {
  game: GameItem
  rounds: Array<{
    game_id: string
    round_num: number
    player_id: string
    action_type: string
    cards: string[]
    hand_snapshot: string[]
    all_hands: Record<string, string[]>
    prompt: Array<{ role: string; content: string }>
    raw_response: string | null
    thinking: string
    prompt_tokens: number | null
    completion_tokens: number | null
    total_tokens: number | null
    response_time_ms: number | null
    model_provider: string | null
    model_name: string | null
    created_at: string
  }>
  thinking: Record<number, string>
}

export interface RoundData {
  game_id: string
  round_num: number
  player_id: string
  action_type: string
  cards: string[]
  hand_snapshot: string[]
  all_hands: Record<string, string[]>
  prompt: Array<{ role: string; content: string }>
  raw_response: string | null
  thinking: string
  prompt_tokens: number | null
  completion_tokens: number | null
  response_time_ms: number | null
  model_provider: string | null
  model_name: string | null
  created_at: string
}

export const gameApi = {
  list: (params?: Record<string, string | number>) =>
    apiClient.get<never, ApiResponse<PaginatedData<GameItem>>>('/api/v1/games', { params }),

  create: (data: CreateGameRequest) =>
    apiClient.post<never, ApiResponse<GameItem>>('/api/v1/games', data),

  get: (id: string) => apiClient.get<never, ApiResponse<GameItem>>(`/api/v1/games/${id}`),

  start: (id: string) => apiClient.post<never, ApiResponse<GameItem>>(`/api/v1/games/${id}/start`),

  pause: (id: string) =>
    apiClient.post<never, ApiResponse<Record<string, string>>>(`/api/v1/games/${id}/pause`),

  resume: (id: string) =>
    apiClient.post<never, ApiResponse<Record<string, string>>>(`/api/v1/games/${id}/resume`),

  replay: (id: string) =>
    apiClient.get<never, ApiResponse<ReplayData>>(`/api/v1/games/${id}/replay`),

  rounds: (id: string) =>
    apiClient.get<never, ApiResponse<RoundData[]>>(`/api/v1/games/${id}/rounds`),

  batch: (data: BatchCreateRequest) =>
    apiClient.post<never, ApiResponse<{ game_ids: string[]; count: number }>>(
      '/api/v1/games/batch',
      data,
    ),
}
