import { apiClient } from './client'
import type { ApiResponse } from './types'

export interface PromptTemplateResponse {
  id: string
  template_key: string
  version: string
  content: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface CreatePromptRequest {
  template_key: string
  version: string
  content: string
}

export interface UpdatePromptRequest {
  content: string
}

export interface ActivatePromptRequest {
  version: string
}

export interface DeactivatePromptRequest {
  version: string
}

export interface ABTestConfig {
  enabled: boolean
  ratio: number
}

export interface ABStatsResponse {
  enabled: boolean
  ratio: number
  total_assignments: number
  v1_count: number
  v2_count: number
}

export interface ListPromptsParams {
  template_key?: string
  active_only?: boolean
}

export const promptsApi = {
  list: (params?: ListPromptsParams) =>
    apiClient.get<never, ApiResponse<PromptTemplateResponse[]>>('/api/v1/prompts', { params }),

  create: (data: CreatePromptRequest) =>
    apiClient.post<never, ApiResponse<PromptTemplateResponse>>('/api/v1/prompts', data),

  update: (template_key: string, version: string, data: UpdatePromptRequest) =>
    apiClient.put<never, ApiResponse<PromptTemplateResponse>>(
      `/api/v1/prompts/${template_key}/${version}`,
      data,
    ),

  delete: (template_key: string, version: string) =>
    apiClient.delete<never, void>(`/api/v1/prompts/${template_key}/${version}`),

  activate: (template_key: string, data: ActivatePromptRequest) =>
    apiClient.post<never, ApiResponse<PromptTemplateResponse>>(
      `/api/v1/prompts/${template_key}/activate`,
      data,
    ),

  deactivate: (template_key: string, data: DeactivatePromptRequest) =>
    apiClient.post<never, ApiResponse<PromptTemplateResponse>>(
      `/api/v1/prompts/${template_key}/deactivate`,
      data,
    ),

  getAbStats: () =>
    apiClient.get<never, ApiResponse<ABStatsResponse>>('/api/v1/prompts/ab-stats'),

  updateAbConfig: (data: ABTestConfig) =>
    apiClient.put<never, ApiResponse<ABStatsResponse>>('/api/v1/prompts/ab-config', data),
}
