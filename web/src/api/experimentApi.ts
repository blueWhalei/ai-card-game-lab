import { apiClient } from './client'
import type { ApiResponse } from './types'
import type { GameItem } from './gameApi'
import { tt } from '@/i18n'
import type { OutcomeScope, PromptDesign } from './promptDesignApi'

export type ExperimentStatus = 'pending_collect' | 'collecting' | 'ready_review' | 'ready_more'

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
  decided_games: number
  win_rate: number | null
  win_rate_ci: [number, number] | null
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
  policy_kind?: 'llm' | 'tool_loop' | 'search' | 'heuristic' | 'random' | 'first'
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
  /** Actual frozen versions per template key; may differ after a single-phase change. */
  prompt_versions?: Record<string, string>
  /** content_hash per template_key when solver.prompts was frozen */
  prompt_hashes?: Record<string, string>
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

/** Nested protocol as stored/returned by the API (schema_version = 2). */
export interface ExperimentProtocolNested {
  design?: PromptDesign
  schema_version: number
  frozen_at: string
  dataset: {
    holdout_for?: string
    collect_mode?: CollectMode
    deal_seeds: number[]
    pair_deals: boolean
    source_experiment_id: string | null
  }
  solver: {
    players: ExperimentProtocolPlayer[]
    prompt_version: string
    prompts?: Record<string, { version?: string; content?: string; content_hash?: string }>
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

export type ExperimentProtocolRaw = ExperimentProtocolNested

export function flattenProtocol(
  protocol: ExperimentProtocolRaw | null | undefined,
): ExperimentProtocol | null {
  if (!protocol) return null
  if (protocol.schema_version !== 2) return null
  const nested = protocol
  return {
    schema_version: nested.schema_version,
    frozen_at: nested.frozen_at,
    prompt_version: nested.solver?.prompt_version ?? '',
    prompt_versions: Object.fromEntries(
      Object.entries(nested.solver?.prompts ?? {}).map(([key, entry]) => [
        key,
        String(entry?.version ?? ''),
      ]),
    ),
    prompt_hashes: Object.fromEntries(
      Object.entries(nested.solver?.prompts ?? {}).map(([key, entry]) => [
        key,
        String(entry?.content_hash ?? ''),
      ]),
    ),
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

export type ExperimentDeltaRelation = 'vs_source' | 'vs_control'

export type ExperimentDeltaReason =
  | 'no_games'
  | 'peer_not_ready'
  | 'low_power'
  | 'protocol_mismatch'
  | 'missing_paired_evidence'
  | 'incomplete_holdout'
  | 'uncertain_difference'

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

export type DealPurpose = 'development' | 'holdout' | 'mixed'

export interface PairedOutcomeCounts {
  both_won: number
  a_only_won: number
  b_only_won: number
  both_lost: number
}

export interface PairedStatistics {
  outcome_counts: PairedOutcomeCounts
  ci_method: 'clopper_pearson_bonferroni'
}

export interface ExperimentDelta extends OutcomeScope, PairedStatistics {
  deal_purpose: DealPurpose
  paired_excluded_n: number
  difference_basis: 'paired' | 'unpaired' | null
  design_hypothesis: string | null
  peer_id: string
  peer_name: string
  relation: ExperimentDeltaRelation
  peer_ready: boolean
  this_win_rate: number | null
  peer_win_rate: number | null
  win_rate_diff: number | null
  this_win_rate_ci: [number, number] | null
  peer_win_rate_ci: [number, number] | null
  this_decisive_n: number
  peer_decisive_n: number
  paired_n: number
  paired_p?: number | null
  paired_ci?: [number, number] | null
  low_power: boolean
  can_conclude: boolean
  inconclusive_reason: ExperimentDeltaReason | null
  verdict_key: ExperimentVerdictKey
  scenario_diffs?: Record<string, ExperimentScenarioDiff>
}

export interface ExperimentCredibility {
  decisive_n: number
  win_rate_ci_width: number | null
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
  study_id: string | null
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
  study_id?: string
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
  /** Template version frozen into protocol.solver (default server-side v3). */
  prompt_version?: string | null
}

export interface UpdateExperimentRequest {
  expected_draft_revision?: number
  name?: string
  notes?: string
  hypothesis?: string
  conclusion?: string
  tags?: string[]
}

export interface ConclusionDraftBlunder {
  id: string
  game_id: string
  round_number?: number | null
  action_id: string
  ev_loss?: number | null
}

export interface ConclusionDraft {
  text: string
  locale: string
  verdict_key: ExperimentVerdictKey
  can_conclude: boolean
  blunder_ids: string[]
  blunders: ConclusionDraftBlunder[]
}

export interface CloneExperimentRequest {
  name?: string
  copy_deal_seeds?: boolean
  copy_hypothesis?: boolean
}

export interface CollectExperimentRequest {
  count: number
  idempotency_key?: string
}

export interface CollectExperimentResult {
  game_ids: string[]
  count: number
}

export interface ExperimentComparePlayerStat {
  player_id: string
  wins: number
  decided_games: number
  win_rate: number | null
  win_rate_ci: [number, number] | null
  train_usable_decisions: number
  avg_response_time_ms: number
  trace_count: number
  paired_wins: number | null
  games_as_landlord?: number
  wins_as_landlord?: number
  landlord_win_rate?: number
}

export interface ExperimentCompareRow {
  hypothesis?: string
  game_ids: string[]
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
  paired_seat_wins: number[] | null
  paired_landlord_win_rate?: number
  scenario_scores?: Record<string, ExperimentScenarioScore>
}

export interface ExperimentPairedSummary extends OutcomeScope, PairedStatistics {
  paired_p?: number | null
  paired_ci?: [number, number] | null
  shared_seeds: number
  source_id: string
  control_id: string
  win_rate_diff: number | null
  low_power: boolean
}

export interface ComparisonReview {
  baseline_id: string
  /** Present when this exact pair matches a frozen Prompt A/B design. */
  design_changes?: string[]
  allowed_changes: string[]
  controlled: boolean
  reasons: string[]
  unknown: { experiment_id: string; fields: string[] }[]
  differences: {
    experiment_id: string
    path: string
    baseline: unknown
    variant: unknown
    baseline_missing: boolean
    variant_missing: boolean
    allowable: boolean
    declared: boolean
  }[]
}
export interface ComparisonCoverage {
  members?: { seed: number; game_ids: Record<string, string> }[]
  deal_purpose: DealPurpose
  excluded_n: number
  excluded_pairs: { seed: number; reasons: Record<string, string> }[]
  planned_shared: number
  effective_n: number
  effective_seeds: number[]
  experiments: {
    experiment_id: string
    planned: number
    valid: number
    not_shared: number
    excluded: Record<string, number>
    conflicts: { seed: number; game_ids: string[] }[]
    missing_seed_games: number
    unplanned_games: number
  }[]
}
export interface ComparisonSnapshotSummary {
  id: string
  title: string
  created_at: string
}
export interface ComparisonSnapshot extends ComparisonSnapshotSummary {
  result: ExperimentCompareResult
}

export interface ExperimentCompareResult {
  metric_version?: string
  computed_at?: string
  protocol_review?: ComparisonReview
  coverage?: ComparisonCoverage
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

export interface ScenarioCounts {
  decision_n: number
  evaluated_n: number
  game_n: number
}
export interface ScenarioGame {
  id: string
  status: string
  created_at: string
  decision_n: number
  evaluated_n: number
}
export interface ScenarioDecision {
  id: string
  game_id: string
  round_number: number
  player_id: string
  game_phase: string
  hand_cards: string[]
  chosen_action: { action_type: string; cards: string[] }
  action_id: string
  ev_loss: number | null
  evaluator_params: Record<string, unknown> | null
  created_at: string
}
export interface ScenarioQuery {
  scenario?: 'bidding' | 'playing' | 'endgame' | 'bomb'
  game_id?: string
  decision_id?: string
  game_page: number
  page: number
}
export interface ScenarioRecords {
  experiment_id: string
  scope: 'current_records'
  read_at: string
  endgame_max_hand: number
  scenario: ScenarioQuery['scenario'] | null
  totals: ScenarioCounts & { unrecorded_game_n: number }
  groups: (ScenarioCounts & { scenario: NonNullable<ScenarioQuery['scenario']> })[]
  games: { items: ScenarioGame[]; total: number; page: number; page_size: number }
  selected_game: ScenarioGame | null
  decisions: { items: ScenarioDecision[]; total: number; page: number; page_size: number }
}

export const experimentApi = {
  scenarios: (id: string, params: ScenarioQuery) =>
    apiClient.get<never, ApiResponse<ScenarioRecords>>(`/api/v1/experiments/${id}/scenarios`, {
      params,
    }),
  list: () => apiClient.get<never, ApiResponse<Experiment[]>>('/api/v1/experiments'),

  get: (id: string) => apiClient.get<never, ApiResponse<Experiment>>(`/api/v1/experiments/${id}`),

  createOffline: (data: Pick<CreateExperimentRequest, 'name' | 'study_id' | 'hypothesis'>) =>
    apiClient.post<never, ApiResponse<Experiment>>('/api/v1/experiments/offline', data),

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

  compare: (ids: string[], allowedChanges: string[] = []) =>
    apiClient.get<never, ApiResponse<ExperimentCompareResult>>('/api/v1/experiments/compare', {
      params: new URLSearchParams([
        ['ids', ids.join(',')],
        ...allowedChanges.map((p) => ['allowed_changes', p]),
      ]),
    }),

  saveComparison: (experimentIds: string[], title: string, allowedChanges: string[]) =>
    apiClient.post<never, ApiResponse<ComparisonSnapshot>>('/api/v1/experiments/comparisons', {
      experiment_ids: experimentIds,
      title,
      allowed_changes: allowedChanges,
    }),
  listComparisons: (offset = 0) =>
    apiClient.get<never, ApiResponse<ComparisonSnapshotSummary[]>>(
      '/api/v1/experiments/comparisons',
      { params: { limit: 30, offset } },
    ),
  getComparison: (id: string) =>
    apiClient.get<never, ApiResponse<ComparisonSnapshot>>(`/api/v1/experiments/comparisons/${id}`),

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
  ready_review: 'muted',
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
