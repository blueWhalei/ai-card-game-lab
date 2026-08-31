import { ref } from 'vue'
import { defineStore } from 'pinia'
import { dataApi } from '@/api/dataApi'
import type { DataStats, DatasetItem, CreateDatasetRequest } from '@/api/dataApi'

export const useDataStore = defineStore('data', () => {
  const stats = ref<DataStats | null>(null)
  const datasets = ref<DatasetItem[]>([])

  // 分开的 loading 状态
  const statsLoading = ref(false)
  const datasetsLoading = ref(false)

  // 加载标记，避免重复请求
  const statsLoaded = ref(false)
  const statsLoadedKey = ref<string | null>(null)
  const datasetsLoaded = ref(false)

  async function fetchStats(experimentId?: string): Promise<void> {
    statsLoading.value = true
    try {
      const res = await dataApi.stats(experimentId ? { experiment_id: experimentId } : undefined)
      stats.value = res.data
      statsLoaded.value = true
      statsLoadedKey.value = experimentId ?? ''
    } finally {
      statsLoading.value = false
    }
  }

  async function fetchDatasets(): Promise<void> {
    datasetsLoading.value = true
    try {
      const res = await dataApi.listDatasets()
      datasets.value = res.data
      datasetsLoaded.value = true
    } finally {
      datasetsLoading.value = false
    }
  }

  async function fetchStatsOnce(experimentId?: string): Promise<void> {
    const key = experimentId ?? ''
    if (statsLoaded.value && statsLoadedKey.value === key) return
    await fetchStats(experimentId)
  }

  async function fetchDatasetsOnce(): Promise<void> {
    if (datasetsLoaded.value) return
    await fetchDatasets()
  }

  async function createDataset(request: CreateDatasetRequest): Promise<DatasetItem> {
    const res = await dataApi.createDataset(request)
    await fetchDatasets()
    return res.data
  }

  async function deleteDataset(id: string): Promise<void> {
    await dataApi.deleteDataset(id)
    await fetchDatasets()
  }

  return {
    stats,
    datasets,
    statsLoading,
    datasetsLoading,
    fetchStats,
    fetchStatsOnce,
    fetchDatasets,
    fetchDatasetsOnce,
    createDataset,
    deleteDataset,
  }
})
