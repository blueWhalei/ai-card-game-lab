import { apiClient } from './client'
import type { ApiResponse } from './types'
import { GAME_TYPE_MAP } from '@/utils/constants'

export type ProviderInfo = {
  id: string
  name: string
  description: string
  configured: boolean
  default_model?: string
}

export type SystemConfig = {
  app_name: string
  version: string
  debug: boolean
  data_dir: string
  sqlite_path: string
  config_dir: string
  models_dir: string
  prompt_version?: string
  prompt_ab_test_enabled?: boolean
  prompt_ab_test_ratio?: number
  training_use_mock?: boolean
  training_deps_available?: boolean
  default_base_models?: string[]
}

export type RuntimeStats = {
  cpu_percent: number
  memory_total_mb: number
  memory_used_mb: number
  memory_available_mb: number
  training_active?: boolean
}

export const systemApi = {
  listGameTypes: () =>
    apiClient.get<never, ApiResponse<string[]>>('/api/v1/system/game-types'),

  listProviders: () =>
    apiClient.get<never, ApiResponse<ProviderInfo[]>>('/api/v1/system/providers'),

  getConfig: () =>
    apiClient.get<never, ApiResponse<SystemConfig>>('/api/v1/system/config'),

  getRuntimeStats: () =>
    apiClient.get<never, ApiResponse<RuntimeStats>>('/api/v1/system/runtime-stats'),
}

export function gameTypeLabel(id: string): string {
  return GAME_TYPE_MAP[id] ?? id
}
