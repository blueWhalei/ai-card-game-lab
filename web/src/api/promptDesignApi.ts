import { apiClient } from './client'
import type { ApiResponse } from './types'
import type { Experiment } from './experimentApi'
import type { ResearchRecord } from './researchApi'

export type PrimaryMetric =
  | { kind: 'landlord_win_rate' }
  | { kind: 'seat_team_win_rate'; player_id: string }

export interface OutcomeScope {
  primary_metric: PrimaryMetric
  affected_player_ids: string[]
}

export interface PromptDesign extends OutcomeScope {
  kind: 'prompt_ab'
  baseline_id: string
  template_key: string
  baseline_hash: string
  variant_hash: string
  hypothesis: string
  created_at: string
  source_revision_id?: string
}
export interface PromptOption {
  template_key: string
  version: string
  content: string
  content_hash: string
}
export interface PromptDesignPreview {
  source_conclusion?: Omit<ResearchRecord, 'evidence'> | null
  baseline: Pick<
    Experiment,
    'id' | 'name' | 'study_id' | 'protocol' | 'target_games' | 'player_ids'
  >
  affected_player_ids: string[]
  fingerprint: string
  issues: string[]
  options: PromptOption[]
}
export interface CreatePromptVariant {
  source_revision_id?: string
  primary_metric: PrimaryMetric
  study_id: string
  baseline_fingerprint: string
  template_key: string
  version: string
  content_hash: string
  name: string
  hypothesis: string
}
export const promptDesignApi = {
  holdout: (id: string) =>
    apiClient.put<never, ApiResponse<{ baseline_id: string; variant_id: string }>>(
      `/api/v1/experiments/${encodeURIComponent(id)}/holdout`,
    ),
  preview: (id: string, source_revision_id?: string) =>
    apiClient.get<never, ApiResponse<PromptDesignPreview>>(
      `/api/v1/experiments/${encodeURIComponent(id)}/prompt-design`,
      { params: source_revision_id ? { source_revision_id } : undefined },
    ),
  create: (id: string, body: CreatePromptVariant) =>
    apiClient.post<never, ApiResponse<Experiment>>(
      `/api/v1/experiments/${encodeURIComponent(id)}/prompt-variant`,
      body,
    ),
}
