<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import UiButton from '@/components/ui/Button.vue'
import UiDialog from '@/components/ui/Dialog.vue'
import UiInput from '@/components/ui/Input.vue'
import UiInputNumber from '@/components/ui/InputNumber.vue'
import UiSelect from '@/components/ui/Select.vue'
import type { SelectOption } from '@/components/ui/Select.vue'
import { controlSlotLabels } from '@/utils/experimentWorkbench'

const { t } = useI18n()

defineProps<{
  challengerOptions: SelectOption[]
  baselineOptions: SelectOption[]
  canSubmit: boolean
  loading: boolean
}>()

const emit = defineEmits<{
  submit: []
}>()

const open = defineModel<boolean>('open', { required: true })
const name = defineModel<string>('name', { required: true })
const target = defineModel<number>('target', { required: true })
const playerIds = defineModel<string[]>('playerIds', { required: true })

const slotLabels = computed(() => controlSlotLabels(playerIds.value.length))

function setPlayerAt(index: number, value: string): void {
  const current = playerIds.value[index] ?? ''
  // Reka Select emits empty on mount before items attach; keep prefilled seats.
  if (!value && current) return
  if (current === value) return
  const next = [...playerIds.value]
  next[index] = value
  playerIds.value = next
}
</script>

<template>
  <UiDialog
    :open="open"
    :title="t('control.title')"
    :description="t('control.description', { n: Math.max(playerIds.length - 1, 0) })"
    @update:open="open = $event"
  >
    <div class="space-y-4">
      <label class="block space-y-1.5">
        <span class="text-sm font-medium text-ink-text">{{ t('common.name') }}</span>
        <UiInput v-model="name" :placeholder="t('control.namePlaceholder')" />
      </label>
      <label
        v-for="(label, index) in slotLabels"
        :key="`${label}-${index}`"
        class="block space-y-1.5"
      >
        <span class="text-sm font-medium text-ink-text">{{ label }}</span>
        <UiSelect
          :model-value="playerIds[index] ?? ''"
          :options="index === 0 ? challengerOptions : baselineOptions"
          :placeholder="index === 0 ? t('control.challengerPlaceholder') : t('control.baselinePlaceholder')"
          class="w-full"
          @update:model-value="setPlayerAt(index, $event)"
        />
      </label>
      <label class="block space-y-1.5">
        <span class="text-sm font-medium text-ink-text">{{ t('experiment.targetGames') }}</span>
        <UiInputNumber v-model="target" :min="1" :max="50" />
      </label>
      <p v-if="challengerOptions.length === 0" class="text-xs text-ink-warning">
        {{ t('control.noPlayers') }}
      </p>
    </div>
    <template #footer>
      <UiButton variant="secondary" @click="open = false">{{ t('common.cancel') }}</UiButton>
      <UiButton :disabled="!canSubmit" :loading="loading" @click="emit('submit')">
        {{ t('experiment.createAndOpen') }}
      </UiButton>
    </template>
  </UiDialog>
</template>
