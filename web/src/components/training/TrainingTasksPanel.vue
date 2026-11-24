<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import UiBadge from '@/components/ui/Badge.vue'
import UiButton from '@/components/ui/Button.vue'
import UiProgress from '@/components/ui/Progress.vue'
import UiSpinner from '@/components/ui/Spinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { useRoute, useRouter } from 'vue-router'
import UiTable from '@/components/ui/Table.vue'
import { TRAINING_STATUS_MAP } from '@/utils/constants'
import { formatDateTime } from '@/utils/format'
import { recordedProgress, trainingError } from '@/utils/trainingRecords'

defineProps<{
  columns: { key: string; label: string; class?: string }[]
  rows: Record<string, unknown>[]
  loading: boolean
  canCreate: boolean
  statusVariant: (status: string) => 'muted' | 'success' | 'warning' | 'danger' | 'default'
  formatProgress: (progress: unknown) => string
}>()

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const emit = defineEmits<{
  delete: [id: string]
}>()
</script>

<template>
  <div class="relative">
    <UiSpinner v-if="loading" overlay :label="t('common.loading')" />
    <EmptyState
      v-if="!loading && rows.length === 0"
      :title="t('training.emptyTasksTitle')"
      :description="t(canCreate ? 'training.emptyTasksHint' : 'training.emptyTasksBlockedHint')"
    >
      <template #action>
        <UiButton
          variant="secondary"
          @click="
            router.push({
              path: '/pipeline/decisions',
              query: { experiment_id: route.query.experiment_id, train_usable: 'true' },
            })
          "
        >
          {{ t('training.reviewDecisions') }}
        </UiButton>
      </template>
    </EmptyState>
    <UiTable v-else :columns="columns" :rows="rows" row-key="id">
      <template #cell-base_model="{ row }">
        <span class="font-mono text-xs">{{ row.base_model }}</span>
      </template>
      <template #cell-status="{ row }">
        <div class="flex flex-wrap items-center gap-1">
          <UiBadge :variant="statusVariant(String(row.status))">
            {{ TRAINING_STATUS_MAP[String(row.status)]?.label || row.status }}
          </UiBadge>
          <UiBadge
            v-if="
              row.status === 'completed' &&
              row.model_path &&
              !String(row.model_path).endsWith('model.bin')
            "
            variant="success"
          >
            LoRA
          </UiBadge>
        </div>
      </template>
      <template #cell-progress="{ row }">
        <span v-if="recordedProgress(row.progress) === null" class="text-caption">{{
          t(row.progress_state === 'invalid' ? 'operations.invalidProgress' : 'operations.missing')
        }}</span>
        <UiProgress
          v-else-if="['exporting', 'training'].includes(String(row.status))"
          :value="recordedProgress(row.progress)!"
          class="mt-1"
        />
        <span v-else-if="row.status === 'completed'" class="text-sm text-ink-success">
          {{ formatProgress(row.progress) }}
        </span>
        <div v-else-if="row.status === 'failed'" class="max-w-xs space-y-0.5">
          <span class="text-sm text-ink-danger">{{ t('training.status.failed') }}</span>
        </div>
        <span v-else class="text-sm text-ink-text-muted">-</span>
        <details v-if="trainingError(row.result)" class="mt-ink-2 max-w-xs">
          <summary class="cursor-pointer text-caption text-ink-primary">
            {{ t('operations.recordedError') }}
          </summary>
          <p class="whitespace-pre-wrap break-words text-caption">
            {{ trainingError(row.result) }}
          </p>
        </details>
        <p v-else-if="row.status === 'failed'" class="max-w-xs text-caption">
          {{ t('operations.noRecordedError') }}
        </p>
        <p v-if="row.result_state === 'invalid'" class="max-w-xs text-caption">
          {{ t('operations.invalidResult') }}
        </p>
        <p v-if="row.config_state === 'invalid'" class="max-w-xs text-caption">
          {{ t('operations.invalidConfig') }}
        </p>
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
