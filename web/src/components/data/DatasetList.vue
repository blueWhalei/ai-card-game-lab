<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { toast } from '@/components/ui/toast'
import { confirmDialog } from '@/components/ui/confirm'
import { useDataStore } from '@/stores/useDataStore'
import type { CreateDatasetRequest, DatasetItem } from '@/api/dataApi'
import { showApiError } from '@/utils/error'
import { formatDateTime } from '@/utils/format'
import { gameTypeLabel } from '@/utils/constants'
import UiButton from '@/components/ui/Button.vue'
import UiDialog from '@/components/ui/Dialog.vue'
import UiInput from '@/components/ui/Input.vue'
import UiSelect from '@/components/ui/Select.vue'
import UiSpinner from '@/components/ui/Spinner.vue'
import UiTable from '@/components/ui/Table.vue'
import type { TableColumn } from '@/components/ui/Table.vue'

const { t } = useI18n()
const store = useDataStore()
const showCreate = ref(false)
const form = ref<CreateDatasetRequest>({
  name: '',
  game_type: 'doudizhu',
  filters: {},
})

const columns = computed(
  (): TableColumn<DatasetItem>[] => [
    { key: 'name', label: t('data.colName') },
    { key: 'game_type', label: t('data.colGame') },
    { key: 'sample_count', label: t('data.colSamples') },
    { key: 'created_at', label: t('common.createdAt'), render: (row) => formatDateTime(row.created_at) },
  ],
)

const gameTypeOptions = computed(() => [{ label: gameTypeLabel('doudizhu'), value: 'doudizhu' }])

onMounted(async () => {
  try {
    await store.fetchDatasetsOnce()
  } catch (e: unknown) {
    showApiError(e, t('data.loadDatasetsFailed'))
  }
})

async function handleCreate() {
  if (!form.value.name.trim()) {
    toast.warning(t('data.needDatasetName'))
    return
  }
  try {
    await store.createDataset({
      ...form.value,
      name: form.value.name.trim(),
    })
    toast.success(t('data.datasetCreated'))
    showCreate.value = false
    form.value = { name: '', game_type: 'doudizhu', filters: {} }
  } catch (e: unknown) {
    showApiError(e, t('error.createFailed'))
  }
}

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
    <UiSpinner v-if="store.datasetsLoading" overlay />
    <div class="mb-4 flex items-center justify-between">
      <h3 class="text-base font-semibold text-ink-text">{{ t('data.datasets') }}</h3>
      <UiButton @click="showCreate = true">{{ t('data.createDataset') }}</UiButton>
    </div>

    <UiTable :columns="columns" :rows="store.datasets" row-key="id">
      <template #actions="{ row }">
        <UiButton size="sm" variant="danger" @click="handleDelete(row.id)">{{ t('common.delete') }}</UiButton>
      </template>
    </UiTable>

    <UiDialog
      :open="showCreate"
      :title="t('data.createDataset')"
      @update:open="(v) => (showCreate = v)"
    >
      <div class="space-y-4">
        <label class="block space-y-1">
          <span class="ink-label">{{ t('data.colName') }}</span>
          <UiInput v-model="form.name" :placeholder="t('data.namePh')" />
        </label>
        <label class="block space-y-1">
          <span class="ink-label">{{ t('data.gameType') }}</span>
          <UiSelect v-model="form.game_type" :options="gameTypeOptions" />
        </label>
      </div>
      <template #footer>
        <UiButton variant="secondary" @click="showCreate = false">{{ t('common.cancel') }}</UiButton>
        <UiButton @click="handleCreate">{{ t('common.create') }}</UiButton>
      </template>
    </UiDialog>
  </div>
</template>
