import { apiClient } from './client'
import type { ApiResponse, PaginatedData } from './types'

export interface TrainingConfig {
  learning_rate: number
  batch_size: number
  num_epochs: number
  output_format: string
  lora_r?: number
  lora_alpha?: number
  lora_dropout?: number
  max_seq_length?: number
  max_steps?: number
  gradient_accumulation_steps?: number
  qlora?: boolean
}

export interface CreateTaskRequest {
  name: string
  dataset_id: string
  training_type?: string
  base_model?: string
  config?: Partial<TrainingConfig>
  experiment_id?: string
}

export interface TrainingTask {
  id: string
  name: string
  dataset_id: string
  base_model: string
  training_type: string
  config: TrainingConfig
  status: string
  progress: number
  result: Record<string, unknown> | null
  model_path: string | null
  created_at: string
  finished_at: string | null
  experiment_id?: string | null
}

export interface ModelItem {
  id: string
  name: string
  base_model: string
  training_type: string
  model_path: string | null
  created_at: string
}

export const trainingApi = {
  listTasks: (params?: Record<string, string | number>) =>
    apiClient.get<never, ApiResponse<PaginatedData<TrainingTask>>>('/api/v1/training/tasks', {
      params,
    }),

  createTask: (data: CreateTaskRequest) =>
    apiClient.post<never, ApiResponse<TrainingTask>>('/api/v1/training/tasks', data),

  getTask: (id: string) =>
    apiClient.get<never, ApiResponse<TrainingTask>>(`/api/v1/training/tasks/${id}`),

  deleteTask: (id: string) =>
    apiClient.delete<never, ApiResponse<Record<string, string>>>(
      `/api/v1/training/tasks/${id}`,
    ),

  cancelTask: (id: string) =>
    apiClient.post<never, ApiResponse<TrainingTask>>(
      `/api/v1/training/tasks/${id}/cancel`,
    ),

  listModels: () => apiClient.get<never, ApiResponse<ModelItem[]>>('/api/v1/models'),

  deleteModel: (id: string) =>
    apiClient.delete<never, ApiResponse<Record<string, string>>>(`/api/v1/models/${id}`),

  exportModel: (
    id: string,
    data?: { ollama_tag?: string; merge?: boolean; try_create?: boolean },
  ) =>
    apiClient.post<never, ApiResponse<Record<string, unknown>>>(
      `/api/v1/models/${id}/export`,
      data ?? {},
    ),

  pushToOllama: (
    id: string,
    data?: { ollama_tag?: string; force_convert?: boolean },
  ) =>
    apiClient.post<never, ApiResponse<Record<string, unknown>>>(
      `/api/v1/models/${id}/push-ollama`,
      data ?? {},
    ),

  verifyModel: (
    id: string,
    data?: { ollama_tag?: string; run_game?: boolean; player_ids?: string[] },
  ) =>
    apiClient.post<never, ApiResponse<Record<string, unknown>>>(
      `/api/v1/models/${id}/verify`,
      data ?? {},
    ),
}
