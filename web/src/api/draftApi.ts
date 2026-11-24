import { apiClient } from './client'
import type { ApiResponse } from './types'
import type { ResearchDraft } from './researchApi'

export interface NotebookDraft {
  kind: 'experiment'
  hypothesis: string
  notes: string
  conclusion: string
  tags_input: string
}

export interface ComparisonDraft extends ResearchDraft {
  kind: 'comparison'
}

export type DraftContent = NotebookDraft | ComparisonDraft
export type DraftKind = DraftContent['kind']
export interface DraftRecord {
  revision: number
  updated_at: string | null
  content: DraftContent
}

export const draftApi = {
  get: (kind: DraftKind, id: string) =>
    apiClient.get<never, ApiResponse<DraftRecord>>(
      `/api/v1/drafts/${kind}/${encodeURIComponent(id)}`,
    ),
  save: (kind: DraftKind, id: string, revision: number, content: DraftContent) =>
    apiClient.put<never, ApiResponse<DraftRecord>>(
      `/api/v1/drafts/${kind}/${encodeURIComponent(id)}`,
      {
        expected_revision: revision,
        content,
      },
    ),
}
