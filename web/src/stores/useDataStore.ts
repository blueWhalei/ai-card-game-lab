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
  const datasetsLoaded = ref(false)

  async function fetchStats(): Promise<void> {
    statsLoading.value = true
    try {
      const res = await dataApi.stats()
      stats.value = res.data
      statsLoaded.value = true
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

  async function fetchStatsOnce(): Promise<void> {
    if (statsLoaded.value) return
    await fetchStats()
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
