<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { ModelItem } from '@/api/trainingApi'
import UiButton from '@/components/ui/Button.vue'
import UiCheckbox from '@/components/ui/Checkbox.vue'
import UiEmpty from '@/components/ui/Empty.vue'
import UiTable from '@/components/ui/Table.vue'
import { formatDateTime } from '@/utils/format'

defineProps<{
  columns: { key: string; label: string; class?: string }[]
  rows: Record<string, unknown>[]
  empty: boolean
  registerAfterPush: boolean
  pushingModelId: string | null
  isLoraModel: (model: ModelItem) => boolean
}>()

function asModel(row: Record<string, unknown>): ModelItem {
  return row as unknown as ModelItem
}

const { t } = useI18n()

const emit = defineEmits<{
  'update:registerAfterPush': [value: boolean]
  push: [model: ModelItem]
  export: [id: string]
  register: [model: ModelItem]
  verify: [id: string, runGame: boolean]
  delete: [id: string]
}>()
</script>

<template>
  <div class="space-y-3">
    <UiEmpty v-if="empty" :title="t('training.noModels')" />
    <template v-else>
      <UiCheckbox
        :model-value="registerAfterPush"
        :label="t('training.pushAndAdd')"
        @update:model-value="emit('update:registerAfterPush', Boolean($event))"
      />
      <UiTable :columns="columns" :rows="rows" row-key="id">
        <template #cell-base_model="{ row }">
          <span class="font-mono text-xs">{{ row.base_model }}</span>
        </template>
        <template #cell-model_path="{ row }">
          <span class="block max-w-xs truncate font-mono text-xs" :title="String(row.model_path || '')">
            {{ row.model_path || t('common.dash') }}
          </span>
        </template>
        <template #cell-created_at="{ row }">
          {{ formatDateTime(String(row.created_at)) }}
        </template>
        <template #actions="{ row }">
          <div class="flex max-w-md flex-wrap gap-1">
            <UiButton
              variant="primary"
              size="sm"
              :disabled="!isLoraModel(asModel(row)) || pushingModelId === row.id"
              @click="emit('push', asModel(row))"
            >
              {{ pushingModelId === row.id ? t('training.pushing') : t('training.pushOllama') }}
            </UiButton>
            <UiButton variant="secondary" size="sm" @click="emit('export', String(row.id))">
              {{ t('training.export') }}
            </UiButton>
            <UiButton
              variant="secondary"
              size="sm"
              :disabled="!isLoraModel(asModel(row))"
              @click="emit('register', asModel(row))"
            >
              {{ t('training.addAsPlayer') }}
            </UiButton>
            <UiButton variant="secondary" size="sm" @click="emit('verify', String(row.id), false)">
              {{ t('training.verify') }}
            </UiButton>
            <UiButton variant="secondary" size="sm" @click="emit('verify', String(row.id), true)">
              {{ t('training.testGame') }}
            </UiButton>
            <UiButton
              variant="ghost"
              size="sm"
              class="text-ink-danger"
              @click="emit('delete', String(row.id))"
            >
              {{ t('common.delete') }}
            </UiButton>
          </div>
        </template>
      </UiTable>
    </template>
  </div>
</template>
