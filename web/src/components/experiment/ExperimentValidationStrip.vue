<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import type { ExperimentValidation } from '@/api/experimentApi'
import UiBadge from '@/components/ui/Badge.vue'
import UiButton from '@/components/ui/Button.vue'

const props = defineProps<{
  validation: ExperimentValidation | null
  shortExperimentId: (id: string) => string
}>()

const emit = defineEmits<{
  openControl: []
  compare: []
}>()

const { t } = useI18n()
const router = useRouter()

const controls = computed(() => props.validation?.control_progress ?? [])
const hasControls = computed(() => controls.value.length > 0)
const ready = computed(() => props.validation?.validation_ready === true)

function goCollect(controlId: string): void {
  void router.push({ path: `/experiments/${controlId}`, query: { collect: '1' } })
}
</script>

<template>
  <div
    v-if="validation"
    class="rounded-ink-md border border-ink-border bg-ink-surface-muted/40 px-3 py-2.5"
  >
    <div class="flex flex-wrap items-center justify-between gap-2">
      <div class="flex flex-wrap items-center gap-2">
        <span class="text-sm font-medium text-ink-text">{{ t('experiment.validationStripTitle') }}</span>
        <UiBadge :variant="ready ? 'success' : 'warning'">
          {{
            ready ? t('experiment.validationReady') : t('experiment.validationPending')
          }}
        </UiBadge>
      </div>
      <div class="flex flex-wrap gap-2">
        <UiButton v-if="!hasControls" size="sm" variant="secondary" @click="emit('openControl')">
          {{ t('experiment.validationOpenControl') }}
        </UiButton>
        <UiButton v-else-if="ready" size="sm" @click="emit('compare')">
          {{ t('experiment.compare') }}
        </UiButton>
      </div>
    </div>

    <p v-if="!hasControls" class="mt-2 text-sm text-ink-text-secondary">
      {{ t('experiment.validationNoControl') }}
    </p>

    <ul v-else class="mt-2 space-y-1.5">
      <li
        v-for="item in controls"
        :key="item.id"
        class="flex flex-wrap items-center gap-2 text-sm text-ink-text-secondary"
      >
        <button
          type="button"
          class="font-medium text-ink-primary hover:underline"
          @click="router.push(`/experiments/${item.id}`)"
        >
          {{ item.name }}
        </button>
        <span>
          {{
            t('experiment.validationControlProgress', {
              finished: item.finished_games,
              target: item.target_games,
              paired: item.paired_n,
            })
          }}
        </span>
        <UiBadge :variant="item.ready ? 'success' : 'muted'" class="text-xs">
          {{ item.ready ? t('experiment.validationReady') : t('experiment.validationPending') }}
        </UiBadge>
        <UiButton
          v-if="!item.ready"
          size="sm"
          variant="ghost"
          class="h-7 px-2 text-xs"
          @click="goCollect(item.id)"
        >
          {{ t('experiment.nextStep.collect_control') }}
        </UiButton>
      </li>
    </ul>
  </div>
</template>
