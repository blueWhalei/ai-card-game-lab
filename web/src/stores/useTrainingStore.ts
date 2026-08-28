import { ref } from 'vue'
import { defineStore } from 'pinia'
import { trainingApi } from '@/api/trainingApi'
import type { TrainingTask, ModelItem, CreateTaskRequest } from '@/api/trainingApi'

export const useTrainingStore = defineStore('training', () => {
  const tasks = ref<TrainingTask[]>([])
  const total = ref(0)
  const models = ref<ModelItem[]>([])
  const isLoading = ref(false)
  const currentTask = ref<TrainingTask | null>(null)

  async function fetchTasks(params?: { page?: number; status?: string }): Promise<void> {
    isLoading.value = true
    try {
      const res = await trainingApi.listTasks(params)
      tasks.value = res.data.items
      total.value = res.data.total
    } finally {
      isLoading.value = false
    }
  }

  async function fetchTask(id: string): Promise<void> {
    const res = await trainingApi.getTask(id)
    currentTask.value = res.data
    // Also update in list if present
    const idx = tasks.value.findIndex((t) => t.id === id)
    if (idx >= 0) {
      tasks.value = [...tasks.value.slice(0, idx), res.data, ...tasks.value.slice(idx + 1)]
    }
  }

  async function createTask(data: CreateTaskRequest): Promise<TrainingTask> {
    const res = await trainingApi.createTask(data)
    await fetchTasks()
    return res.data
  }

  async function deleteTask(id: string): Promise<void> {
    await trainingApi.deleteTask(id)
    tasks.value = tasks.value.filter((t) => t.id !== id)
    total.value = Math.max(0, total.value - 1)
  }

  async function cancelTask(id: string): Promise<TrainingTask> {
    const res = await trainingApi.cancelTask(id)
    const updated = res.data
    const idx = tasks.value.findIndex((t) => t.id === id)
    if (idx >= 0) {
      tasks.value = [...tasks.value.slice(0, idx), updated, ...tasks.value.slice(idx + 1)]
    }
    return updated
  }

  async function fetchModels(): Promise<void> {
    isLoading.value = true
    try {
      const res = await trainingApi.listModels()
      models.value = res.data
    } finally {
      isLoading.value = false
    }
  }

  async function deleteModel(id: string): Promise<void> {
    await trainingApi.deleteModel(id)
    models.value = models.value.filter((m) => m.id !== id)
  }

  async function exportModel(
    id: string,
    data?: { ollama_tag?: string; merge?: boolean; try_create?: boolean },
  ): Promise<Record<string, unknown>> {
    const res = await trainingApi.exportModel(id, data)
    return res.data
  }

  async function verifyModel(
    id: string,
    data?: { ollama_tag?: string; run_game?: boolean; player_ids?: string[] },
  ): Promise<Record<string, unknown>> {
    const res = await trainingApi.verifyModel(id, data)
    return res.data
  }

  return {
    tasks,
    total,
    models,
    isLoading,
    currentTask,
    fetchTasks,
    fetchTask,
    createTask,
    deleteTask,
    cancelTask,
    fetchModels,
    deleteModel,
    exportModel,
    verifyModel,
  }
})
