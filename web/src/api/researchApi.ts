import { apiClient } from './client'
import type { ApiResponse } from './types'

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
}
export interface ResearchVersion {
  record: ResearchRecord
  evidence_status: Record<string, 'available' | 'missing' | 'identity_mismatch' | 'changed'>
}
export interface ResearchDraft {
  expected_revision: number
  observations: string
  interpretation: string
  limitations: string
  evidence: EvidenceReference[]
}
export const researchApi = {
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
    apiClient.get<
      never,
      ApiResponse<
        ResearchVersion & {
          kind: 'cardlab.research_report'
          comparison: unknown
          exported_at: string
          scope: string
        }
      >
    >(`/api/v1/experiments/conclusions/${id}/export`),
}
