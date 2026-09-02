<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Icon } from '@iconify/vue'
import type { ModelItem } from '@/api/trainingApi'
import UiButton from '@/components/ui/Button.vue'
import UiCheckbox from '@/components/ui/Checkbox.vue'
import UiDropdownMenu from '@/components/ui/DropdownMenu.vue'
import type { DropdownMenuItemDef } from '@/components/ui/DropdownMenu.vue'
import UiEmpty from '@/components/ui/Empty.vue'
import UiTable from '@/components/ui/Table.vue'
import { formatDateTime } from '@/utils/format'

export type ModelBusyAction = 'push' | 'export' | 'verify' | 'verify_game' | 'register' | 'delete'

export type ModelBusyState = {
  id: string
  action: ModelBusyAction
}

const props = defineProps<{
  columns: { key: string; label: string; class?: string }[]
  rows: Record<string, unknown>[]
  empty: boolean
  registerAfterPush: boolean
  modelBusy: ModelBusyState | null
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

function rowBusy(row: Record<string, unknown>): ModelBusyState | null {
  if (!props.modelBusy || props.modelBusy.id !== String(row.id)) return null
  return props.modelBusy
}

function menuItems(row: Record<string, unknown>): DropdownMenuItemDef[] {
  const model = asModel(row)
  const busy = rowBusy(row) != null
  const lora = props.isLoraModel(model)
  return [
    { id: 'export', label: t('training.export'), disabled: busy },
    { id: 'register', label: t('training.addAsPlayer'), disabled: !lora || busy },
    { id: 'verify', label: t('training.verify'), disabled: busy },
    { id: 'testGame', label: t('training.testGame'), disabled: busy },
    { id: 'delete', label: t('common.delete'), danger: true, disabled: busy },
  ]
}

function onMenuSelect(row: Record<string, unknown>, id: string): void {
  const model = asModel(row)
  switch (id) {
    case 'export':
      emit('export', model.id)
      break
    case 'register':
      emit('register', model)
      break
    case 'verify':
      emit('verify', model.id, false)
      break
    case 'testGame':
      emit('verify', model.id, true)
      break
    case 'delete':
      emit('delete', model.id)
      break
  }
}

const anyBusy = computed(() => props.modelBusy != null)

function modelPathLabel(path: unknown): string {
  const raw = String(path ?? '').trim()
  if (!raw) return t('common.dash')
  const parts = raw.replace(/\\/g, '/').split('/').filter(Boolean)
  const tail = parts[parts.length - 1] ?? raw
  return tail.length > 28 ? `…${tail.slice(-27)}` : tail
}
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
      <UiTable
        :columns="columns"
        :rows="rows"
        row-key="id"
        fixed-layout
        actions-column-class="w-[24%] min-w-[10.5rem]"
      >
        <template #cell-name="{ row }">
          <span class="block truncate font-medium" :title="String(row.name || '')">
            {{ row.name }}
          </span>
        </template>
        <template #cell-base_model="{ row }">
          <span class="block truncate font-mono text-xs" :title="String(row.base_model || '')">
            {{ row.base_model }}
          </span>
        </template>
        <template #cell-model_path="{ row }">
          <span
            class="block truncate font-mono text-xs text-ink-text-secondary"
            :title="String(row.model_path || '')"
          >
            {{ modelPathLabel(row.model_path) }}
          </span>
        </template>
        <template #cell-created_at="{ row }">
          {{ formatDateTime(String(row.created_at)) }}
        </template>
        <template #actions="{ row }">
          <div class="flex min-w-[10.5rem] items-center gap-1.5 whitespace-normal">
            <UiButton
              variant="primary"
              size="sm"
              class="shrink-0"
              :disabled="!isLoraModel(asModel(row)) || anyBusy"
              :loading="rowBusy(row)?.action === 'push'"
              @click="emit('push', asModel(row))"
            >
              {{ t('training.pushOllama') }}
            </UiButton>
            <UiDropdownMenu
              :items="menuItems(row)"
              @select="onMenuSelect(row, $event)"
            >
              <UiButton
                size="sm"
                variant="secondary"
                type="button"
                class="shrink-0 px-2"
                :disabled="anyBusy"
                :aria-label="t('training.moreActions')"
              >
                <Icon icon="lucide:more-horizontal" class="h-4 w-4" />
              </UiButton>
            </UiDropdownMenu>
          </div>
        </template>
      </UiTable>
    </template>
  </div>
</template>
