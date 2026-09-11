<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  experimentTimelineLabel,
  type ExperimentControlProgress,
  type ExperimentTimelineEvent,
} from '@/api/experimentApi'
import { formatDateTime } from '@/utils/format'
import { formatExperimentProgress } from '@/utils/experimentStage'

const props = defineProps<{
  events?: ExperimentTimelineEvent[]
  controlProgress?: ExperimentControlProgress[]
}>()

const emit = defineEmits<{
  openExperiment: [id: string]
}>()

const { t } = useI18n()

const events = computed(() => props.events ?? [])

const controls = computed(() => props.controlProgress ?? [])

function controlProgressLabel(control: ExperimentControlProgress): string {
  const progress = formatExperimentProgress(control.finished_games, control.target_games, t)
  return t('stage.controlProgressLabeled', {
    progress,
    paired: control.paired_n,
  })
}
</script>

<template>
  <section v-if="events.length > 0 || controls.length > 0" class="ink-section">
    <h2 class="ink-section-title">{{ t('stage.timelineTitle') }}</h2>

    <ol class="mt-ink-3 grid gap-ink-4 sm:grid-cols-2 lg:grid-cols-3">
      <li
        v-for="event in events"
        :key="`${event.id}-${event.at}`"
        class="flex flex-col gap-ink-1 border-l border-ink-border pl-ink-3"
      >
        <span class="w-44 shrink-0 text-caption tabular-nums text-ink-text-muted">
          {{ formatDateTime(event.at) }}
        </span>
        <span class="text-body text-ink-text">{{ experimentTimelineLabel(event.id) }}</span>
      </li>
    </ol>

    <ul v-if="controls.length > 0" class="mt-ink-4 space-y-ink-2">
      <li
        v-for="control in controls"
        :key="control.id"
        class="flex flex-col gap-ink-1 border-l border-ink-border pl-ink-3"
      >
        <span class="w-24 shrink-0 text-caption text-ink-text-muted">
          {{ t('stage.controlLabel') }}
        </span>
        <span class="min-w-0 text-body text-ink-text">
          <button
            type="button"
            class="text-ink-primary hover:underline"
            @click="emit('openExperiment', control.id)"
          >
            {{ control.name }}
          </button>
          <span class="ml-ink-2 text-caption tabular-nums text-ink-text-muted">
            {{ controlProgressLabel(control) }}
          </span>
        </span>
      </li>
    </ul>
  </section>
</template>
