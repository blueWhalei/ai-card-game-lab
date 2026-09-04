import { apiClient } from './client'
import type { ApiResponse } from './types'
import type { GameItem } from './gameApi'
import { tt } from '@/i18n'

export type ExperimentStatus =
  | 'pending_collect'
  | 'collecting'
  | 'ready_review'
  | 'ready_more'

export type CollectMode = 'free' | 'benchmark'

export type ExperimentNextStepId =
  | 'collect'
  | 'watch'
  | 'decisions'
  | 'review_decisions'
  | 'register_train'
  | 'open_control'
  | 'collect_control'
  | 'compare'
  | 'collect_more'
  | 'review'

export type ExperimentNextStepAction =
  | 'collect'
  | 'games'
  | 'decisions'
  | 'train'
  | 'control'
  | 'control_collect'
  | 'compare'
  | 'stay'

export interface ExperimentTimelineEvent {
  id: string
  at: string
  ref_id: string | null
}

export interface ExperimentControlProgress {
  id: string
  name: string
  finished_games: number
  target_games: number
  paired_n: number
  ready: boolean
}

export interface ExperimentValidation {
  control_experiment_ids: string[]
  validation_ready: boolean
  suggested_compare_ids: string[]
  paired_n: number
  control_progress?: ExperimentControlProgress[]
  all_controls_ready?: boolean
}

export interface ExperimentNextStep {
  id: ExperimentNextStepId
  action: ExperimentNextStepAction
  ref_id?: string
}

export interface ExperimentPlayerStat {
  player_id: string
  wins: number
  win_rate: number
  win_rate_ci?: [number, number]
  train_usable_decisions: number
  avg_response_time_ms: number
  trace_count: number
  games_as_landlord?: number
  wins_as_landlord?: number
  landlord_win_rate?: number
}

export interface ExperimentProtocolPlayer {
  id: string
  name: string
  notes: string
  model_config: {
    provider: string
    model_name: string
    temperature?: number
    top_p?: number
    max_tokens?: number
  }
}

export interface ExperimentProtocol {
  schema_version: number
  frozen_at: string
  prompt_version: string
  players: ExperimentProtocolPlayer[]
  source_experiment_id: string | null
  pair_deals: boolean
  deal_seeds: number[]
  collect_mode?: CollectMode
  game_type: string
  engine_version: string
  decision_schema_version: number
  rules_ref: string | null
  phases: string[]
  prompt_keys: Record<string, string>
  roles: string[]
  eval_metric_ids: string[]
  supports_deal_seed: boolean
  benchmark_seed_count: number
}

export type ExperimentDeltaRelation = 'vs_source' | 'vs_control'

export type ExperimentDeltaReason = 'no_games' | 'peer_not_ready' | 'low_power'

/** Plain-language claim the verdict block renders; wording lives in `stage.verdict.*`. */
export type ExperimentVerdictKey = 'stronger' | 'weaker' | 'even' | 'peer_pending' | 'no_data'

export interface ExperimentScenarioScore {
  n: number
  train_usable_n: number
  train_usable_rate: number
  parser_n: number
  parser_ok: number
  parser_success_rate: number
}

export interface ExperimentScenarioDiff {
  this_n: number
  peer_n: number
  train_usable_rate_diff: number | null
  parser_success_rate_diff: number | null
}

export interface ExperimentDelta {
  peer_id: string
  peer_name: string
  relation: ExperimentDeltaRelation
  peer_ready: boolean
  this_landlord_win_rate: number
  peer_landlord_win_rate: number
  landlord_win_rate_diff: number | null
  this_landlord_win_rate_ci: [number, number] | null
  peer_landlord_win_rate_ci: [number, number] | null
  this_decisive_n: number
  peer_decisive_n: number
  paired_n: number
  paired_landlord_win_rate_diff: number | null
  low_power: boolean
  can_conclude: boolean
  inconclusive_reason: ExperimentDeltaReason | null
  verdict_key?: ExperimentVerdictKey
  scenario_diffs?: Record<string, ExperimentScenarioDiff>
}

export interface ExperimentCredibility {
  decisive_n: number
  landlord_ci_width: number | null
  low_power: boolean
}

export interface ExperimentSummary {
  status: ExperimentStatus
  target_games: number
  total_games: number
  active_games: number
  finished_games: number
  games_with_winner: number
  train_usable_decisions: number
  not_usable_decisions?: number
  decision_total?: number
  train_usable_rate?: number
  decision_count?: number
  avg_rounds: number
  wins_by_config: Record<string, number>
  wins_by_role?: Record<string, number>
  decisive_games?: number
  landlord_win_rate?: number
  landlord_win_rate_ci?: [number, number]
  parser_success_rate?: number
  parser_n?: number
  avg_response_time_ms?: number
  p50_response_ms?: number
  p95_response_ms?: number
  total_tokens?: number
  tokens_per_game?: number
  avg_tokens_per_round?: number
  status_counts?: Record<string, number>
  player_stats: ExperimentPlayerStat[]
  latest_game_id: string | null
  paired_games?: number
  credibility?: ExperimentCredibility
  scenario_scores?: Record<string, ExperimentScenarioScore>
}

