<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  experimentStatusLabel,
  isBenchmarkExperiment,
  EXPERIMENT_STATUS_VARIANT,
  type Experiment,
} from '@/api/experimentApi'
import {
  formatExperimentProgress,
  resolveStageId,
  verdictHeadlineOf,
  gamesNeededForPower,
} from '@/utils/experimentStage'
import { experimentOutcomeText } from '@/utils/experimentOutcomes'
import NameChips from '@/components/common/NameChips.vue'
import UiBadge from '@/components/ui/Badge.vue'
import UiButton from '@/components/ui/Button.vue'

const props = defineProps<{
  experiment: Experiment
  playerNames: string[]
}>()

const emit = defineEmits<{
  open: []
  watch: []
}>()

const { t } = useI18n()

const stage = computed(() => resolveStageId(props.experiment))
const summary = computed(() => props.experiment.summary)
const progress = computed(() =>
  formatExperimentProgress(summary.value.finished_games, summary.value.target_games, t),
)

const claim = computed(() => {
  const exp = props.experiment
  if (stage.value === 'empty') return t('stage.empty.claim')
  if (stage.value === 'collecting') return t('stage.collecting.claim')
  if (stage.value === 'verdict' && exp.delta) {
    const headline = verdictHeadlineOf(exp.delta, gamesNeededForPower(exp))
    return t(`stage.${headline.key}`, headline.params ?? {})
  }
  return t('stage.harvest.readyClaim')
})

const actionLabel = computed(() => {
  if (stage.value === 'empty') return t('stage.empty.action')
  if (stage.value === 'collecting') return t('stage.collecting.action')
  if (stage.value === 'verdict') {
    const delta = props.experiment.delta
    if (delta && !delta.can_conclude) {
      return delta.relation === 'vs_source'
        ? t('stage.verdictAction.collectHere')
        : t('stage.verdictAction.collectControl')
    }
    return t('experiment.openDetail')
  }
  return t('experiment.openDetail')
})

const canWatch = computed(
  () => stage.value === 'collecting' && Boolean(summary.value.latest_game_id),
)

function onPrimary(): void {
  if (canWatch.value) {
    emit('watch')
    return
  }
  emit('open')
}
</script>

<template>
  <article
    class="flex flex-wrap items-center justify-between gap-ink-4 px-ink-6 py-ink-6 transition-colors hover:bg-ink-paper-elevated"
  >
    <button
      type="button"
      class="min-w-0 flex-1 rounded-ink text-left focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ink-primary"
      @click="emit('open')"
    >
      <div class="flex flex-wrap items-center gap-ink-2">
        <h3 class="truncate text-lead font-semibold text-ink-text">{{ experiment.name }}</h3>
        <UiBadge :variant="EXPERIMENT_STATUS_VARIANT[summary.status]" size="xs">
          {{ experimentStatusLabel(summary.status) }}
        </UiBadge>
        <UiBadge v-if="isBenchmarkExperiment(experiment)" variant="muted" size="xs">
          {{ t('experiment.modeBenchmark') }}
        </UiBadge>
      </div>
      <p class="mt-ink-1 max-w-2xl text-body text-ink-text-secondary">{{ claim }}</p>
      <p v-if="summary.total_games > 0" class="mt-ink-1 text-caption text-ink-text-muted">
        {{ experimentOutcomeText(summary) }}
      </p>
      <div class="mt-ink-2 flex flex-wrap items-center gap-ink-3 text-caption text-ink-text-muted">
        <span class="tabular-nums">{{ t('experiment.collectionProgress', { progress }) }}</span>
        <NameChips :names="playerNames" :max="3" />
      </div>
    </button>
    <UiButton size="sm" :variant="canWatch ? 'primary' : 'secondary'" @click="onPrimary">
      {{ actionLabel }}
    </UiButton>
  </article>
</template>
