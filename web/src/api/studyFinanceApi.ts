import { apiClient } from './client'
import type { ApiResponse } from './types'

export type Currency = 'CNY' | 'USD' | 'EUR'
export type ExpenseSource = 'provider_statement' | 'payment_receipt' | 'manual_allocation'
export interface StudyBudget {
  study_id: string
  revision: number
  currency: Currency
  limit: string | null
  enforcement_enabled: boolean
  reason: string
  created_at: string
}
export interface StudyExpense {
  id: string
  study_id: string
  request_id: string
  currency: Currency
  amount: string
  incurred_on: string
  source_type: ExpenseSource
  source_reference: string
  scope_description: string
  created_at: string
  voided_at: string | null
  void_reason: string | null
}
export interface StudyFinance {
  study_id: string
  page: number
  page_size: number
  total: number
  active_count: number
  voided_count: number
  recorded_amount: string | null
  budget_difference: string | null
  admission_blocked: boolean
  budget: StudyBudget | null
  budget_history: StudyBudget[]
  items: StudyExpense[]
  read_at: string
}
export interface BudgetInput {
  expected_revision: number
  currency: Currency
  limit: string | null
  enforcement_enabled: boolean
  reason: string
}
export interface ExpenseInput {
  request_id: string
  currency: Currency
  amount: string
  incurred_on: string
  source_type: ExpenseSource
  source_reference: string
  scope_description: string
}
const base = (id: string) => `/api/v1/studies/${encodeURIComponent(id)}`
export const studyFinanceApi = {
  get: (id: string, page: number) =>
    apiClient.get<never, ApiResponse<StudyFinance>>(`${base(id)}/finance`, { params: { page } }),
  setBudget: (id: string, body: BudgetInput) =>
    apiClient.put<never, ApiResponse<StudyBudget>>(`${base(id)}/budget`, body),
  addExpense: (id: string, body: ExpenseInput) =>
    apiClient.post<never, ApiResponse<StudyExpense>>(`${base(id)}/expenses`, body),
  voidExpense: (id: string, entryId: string, reason: string) =>
    apiClient.post<never, ApiResponse<StudyExpense>>(
      `${base(id)}/expenses/${encodeURIComponent(entryId)}/void`,
      { reason },
    ),
}
