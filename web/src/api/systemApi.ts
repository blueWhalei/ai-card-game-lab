import { apiClient } from './client'
import type { ApiResponse } from './types'

export { gameTypeLabel } from '@/utils/constants'

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
  models_dir: string
  prompt_version?: string
  prompt_ab_test_enabled?: boolean
  prompt_ab_test_ratio?: number
  max_concurrent_games?: number
  training_deps_available?: boolean
  default_base_models?: string[]
}

export type StartupCheck = {
  data_dirs_ready: boolean
  can_collect: boolean
  seed_provider: string
  providers: ProviderInfo[]
  warnings: string[]
}

export type RuntimeStats = {
  cpu_percent: number
  memory_total_mb: number
  memory_used_mb: number
  memory_available_mb: number
  training_active?: boolean
}

export type EngineInfo = {
  id: string
  min_players: number
  max_players: number
}

export type BenchmarkSeedsInfo = {
  count: number
  description: string
  seeds: number[]
}

export const systemApi = {
  listGameTypes: () =>
    apiClient.get<never, ApiResponse<string[]>>('/api/v1/system/game-types'),

  listEngines: () =>
    apiClient.get<never, ApiResponse<EngineInfo[]>>('/api/v1/system/engines'),

  benchmarkSeeds: () =>
    apiClient.get<never, ApiResponse<BenchmarkSeedsInfo>>('/api/v1/system/benchmark-seeds'),

  listProviders: () =>
    apiClient.get<never, ApiResponse<ProviderInfo[]>>('/api/v1/system/providers'),

  getConfig: () =>
    apiClient.get<never, ApiResponse<SystemConfig>>('/api/v1/system/config'),

  getRuntimeStats: () =>
    apiClient.get<never, ApiResponse<RuntimeStats>>('/api/v1/system/runtime-stats'),

  getStartupCheck: () =>
    apiClient.get<never, ApiResponse<StartupCheck>>('/api/v1/system/startup-check'),

  seedDemo: () =>
    apiClient.post<never, ApiResponse<{ game_id: string; created: boolean }>>(
      '/api/v1/system/seed-demo',
    ),
}
