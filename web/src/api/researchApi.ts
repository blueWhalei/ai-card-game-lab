import { apiClient } from './client'
import type { Trace } from './traces'
import type { ApiResponse } from './types'
import type { DecisionPoint } from './decision'
import type { ComparisonSnapshot, ComparisonSnapshotSummary } from './experimentApi'
import type { ObserverSnapshot } from '@/types/observer'
import type { ExperimentScenarioId } from '@/utils/experimentWorkbench'
import type { PuzzleResult, PuzzlePackSummary } from './puzzleApi'

export interface PairScenarioCounts {
  scenario: ExperimentScenarioId | null
  left_n: number
  right_n: number
  left_game_n: number
  right_game_n: number
  pair_n: number
}

export type PairedDecision = Pick<
  DecisionPoint,
  | 'id'
  | 'game_id'
  | 'player_id'
  | 'round_number'
  | 'game_phase'
  | 'hand_cards'
  | 'opponent_hands'
  | 'last_action'
  | 'chosen_action'
> & { action_id: string }
export interface DecisionPairList {
  comparison_id: string
  scenario: ExperimentScenarioId | null
  cutoff: string
  read_at: string
  endgame_max_hand: number
  cohort_n: number
  groups: PairScenarioCounts[]
  runs: { id: string; name: string }[]
  items: {
    seed: number
    left_game_id: string
    right_game_id: string
    left_n: number
    right_n: number
  }[]
}
export interface DecisionPairFrame {
  turn: number
  status: 'same' | 'divergence' | 'different_path' | 'different_context' | 'unverified'
  reasons: string[]
  left: PairedDecision | null
  right: PairedDecision | null
  left_ended: boolean
  right_ended: boolean
  left_scenario: ExperimentScenarioId | null
  right_scenario: ExperimentScenarioId | null
}
export interface DecisionPair {
  boards: {
    cutoff: string
    read_at: string
    engine_version: string
    left: DecisionBoards
    right: DecisionBoards
  }
  scenario: ExperimentScenarioId | null
  matching_turns: number[]
  seed: number
  left: { experiment_id: string; name: string; game_id: string }
  right: { experiment_id: string; name: string; game_id: string }
  frames: DecisionPairFrame[]
  first_divergence: number | null
}

export interface DecisionBoards {
  frames: Record<number, { decision_id: string; snapshot: ObserverSnapshot }>
  status: 'verified' | 'unverified' | 'unsupported_engine'
  stopped_at: number | null
}
export interface DecisionEvidencePreview {
  comparison_id: string
  seed: number
  decision: PairedDecision & EvidenceCandidate
}
export interface DecisionEvidenceTargets {
  decision_id: string
  items: (ComparisonSnapshotSummary & { seed: number })[]
  next_offset: number | null
}
export interface PuzzleEvidenceTargets {
  pack_id: string
  run_id: string
  report_hash: string
  read_at: string
  items: ComparisonSnapshotSummary[]
  next_offset: number | null
}
export interface TraceEvidenceTargets {
  trace_id: string
  source_hash: string
  items: ComparisonSnapshotSummary[]
  next_offset: number | null
}
export interface TraceEvidenceReference {
  trace_id: string
  expected_source_hash: string
  note: string
}
export interface ResearchTracePreview {
  comparison_id: string
  cutoff: string
  read_at: string
  source_hash: string
  trace: Trace
  source: {
    experiment_id: string
    game_id: string
    game_type: string
    player_ids: string[]
    deal_seed: number
    created_at: string
    status: string
  }
}
export type TraceEvidenceStatus =
  | 'available'
  | 'changed'
  | 'missing'
  | 'identity_mismatch'
  | 'invalid'
export type CitationSource =
  | { kind: 'trace'; id: string }
  | { kind: 'decision'; id: string; turn: number }
  | { kind: 'puzzle'; packId: string; runId: string; reportHash: string; page: number }

