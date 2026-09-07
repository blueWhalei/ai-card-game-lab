<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { toast } from '@/components/ui/toast'
import { confirmDialog } from '@/components/ui/confirm'
import { useDataStore } from '@/stores/useDataStore'
import type { DatasetItem } from '@/api/dataApi'
import { showApiError } from '@/utils/error'
import { formatDateTime } from '@/utils/format'
import UiButton from '@/components/ui/Button.vue'
import UiSpinner from '@/components/ui/Spinner.vue'
import UiTable from '@/components/ui/Table.vue'
import type { TableColumn } from '@/components/ui/Table.vue'

const { t } = useI18n()
const store = useDataStore()

const columns = computed(
  (): TableColumn<DatasetItem>[] => [
    { key: 'name', label: t('data.colName') },
    { key: 'game_type', label: t('data.colGame') },
    { key: 'sample_count', label: t('data.colSamples') },
    { key: 'created_at', label: t('common.createdAt'), render: (row) => formatDateTime(row.created_at) },
  ],
)

onMounted(async () => {
  try {
    await store.fetchDatasetsOnce()
  } catch (e: unknown) {
    showApiError(e, t('data.loadDatasetsFailed'))
  }
})

async function handleDelete(id: string) {
  const ok = await confirmDialog({
    title: t('data.deleteDatasetTitle'),
    message: t('data.deleteDatasetMsg'),
    danger: true,
  })
  if (!ok) return
  try {
    await store.deleteDataset(id)
    toast.success(t('error.deleted'))
  } catch (e: unknown) {
    showApiError(e, t('error.deleteFailed'))
  }
}
</script>

<template>
  <div class="relative ink-card">
    <UiSpinner v-if="store.datasetsLoading" overlay :label="t('common.loading')" />
    <div class="mb-4 space-y-1">
      <h3 class="text-base font-semibold text-ink-text">{{ t('data.datasets') }}</h3>
      <p class="text-caption text-ink-text-muted">{{ t('data.datasetsFromDecisions') }}</p>
    </div>

    <UiTable :columns="columns" :rows="store.datasets" row-key="id">
      <template #actions="{ row }">
        <UiButton size="sm" variant="danger" @click="handleDelete(row.id)">{{ t('common.delete') }}</UiButton>
      </template>
    </UiTable>
  </div>
</template>