export interface Experiment {
  id: string
  name: string
  notes: string
  hypothesis: string
  conclusion: string
  tags: string[]
  game_type: string
  player_ids: string[]
  target_games: number
  protocol?: ExperimentProtocol | null
  created_at: string
  updated_at: string
  summary: ExperimentSummary
  games?: GameItem[]
  timeline?: ExperimentTimelineEvent[]
  validation?: ExperimentValidation
  next_step?: ExperimentNextStep
  delta?: ExperimentDelta | null
}

export interface CreateExperimentRequest {
  name: string
  notes?: string
  hypothesis?: string
  tags?: string[]
  game_type?: string
  player_ids: string[]
  target_games: number
  source_experiment_id?: string | null
  pair_deals?: boolean
  collect_mode?: CollectMode
}

export interface UpdateExperimentRequest {
  name?: string
  notes?: string
  hypothesis?: string
  conclusion?: string
  tags?: string[]
}

export interface CloneExperimentRequest {
  name?: string
  copy_deal_seeds?: boolean
  copy_hypothesis?: boolean
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
  paired_wins?: number
  games_as_landlord?: number
  wins_as_landlord?: number
  landlord_win_rate?: number
}

export interface ExperimentCompareRow {
  id: string
  name: string
  notes: string
  game_type: string
  player_ids: string[]
  protocol?: ExperimentProtocol | null
  finished_games: number
  games_with_winner: number
  avg_rounds: number
  avg_response_time_ms: number
  p50_response_ms?: number
  p95_response_ms?: number
  total_tokens: number
  tokens_per_game?: number
  avg_tokens_per_round: number
  train_usable_rate: number
  train_usable_n: number
  decision_count: number
  parser_success_rate: number
  parser_n: number
  wins_by_role?: Record<string, number>
  decisive_games?: number
  landlord_win_rate?: number
  landlord_win_rate_ci?: [number, number]
  credibility?: ExperimentCredibility
  status_counts?: Record<string, number>
  player_stats: ExperimentComparePlayerStat[]
  paired_n?: number
  paired_seat_wins?: number[]
  paired_landlord_win_rate?: number
  scenario_scores?: Record<string, ExperimentScenarioScore>
}

export interface ExperimentPairedSummary {
  shared_seeds: number
  source_id: string
  control_id: string
  landlord_win_rate_diff: number | null
  low_power: boolean
}

export interface ExperimentCompareResult {
  experiments: ExperimentCompareRow[]
  paired_summary?: ExperimentPairedSummary
}

export interface ExperimentPackRequirements {
  providers: string[]
  ollama_tags: string[]
}

export interface ExperimentPackPlayer {
  id: string
  name: string
  notes: string
  model_config: ExperimentProtocolPlayer['model_config']
}

export interface ExperimentPack {
  kind: 'cardlab.player_pack' | 'cardlab.experiment_pack'
  schema_version: number
  exported_at?: string
  experiment?: {
    name: string
    notes: string
    hypothesis: string
    tags: string[]
    game_type: string
    player_ids: string[]
    target_games: number
    collect_mode: CollectMode
  }
  protocol?: ExperimentProtocol | null
  players: ExperimentPackPlayer[]
  requirements?: ExperimentPackRequirements
  deal_seeds?: number[]
}

export interface ExperimentPackImportResult {
  kind: ExperimentPack['kind']
  experiment: Experiment | null
  players_created: string[]
  players_reused: string[]
  requirements?: ExperimentPackRequirements
  unconfigured_providers?: string[]
}

export const experimentApi = {
  list: () => apiClient.get<never, ApiResponse<Experiment[]>>('/api/v1/experiments'),

  get: (id: string) =>
    apiClient.get<never, ApiResponse<Experiment>>(`/api/v1/experiments/${id}`),

  create: (data: CreateExperimentRequest) =>
    apiClient.post<never, ApiResponse<Experiment>>('/api/v1/experiments', data),

  update: (id: string, data: UpdateExperimentRequest) =>
    apiClient.patch<never, ApiResponse<Experiment>>(`/api/v1/experiments/${id}`, data),

  clone: (id: string, data?: CloneExperimentRequest) =>
    apiClient.post<never, ApiResponse<Experiment>>(`/api/v1/experiments/${id}/clone`, data ?? {}),

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

  exportPack: (id: string) =>
    apiClient.get<never, ApiResponse<ExperimentPack>>(`/api/v1/experiments/${id}/export`),

  importPack: (pack: unknown) =>
    apiClient.post<never, ApiResponse<ExperimentPackImportResult>>(
      '/api/v1/experiments/import',
      pack,
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

export function experimentTimelineLabel(id: string): string {
  return tt(`experiment.timeline.${id}`)
}

export function isBenchmarkExperiment(experiment: {
  protocol?: ExperimentProtocol | null
}): boolean {
  return experiment.protocol?.collect_mode === 'benchmark'
}
