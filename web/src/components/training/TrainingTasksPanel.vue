<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import UiBadge from '@/components/ui/Badge.vue'
import UiButton from '@/components/ui/Button.vue'
import UiProgress from '@/components/ui/Progress.vue'
import UiSpinner from '@/components/ui/Spinner.vue'
import UiTable from '@/components/ui/Table.vue'
import { TRAINING_STATUS_MAP } from '@/utils/constants'
import { formatDateTime } from '@/utils/format'

defineProps<{
  columns: { key: string; label: string; class?: string }[]
  rows: Record<string, unknown>[]
  loading: boolean
  statusVariant: (status: string) => 'muted' | 'success' | 'warning' | 'danger' | 'default'
  formatProgress: (progress: number) => string
}>()

const { t } = useI18n()

const emit = defineEmits<{
  delete: [id: string]
}>()
</script>

<template>
  <div class="relative">
    <UiSpinner v-if="loading" overlay :label="t('common.loading')" />
    <UiTable :columns="columns" :rows="rows" row-key="id">
      <template #cell-base_model="{ row }">
        <span class="font-mono text-xs">{{ row.base_model }}</span>
      </template>
      <template #cell-status="{ row }">
        <div class="flex flex-wrap items-center gap-1">
          <UiBadge :variant="statusVariant(String(row.status))">
            {{ TRAINING_STATUS_MAP[String(row.status)]?.label || row.status }}
          </UiBadge>
          <UiBadge
            v-if="row.status === 'completed' && !String(row.model_path || '').endsWith('model.bin')"
            variant="success"
          >
            LoRA
          </UiBadge>
        </div>
      </template>
      <template #cell-progress="{ row }">
        <UiProgress
          v-if="['exporting', 'training'].includes(String(row.status))"
          :value="Math.round(Number(row.progress) * 100)"
          class="mt-1"
        />
        <span v-else-if="row.status === 'completed'" class="text-sm text-ink-success">
          {{ formatProgress(Number(row.progress)) }}
        </span>
        <span v-else class="text-sm text-ink-text-muted">-</span>
      </template>
      <template #cell-created_at="{ row }">
        {{ formatDateTime(String(row.created_at)) }}
      </template>
      <template #actions="{ row }">
        <UiButton
          variant="ghost"
          size="sm"
          class="text-ink-danger"
          @click="emit('delete', String(row.id))"
        >
          {{ t('common.delete') }}
        </UiButton>
      </template>
    </UiTable>
  </div>
</template>
