import { apiClient } from './client'
import type { ApiResponse } from './types'
import type { BillingAttempt } from './studyBillingApi'

export type ReconciliationSource =
  | 'cost_export'
  | 'invoice_project_subtotal'
  | 'invoice_total'
  | 'payment_receipt'
export type ReviewAction = 'resolve' | 'reopen' | 'void'
export interface ReconciliationInput {
  attempt_id: string
  source_type: ReconciliationSource
  source_reference: string
  organization_id: string
  project_id: string | null
  currency: 'USD' | 'CNY' | 'EUR'
  source_amount: string
  period_start: string
  period_end: string
  scope_note: string
}
export type CsvColumnRole = 'amount' | 'date' | 'organization' | 'project' | 'currency'
export interface ReconciliationCsv {
  filename: string
  content_base64: string
  amount_column: string
  date_column: string
  organization_column: string | null
  project_column: string | null
  currency_column: string | null
}
type ReconciliationRequest = Omit<ReconciliationInput, 'source_amount'> &
  ({ source_amount: string } | { source_amount: null; csv: ReconciliationCsv })

export type ReconciliationSnapshot = Pick<
  BillingAttempt,
  'id' | 'revision' | 'organization_id' | 'project_id' | 'start_time' | 'end_time' | 'finished_at'
>
export interface ReconciliationResult {
  calculation_version: string
  input: ReconciliationInput
  result: 'matched' | 'difference' | 'not_comparable'
  reasons: ('basis' | 'organization' | 'project' | 'currency' | 'period' | 'bucket_boundary')[]
  interface_amount: string | null
  difference: string | null
  included_line_count: number | null
  snapshot: ReconciliationSnapshot &
    Pick<BillingAttempt, 'amount' | 'trigger' | 'schedule_revision'>
  source_url: string
  preview_hash: string
  csv_evidence?: {
    filename: string
    sha256: string
    parser_version: string
    columns: Record<CsvColumnRole, string | null>
    row_count: number
    first_service_date: string
    last_service_date: string
  }
}
export interface ReconciliationRecord {
  id: string
  study_id: string
  created_at: string
  comparison: ReconciliationResult
  review_revision: number
  review_action: ReviewAction | null
  review_reason: string | null
  reviewed_at: string | null
  pending: boolean
}
export interface ReconciliationReview {
  record_id: string
  revision: number
  action: ReviewAction
  reason: string
  created_at: string
}
export interface ReconciliationPolicy {
  study_id: string
  revision: number
  enabled: boolean | number
  reason: string
  created_at: string
}
export interface ReconciliationOverview {
  study_id: string
  policy: ReconciliationPolicy | null
  policy_history: ReconciliationPolicy[]
  pending_count: number
  admission_blocked: boolean
  records: ReconciliationRecord[]
  page: number
  page_size: number
  total: number
  read_at: string
}
const base = (id: string) => `/api/v1/studies/${encodeURIComponent(id)}/billing/reconciliations`
export const billingReconciliationApi = {
  get: (id: string, page = 1) =>
    apiClient.get<never, ApiResponse<ReconciliationOverview>>(base(id), { params: { page } }),
  csvColumns: (id: string, content_base64: string) =>
    apiClient.post<never, ApiResponse<string[]>>(`${base(id)}/csv-columns`, { content_base64 }),
  preview: (id: string, body: ReconciliationRequest) =>
    apiClient.post<never, ApiResponse<ReconciliationResult>>(`${base(id)}/preview`, body),
  save: (
    id: string,
    body: ReconciliationRequest & { request_id: string; expected_preview_hash: string },
  ) => apiClient.post<never, ApiResponse<ReconciliationRecord>>(base(id), body),
  policy: (id: string, body: { expected_revision: number; enabled: boolean; reason: string }) =>
    apiClient.put<never, ApiResponse<ReconciliationPolicy>>(`${base(id)}/policy`, body),
  detail: (id: string, record: string) =>
    apiClient.get<never, ApiResponse<ReconciliationRecord & { reviews: ReconciliationReview[] }>>(
      `${base(id)}/${encodeURIComponent(record)}`,
    ),
  review: (
    id: string,
    record: string,
    body: { expected_revision: number; action: ReviewAction; reason: string },
  ) =>
    apiClient.post<never, ApiResponse<ReconciliationRecord>>(
      `${base(id)}/${encodeURIComponent(record)}/reviews`,
      body,
    ),
}
