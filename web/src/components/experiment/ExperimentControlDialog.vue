<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import UiButton from '@/components/ui/Button.vue'
import UiCheckbox from '@/components/ui/Checkbox.vue'
import UiDialog from '@/components/ui/Dialog.vue'
import UiInput from '@/components/ui/Input.vue'
import UiInputNumber from '@/components/ui/InputNumber.vue'
import UiSelect from '@/components/ui/Select.vue'
import type { SelectOption } from '@/components/ui/Select.vue'
import { controlSlotLabels } from '@/utils/experimentWorkbench'

const { t } = useI18n()

const props = defineProps<{
  challengerOptions: SelectOption[]
  baselineOptions: SelectOption[]
  canSubmit: boolean
  loading: boolean
  protocolSummaryBits: string[]
  sourceExperimentLabel: string
  seedCount: number
}>()

const emit = defineEmits<{
  submit: []
}>()

const open = defineModel<boolean>('open', { required: true })
const name = defineModel<string>('name', { required: true })
const target = defineModel<number>('target', { required: true })
const playerIds = defineModel<string[]>('playerIds', { required: true })
const pairDeals = defineModel<boolean>('pairDeals', { default: true })
const openCollectAfter = defineModel<boolean>('openCollectAfter', { default: true })

const step = ref(0)
const maxStep = 2

const slotLabels = computed(() => controlSlotLabels(playerIds.value.length))

const stepTitle = computed(() => {
  if (step.value === 0) return t('control.wizardStepConfig')
  if (step.value === 1) return t('control.wizardStepProtocol')
  return t('control.wizardStepConfirm')
})

watch(open, (isOpen) => {
  if (isOpen) step.value = 0
})

function setPlayerAt(index: number, value: string): void {
  const current = playerIds.value[index] ?? ''
  if (!value && current) return
  if (current === value) return
  const next = [...playerIds.value]
  next[index] = value
  playerIds.value = next
}

function nextStep(): void {
  if (step.value < maxStep) step.value += 1
}

function prevStep(): void {
  if (step.value > 0) step.value -= 1
}
</script>

<template>
  <UiDialog
    :open="open"
    :title="t('control.title')"
    :description="stepTitle"
    @update:open="open = $event"
  >
    <div class="space-y-4">
      <div v-if="step === 0" class="space-y-4">
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-text">{{ t('common.name') }}</label>
          <UiInput v-model="name" :placeholder="t('control.namePlaceholder')" class="w-full" />
        </div>
        <div v-for="(label, index) in slotLabels" :key="`${label}-${index}`">
          <label class="mb-1.5 block text-sm font-medium text-ink-text">{{ label }}</label>
          <UiSelect
            :model-value="playerIds[index] ?? ''"
            :options="index === 0 ? challengerOptions : baselineOptions"
            :placeholder="
              index === 0 ? t('control.challengerPlaceholder') : t('control.baselinePlaceholder')
            "
            class="w-full"
            @update:model-value="setPlayerAt(index, $event)"
          />
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-text">
            {{ t('experiment.targetGames') }}
          </label>
          <UiInputNumber v-model="target" :min="1" :max="50" />
        </div>
        <div class="space-y-1.5">
          <UiCheckbox v-model="pairDeals" :label="t('control.pairDeals')" disabled />
          <p class="text-xs text-ink-text-muted">{{ t('control.pairDealsHint') }}</p>
        </div>
        <p v-if="challengerOptions.length === 0" class="text-xs text-ink-warning">
          {{ t('control.noPlayers') }}
        </p>
      </div>

      <div v-else-if="step === 1" class="space-y-3 text-sm text-ink-text-secondary">
        <p>{{ t('control.wizardProtocolIntro', { id: sourceExperimentLabel }) }}</p>
        <ul class="space-y-1 rounded-ink border border-ink-border bg-ink-surface-muted/40 px-3 py-2">
          <li>{{ t('control.wizardSeedCount', { n: seedCount }) }}</li>
          <li v-for="(bit, i) in protocolSummaryBits" :key="i">{{ bit }}</li>
        </ul>
      </div>

      <div v-else class="space-y-3 text-sm text-ink-text-secondary">
        <p>{{ t('control.wizardConfirmIntro') }}</p>
        <UiCheckbox v-model="openCollectAfter" :label="t('control.openCollectAfter')" />
      </div>

      <div class="flex justify-end gap-2 pt-2">
        <UiButton v-if="step > 0" variant="secondary" :disabled="loading" @click="prevStep">
          {{ t('common.back') }}
        </UiButton>
        <UiButton v-if="step < maxStep" :disabled="step === 0 && !canSubmit" @click="nextStep">
          {{ t('control.wizardNext') }}
        </UiButton>
        <UiButton
          v-else
          :disabled="!canSubmit"
          :loading="loading"
          @click="emit('submit')"
        >
          {{ t('control.submit') }}
        </UiButton>
      </div>
    </div>
  </UiDialog>
</template>