export interface EvidenceCandidate {
  id: string
  game_id: string
  player_id: string
  round_number: number
  action_id: string
  ev_loss: number | null
  annotation: string | null
}
export interface EvidenceReference {
  decision_id: string
  note: string
}
export interface PuzzleEvidenceReference {
  pack_id: string
  run_id: string
  expected_report_hash: string
  note: string
}
export interface ResearchPuzzlePreview {
  result: PuzzleResult
  sources: { decision: EvidenceCandidate & Record<string, unknown> }[]
}
export interface PuzzleEvidenceStatus {
  record_status: 'available' | 'changed' | 'missing' | 'invalid' | 'unsupported'
  source_status: PuzzleResult['source_status'] | null
  decisions: ResearchVersion['evidence_status']
}
export interface ResearchVersionSummary {
  id: string
  revision: number
  created_at: string
}
export interface ResearchRecord extends ResearchVersionSummary {
  comparison_id: string
  observations: string
  interpretation: string
  limitations: string
  evidence: { note: string; decision: EvidenceCandidate & Record<string, unknown> }[]
  puzzle_evidence?: (ResearchPuzzlePreview & { note: string })[]
  trace_evidence?: (ResearchTracePreview & { note: string })[]
}
export interface ResearchVersion {
  record: ResearchRecord
  evidence_status: Record<string, 'available' | 'missing' | 'identity_mismatch' | 'changed'>
  puzzle_evidence_status?: PuzzleEvidenceStatus[]
  trace_evidence_status?: Record<string, TraceEvidenceStatus>
}
export interface ResearchReport extends ResearchVersion {
  kind: 'cardlab.research_report'
  comparison: ComparisonSnapshot
  exported_at: string
  scope: string
}
export interface ResearchDraft {
  expected_revision: number
  observations: string
  interpretation: string
  limitations: string
  evidence: EvidenceReference[]
  puzzle_evidence?: PuzzleEvidenceReference[]
  trace_evidence?: TraceEvidenceReference[]
}
export const researchApi = {
  traceTargets: (id: string, offset = 0) =>
    apiClient.get<never, ApiResponse<TraceEvidenceTargets>>(
      `/api/v1/experiments/evidence/traces/${encodeURIComponent(id)}/comparisons`,
      { params: { offset } },
    ),
  tracePreview: (comparison: string, id: string) =>
    apiClient.get<never, ApiResponse<ResearchTracePreview>>(
      `/api/v1/experiments/comparisons/${encodeURIComponent(comparison)}/traces/${encodeURIComponent(id)}`,
    ),
  puzzleTargets: (pack: string, run: string, offset = 0) =>
    apiClient.get<never, ApiResponse<PuzzleEvidenceTargets>>(
      `/api/v1/experiments/evidence/puzzle-results/${encodeURIComponent(pack)}/${encodeURIComponent(run)}/comparisons`,
      { params: { offset } },
    ),
  decision: (comparison: string, decision: string) =>
    apiClient.get<never, ApiResponse<DecisionEvidencePreview>>(
      `/api/v1/experiments/comparisons/${encodeURIComponent(comparison)}/decisions/${encodeURIComponent(decision)}`,
    ),
  decisionTargets: (decision: string, offset = 0) =>
    apiClient.get<never, ApiResponse<DecisionEvidenceTargets>>(
      `/api/v1/experiments/evidence/decisions/${encodeURIComponent(decision)}/comparisons`,
      { params: { offset } },
    ),
  puzzlePacks: (id: string) =>
    apiClient.get<never, ApiResponse<PuzzlePackSummary[]>>(
      `/api/v1/experiments/comparisons/${id}/puzzle-packs`,
    ),
  puzzlePreview: (id: string, pack: string, run: string) =>
    apiClient.get<never, ApiResponse<ResearchPuzzlePreview>>(
      `/api/v1/experiments/comparisons/${id}/puzzle-results/${encodeURIComponent(pack)}/${encodeURIComponent(run)}`,
    ),
  pairs: (id: string, scenario?: ExperimentScenarioId) =>
    apiClient.get<never, ApiResponse<DecisionPairList>>(
      `/api/v1/experiments/comparisons/${id}/pairs`,
      { params: { scenario } },
    ),
  pair: (id: string, seed: number, scenario?: ExperimentScenarioId) =>
    apiClient.get<never, ApiResponse<DecisionPair>>(
      `/api/v1/experiments/comparisons/${id}/pairs/${seed}`,
      { params: { scenario } },
    ),
  candidates: (id: string, offset = 0) =>
    apiClient.get<never, ApiResponse<{ total: number; items: EvidenceCandidate[] }>>(
      `/api/v1/experiments/comparisons/${id}/decisions`,
      { params: { limit: 20, offset } },
    ),
  versions: (id: string, offset = 0) =>
    apiClient.get<never, ApiResponse<ResearchVersionSummary[]>>(
      `/api/v1/experiments/comparisons/${id}/conclusions`,
      { params: { limit: 20, offset } },
    ),
  get: (id: string) =>
    apiClient.get<never, ApiResponse<ResearchVersion>>(`/api/v1/experiments/conclusions/${id}`),
  save: (id: string, data: ResearchDraft) =>
    apiClient.post<never, ApiResponse<ResearchVersion>>(
      `/api/v1/experiments/comparisons/${id}/conclusions`,
      data,
    ),
  export: (id: string) =>
    apiClient.get<never, ApiResponse<ResearchReport>>(
      `/api/v1/experiments/conclusions/${id}/export`,
    ),
}
