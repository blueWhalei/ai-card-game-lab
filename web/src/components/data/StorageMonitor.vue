<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { apiClient } from '@/api/client'
import type { ApiResponse } from '@/api/types'
import { formatBytes } from '@/utils/format'
import { showApiError } from '@/utils/error'
import UiSpinner from '@/components/ui/Spinner.vue'

interface StorageInfo {
  db_size_bytes: number
  data_size_bytes: number
  jsonl_file_count: number
}

const storage = ref<StorageInfo | null>(null)
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    const res = await apiClient.get<never, ApiResponse<StorageInfo>>('/api/v1/system/storage')
    storage.value = res.data
  } catch (e: unknown) {
    showApiError(e, '加载存储信息失败')
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="relative ink-card min-h-[120px]">
    <UiSpinner v-if="loading" overlay label="加载中…" />
    <h3 class="mb-4 text-base font-semibold text-ink-text">存储空间</h3>
    <div v-if="storage" class="grid grid-cols-1 gap-4 md:grid-cols-3">
      <div class="rounded-ink-md bg-ink-surface-muted p-4">
        <div class="text-xl font-semibold text-ink-text">
          {{ formatBytes(storage.db_size_bytes) }}
        </div>
        <div class="mt-1 text-xs text-ink-text-muted">SQLite 数据库</div>
      </div>
      <div class="rounded-ink-md bg-ink-surface-muted p-4">
        <div class="text-xl font-semibold text-ink-text">
          {{ formatBytes(storage.data_size_bytes) }}
        </div>
        <div class="mt-1 text-xs text-ink-text-muted">数据目录总大小</div>
      </div>
      <div class="rounded-ink-md bg-ink-surface-muted p-4">
        <div class="text-xl font-semibold text-ink-text">{{ storage.jsonl_file_count }}</div>
        <div class="mt-1 text-xs text-ink-text-muted">JSONL 文件数</div>
      </div>
    </div>
    <div v-else-if="!loading" class="py-8 text-center text-ink-text-muted">暂无存储信息</div>
  </div>
</template>
