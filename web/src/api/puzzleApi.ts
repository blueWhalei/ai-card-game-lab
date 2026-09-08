import { apiClient } from './client'
import type { ApiResponse } from './types'

export type PuzzleBaselineKind = 'heuristic' | 'random' | 'first'

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
    game_id?: string
    decision_id?: string
    round_number?: number
  }
}

export interface PuzzleRunSummary {
  n: number
  accuracy: number
  mean_ev_loss: number
  truncated_n: number
}

export interface PuzzleRunRow {
  puzzle_id: string
  chosen_action_id: string
  best_action_id: string
  hit: boolean
  ev_loss: number
  truncated: boolean
}

export interface PuzzleRunReport {
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
  consistency: number
  base_accuracy: number
  pert_accuracy: number
  base_mean_ev_loss: number
  pert_mean_ev_loss: number
}

export interface PuzzleProbeReport {
  run_id: string
  pack_id: string
  baseline_kind: string
  seed: number
  created_at: string
  summary: PuzzleProbeSummary
  puzzles?: unknown[]
}

export interface PuzzleExtractRequest {
  experiment_id: string
  min_spread?: number
  max_per_game?: number
  max_total?: number
}

export const puzzleApi = {
  listPacks: () =>
    apiClient.get<never, ApiResponse<PuzzlePackSummary[]>>('/api/v1/puzzles/packs'),

  getPack: (packId: string, preview = 5) =>
    apiClient.get<
      never,
      ApiResponse<{ manifest: PuzzlePackSummary; preview: PuzzlePreview[] }>
    >(`/api/v1/puzzles/packs/${encodeURIComponent(packId)}`, {
      params: { preview },
    }),

  extract: (body: PuzzleExtractRequest) =>
    apiClient.post<never, ApiResponse<PuzzlePackSummary>>('/api/v1/puzzles/extract', body),

  run: (
    packId: string,
    body: { baseline_kind?: PuzzleBaselineKind; seed?: number } = {},
  ) =>
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
