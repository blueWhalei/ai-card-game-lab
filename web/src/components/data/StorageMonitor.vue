<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
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

const { t } = useI18n()
const storage = ref<StorageInfo | null>(null)
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    const res = await apiClient.get<never, ApiResponse<StorageInfo>>('/api/v1/system/storage')
    storage.value = res.data
  } catch (e: unknown) {
    showApiError(e, t('data.storageFailed'))
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="relative ink-card min-h-[120px]">
    <UiSpinner v-if="loading" overlay :label="t('common.loading')" />
    <h3 class="mb-4 text-base font-semibold text-ink-text">{{ t('data.storage') }}</h3>
    <div v-if="storage" class="grid grid-cols-1 gap-4 md:grid-cols-3">
      <div class="rounded-ink-md bg-ink-surface-muted p-4">
        <div class="text-xl font-semibold text-ink-text">
          {{ formatBytes(storage.db_size_bytes) }}
        </div>
        <div class="mt-1 text-xs text-ink-text-muted">{{ t('data.sqlite') }}</div>
      </div>
      <div class="rounded-ink-md bg-ink-surface-muted p-4">
        <div class="text-xl font-semibold text-ink-text">
          {{ formatBytes(storage.data_size_bytes) }}
        </div>
        <div class="mt-1 text-xs text-ink-text-muted">{{ t('data.dataDirSize') }}</div>
      </div>
      <div class="rounded-ink-md bg-ink-surface-muted p-4">
        <div class="text-xl font-semibold text-ink-text">{{ storage.jsonl_file_count }}</div>
        <div class="mt-1 text-xs text-ink-text-muted">{{ t('data.jsonlCount') }}</div>
      </div>
    </div>
    <div v-else-if="!loading" class="py-8 text-center text-ink-text-muted">{{ t('data.noStorage') }}</div>
  </div>
</template>
