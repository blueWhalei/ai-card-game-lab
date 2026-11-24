import { apiClient } from './client'
import type { ApiResponse } from './types'

export interface BillingConfig {
  study_id: string
  revision: number
  organization_id: string
  project_id: string
  start_date: string
  limit_amount: string | null
  enforcement_enabled: boolean | number
  max_age_hours: number
  reason: string
  created_at: string
}
export interface BillingAttempt {
  id: string
  study_id: string
  revision: number
  status: 'running' | 'succeeded' | 'failed' | 'interrupted'
  trigger: 'manual' | 'scheduled'
  schedule_revision: number | null
  start_time: number
  end_time: number
  started_at: string
  finished_at: string | null
  error_code: string | null
  amount: string | null
  organization_id: string
  project_id: string
  start_date: string
  limit_amount: string | null
  enforcement_enabled: boolean | number
  max_age_hours: number
  reason: string
}
export interface BillingOverview {
  study_id: string
  provider: 'openai'
  source_url: string
  currency: 'USD'
  organization_id: string
  credential_configured: boolean
  can_sync: boolean
  config: BillingConfig | null
  snapshot: Pick<BillingAttempt, 'id' | 'start_time' | 'end_time' | 'finished_at' | 'amount'> | null
  latest_attempt: BillingAttempt | null
  snapshot_valid_until: string | null
  state: 'unconfigured' | 'missing' | 'failed' | 'interrupted' | 'stale' | 'reached' | 'below'
  admission_blocked: boolean
  cost_admission_blocked: boolean
  reconciliation_blocked: boolean
  history: BillingAttempt[]
  config_history: BillingConfig[]
  read_at: string
}
export interface BillingInput {
  expected_revision: number
  project_id: string
  start_date: string
  limit: string | null
  enforcement_enabled: boolean
  max_age_hours: number
  reason: string
}
export interface BillingSchedulePlan {
  study_id: string
  revision: number
  config_revision: number
  enabled: boolean | number
  interval_minutes: number
  reason: string
  created_at: string
  next_due_at: string | null
  last_attempt_id: string | null
  consecutive_failures: number
  error_code: string | null
  updated_at: string
}
export interface BillingScheduleOverview {
  study_id: string
  config: BillingConfig | null
  plan: BillingSchedulePlan | null
  state:
    | 'not_configured'
    | 'paused'
    | 'scope_changed'
    | 'attention'
    | 'retry_wait'
    | 'due'
    | 'scheduled'
    | 'running'
    | 'recovering'
  checked_at: string | null
  worker_enabled: boolean
  worker_recent: boolean
  history: (Pick<
    BillingSchedulePlan,
    | 'study_id'
    | 'revision'
    | 'config_revision'
    | 'enabled'
    | 'interval_minutes'
    | 'reason'
    | 'created_at'
  > &
    Pick<BillingConfig, 'organization_id' | 'project_id' | 'start_date'>)[]
  read_at: string
}
export interface BillingScheduleInput {
  expected_revision: number
  expected_config_revision: number
  enabled: boolean
  interval_minutes: number
  reason: string
}
export interface BillingEvidence extends BillingAttempt {
  source_url: string
  currency: 'USD'
  page: number
  page_size: number
  total: number
  items: {
    start_time: number
    end_time: number
    amount: string
    currency: 'USD'
    project_id: string
    line_item: string | null
  }[]
}
const base = (id: string) => `/api/v1/studies/${encodeURIComponent(id)}/billing`
export const studyBillingApi = {
  schedule: (id: string) =>
    apiClient.get<never, ApiResponse<BillingScheduleOverview>>(`${base(id)}/schedule`),
  setSchedule: (id: string, body: BillingScheduleInput) =>
    apiClient.put<never, ApiResponse<BillingSchedulePlan>>(`${base(id)}/schedule`, body),
  get: (id: string) => apiClient.get<never, ApiResponse<BillingOverview>>(base(id)),
  configure: (id: string, body: BillingInput) =>
    apiClient.put<never, ApiResponse<BillingConfig>>(`${base(id)}/config`, body),
  sync: (id: string, expected_revision: number) =>
    apiClient.post<never, ApiResponse<BillingOverview>>(
      `${base(id)}/sync`,
      { expected_revision },
      { timeout: 150000 },
    ),
  evidence: (id: string, attempt: string, page: number) =>
    apiClient.get<never, ApiResponse<BillingEvidence>>(
      `${base(id)}/attempts/${encodeURIComponent(attempt)}`,
      { params: { page } },
    ),
}
