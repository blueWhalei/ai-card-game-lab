import { apiClient } from './client'
import type { ApiResponse } from './types'

export type PuzzleBaselineKind = 'heuristic' | 'random' | 'first'

export interface DecisionPuzzleSource {
  experiment_id: string
  experiment_name: string
  game_id: string
  decision_point_id: string
  decision_created_at: string
  round_num: number
  player_id: string
  game_phase: string
  deal_seed: number
  read_at: string
  source_hash: string
  candidates_evaluated: number
  legal_action_count: number
  evaluator_params: Record<string, unknown>
}

export interface DecisionPuzzleExtract {
  method: 'decision_record'
  question: string
  source: DecisionPuzzleSource
}

export function decisionPuzzleExtract(
  pack: PuzzlePackSummary | null,
): DecisionPuzzleExtract | null {
  const value = pack?.extract
  return value?.method === 'decision_record' && value.source && typeof value.question === 'string'
    ? (value as unknown as DecisionPuzzleExtract)
    : null
}

export interface PuzzlePackSummary {
  pack_id: string
  created_at: string
  game_type: string
  source_experiment_id: string
  puzzle_count: number
  extract: Record<string, unknown>
  notes: string
  kind: string
  schema_version: number
}

export interface BatchPuzzleExtract {
  method: 'rollout_spread'
  min_spread: number
  max_per_game: number
  max_total: number
  evaluator_params: Record<string, unknown>
  source_checks: Record<string, { decision_hash?: string; puzzle_hash?: string }>
  selection: {
    order: 'spread_desc_stable'
    source_game_ids: string[]
    selected_game_ids: string[]
    candidates: { puzzle_id: string; game_id: string; spread: number }[]
  }
}

export function batchPuzzleExtract(pack: PuzzlePackSummary): BatchPuzzleExtract | null {
  const value = pack.extract as unknown as Partial<BatchPuzzleExtract>
  return value.method === 'rollout_spread' &&
    value.selection?.order === 'spread_desc_stable' &&
    Array.isArray(value.selection.source_game_ids) &&
    Array.isArray(value.selection.selected_game_ids) &&
    value.selection.source_game_ids.every((p) => typeof p === 'string' && p.length > 0) &&
    value.selection.selected_game_ids.every((p) => typeof p === 'string' && p.length > 0) &&
    Array.isArray(value.selection.candidates) &&
    value.selection.candidates.every(
      (p) =>
        p &&
        typeof p.puzzle_id === 'string' &&
        typeof p.game_id === 'string' &&
        typeof p.spread === 'number' &&
        Number.isFinite(p.spread) &&
        p.spread >= 0,
    ) &&
    value.source_checks &&
    typeof value.source_checks === 'object' &&
    !Array.isArray(value.source_checks) &&
    Object.values(value.source_checks).every((p) => p && typeof p === 'object') &&
    typeof value.min_spread === 'number' &&
    Number.isFinite(value.min_spread) &&
    value.min_spread >= 0 &&
    Number.isSafeInteger(value.max_per_game) &&
    value.max_per_game! > 0 &&
    Number.isSafeInteger(value.max_total) &&
    value.max_total! >= 0 &&
    value.evaluator_params
    ? (value as BatchPuzzleExtract)
    : null
}

export interface PuzzlePreview {
  puzzle_id: string
  game_type: string
  best_action_id: string
  spread: number
  legal_action_count: number
  truncated: boolean
  observation?: {
    phase?: string
    player_id?: string
    text?: string
  }
  source?: {
    experiment_id?: string
    game_id?: string
    decision_point_id?: string
    round_num?: number
  }
}

export interface PuzzleRunSummary {
  n: number
  evaluated_n: number
  unevaluated_n: number
  accuracy: number | null
  mean_ev_loss: number | null
  truncated_n: number
}

export interface PuzzleRunRow {
  puzzle_id: string
  chosen_action_id: string
  best_action_id: string
  hit: boolean | null
  ev_loss: number | null
  truncated: boolean
}

export interface PuzzleRunReport {
  pack_snapshot?: PuzzleResultSnapshot
  pack_fingerprint?: string
  metric_version: string
  run_id: string
  pack_id: string
  baseline_kind: string
  seed: number
  created_at: string
  summary: PuzzleRunSummary
  puzzles: PuzzleRunRow[]
}

