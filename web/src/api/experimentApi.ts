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

/** Flat Task fields used by workbench UI (see ``flattenProtocol``). */
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

/** Nested protocol as stored/returned by the API (schema_version ≥ 2). */
export interface ExperimentProtocolNested {
  schema_version: number
  frozen_at: string
  dataset: {
    collect_mode?: CollectMode
    deal_seeds: number[]
    pair_deals: boolean
    source_experiment_id: string | null
  }
  solver: {
    players: ExperimentProtocolPlayer[]
    prompt_version: string
  }
  scorer: {
    eval_metric_ids: string[]
  }
  engine: {
    game_type: string
    engine_version: string
    decision_schema_version: number
    rules_ref: string | null
    phases: string[]
    prompt_keys: Record<string, string>
    roles: string[]
    supports_deal_seed: boolean
    benchmark_seed_count: number
  }
}

export type ExperimentProtocolRaw = ExperimentProtocol | ExperimentProtocolNested

export function flattenProtocol(
  protocol: ExperimentProtocolRaw | null | undefined,
): ExperimentProtocol | null {
  if (!protocol) return null
  if ('dataset' in protocol && protocol.dataset && typeof protocol.dataset === 'object') {
    const nested = protocol as ExperimentProtocolNested
    return {
      schema_version: nested.schema_version,
      frozen_at: nested.frozen_at,
      prompt_version: nested.solver?.prompt_version ?? '',
      players: nested.solver?.players ?? [],
      source_experiment_id: nested.dataset?.source_experiment_id ?? null,
      pair_deals: Boolean(nested.dataset?.pair_deals),
      deal_seeds: nested.dataset?.deal_seeds ?? [],
      collect_mode: nested.dataset?.collect_mode,
      eval_metric_ids: nested.scorer?.eval_metric_ids ?? [],
      game_type: nested.engine?.game_type ?? '',
      engine_version: nested.engine?.engine_version ?? '',
      decision_schema_version: nested.engine?.decision_schema_version ?? 0,
      rules_ref: nested.engine?.rules_ref ?? null,
      phases: nested.engine?.phases ?? [],
      prompt_keys: nested.engine?.prompt_keys ?? {},
      roles: nested.engine?.roles ?? [],
      supports_deal_seed: Boolean(nested.engine?.supports_deal_seed),
      benchmark_seed_count: nested.engine?.benchmark_seed_count ?? 0,
    }
  }
  return protocol as ExperimentProtocol
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

/** Coverage of the declared deal-seed set. Null unless collect_mode is benchmark. */
export interface ExperimentBenchmark {
  seed_total: number
  seed_started: number
  seed_finished: number
  seed_failed: number
  seed_running: number
  seed_remaining: number
  extra_games: number
  complete: boolean
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
  protocol?: ExperimentProtocolRaw | null
  created_at: string
  updated_at: string
  summary: ExperimentSummary
  games?: GameItem[]
  timeline?: ExperimentTimelineEvent[]
  validation?: ExperimentValidation
  next_step?: ExperimentNextStep
  delta?: ExperimentDelta | null
  benchmark?: ExperimentBenchmark | null
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

export interface ConclusionDraft {
  text: string
  locale: string
  verdict_key: ExperimentVerdictKey
  can_conclude: boolean
  blunder_ids: string[]
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
  protocol?: ExperimentProtocolRaw | null
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
  protocol?: ExperimentProtocolRaw | null
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

  conclusionDraft: (id: string, locale?: string) =>
    apiClient.post<never, ApiResponse<ConclusionDraft>>(
      `/api/v1/experiments/${id}/conclusion-draft`,
      undefined,
      { params: locale ? { locale } : undefined },
    ),

  clone: (id: string, data?: CloneExperimentRequest) =>
    apiClient.post<never, ApiResponse<Experiment>>(`/api/v1/experiments/${id}/clone`, data ?? {}),

  collect: (id: string, data: CollectExperimentRequest) =>
    apiClient.post<never, ApiResponse<CollectExperimentResult>>(
      `/api/v1/experiments/${id}/collect`,
      data,
    ),

  cancelCollect: (id: string) =>
    apiClient.post<never, ApiResponse<{ cancelled_game_ids: string[]; count: number }>>(
      `/api/v1/experiments/${id}/cancel-collect`,
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
  protocol?: ExperimentProtocolRaw | null
}): boolean {
  return flattenProtocol(experiment.protocol)?.collect_mode === 'benchmark'
}