export interface PuzzleProbeSummary {
  n: number
  n_trials: number
  kinds: string[]
  comparisons_n: number
  repeat_consistency: number | null
  consistency: number | null
  base_evaluated_n: number
  base_unevaluated_n: number
  pert_evaluated_n: number
  pert_unevaluated_n: number
  base_accuracy: number | null
  pert_accuracy: number | null
  base_mean_ev_loss: number | null
  pert_mean_ev_loss: number | null
}

export interface PuzzleProbeReport {
  pack_snapshot?: PuzzleResultSnapshot
  pack_fingerprint?: string
  metric_version: string
  run_id: string
  pack_id: string
  baseline_kind: string
  seed: number
  created_at: string
  summary: PuzzleProbeSummary
  puzzles?: PuzzleProbeRow[]
}

export interface PuzzleProbeRow {
  puzzle_id: string
  base_chosen_action_id: string
  best_action_id: string
  trials: {
    trial: number
    control_action_id: string
    chosen_action_id: string
    consistent: boolean
    repeat_consistent: boolean
    hit: boolean | null
    ev_loss: number | null
  }[]
}
export interface PuzzleResultSnapshot {
  manifest: PuzzlePackSummary
  puzzles: {
    puzzle_id: string
    source: NonNullable<PuzzlePreview['source']>
    evaluator_params: Record<string, unknown>
    candidates_evaluated: number
    legal_action_count: number
  }[]
}
export interface PuzzleResult {
  report: PuzzleRunReport | PuzzleProbeReport
  source_status: 'matched' | 'changed' | 'missing' | 'unrecorded' | 'unreadable'
  read_at: string
  report_hash: string
}
export interface PuzzleResultList {
  items: {
    run_id: string
    kind: 'run' | 'probe'
    status: 'available' | 'invalid' | 'unsupported'
    created_at: string | null
    baseline_kind: PuzzleBaselineKind | null
  }[]
  total: number
  page: number
  page_size: number
  read_at: string
}

export interface PuzzleExtractRequest {
  experiment_id: string
  min_spread?: number
  max_per_game?: number
  max_total?: number
}

export const puzzleApi = {
  results: (packId: string, page = 1) =>
    apiClient.get<never, ApiResponse<PuzzleResultList>>(
      `/api/v1/puzzles/packs/${encodeURIComponent(packId)}/results`,
      { params: { page } },
    ),
  result: (packId: string, runId: string) =>
    apiClient.get<never, ApiResponse<PuzzleResult>>(
      `/api/v1/puzzles/packs/${encodeURIComponent(packId)}/results/${encodeURIComponent(runId)}`,
    ),
  decisionSource: (id: string) =>
    apiClient.get<never, ApiResponse<DecisionPuzzleSource>>(
      `/api/v1/puzzles/decisions/${encodeURIComponent(id)}`,
    ),
  fromDecision: (body: { decision_id: string; question: string; expected_source_hash: string }) =>
    apiClient.post<never, ApiResponse<PuzzlePackSummary>>('/api/v1/puzzles/from-decision', body),
  listPacks: () => apiClient.get<never, ApiResponse<PuzzlePackSummary[]>>('/api/v1/puzzles/packs'),

  getPack: (packId: string, preview = 5) =>
    apiClient.get<never, ApiResponse<{ manifest: PuzzlePackSummary; preview: PuzzlePreview[] }>>(
      `/api/v1/puzzles/packs/${encodeURIComponent(packId)}`,
      {
        params: { preview },
      },
    ),

  extract: (body: PuzzleExtractRequest) =>
    apiClient.post<never, ApiResponse<PuzzlePackSummary>>('/api/v1/puzzles/extract', body),

  run: (packId: string, body: { baseline_kind?: PuzzleBaselineKind; seed?: number } = {}) =>
    apiClient.post<never, ApiResponse<PuzzleRunReport>>(
      `/api/v1/puzzles/packs/${encodeURIComponent(packId)}/run`,
      body,
    ),

  probe: (
    packId: string,
    body: {
      baseline_kind?: PuzzleBaselineKind
      seed?: number
      n_trials?: number
      kinds?: Array<'shuffle_legal_actions' | 'shuffle_hand_cards'>
    } = {},
  ) =>
    apiClient.post<never, ApiResponse<PuzzleProbeReport>>(
      `/api/v1/puzzles/packs/${encodeURIComponent(packId)}/probe`,
      body,
    ),
}
