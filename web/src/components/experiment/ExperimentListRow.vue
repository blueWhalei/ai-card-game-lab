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
  const s = summary.value
  if (stage.value === 'empty') return t('stage.empty.claim')
  if (stage.value === 'collecting') return t('stage.collecting.claim')
  if (stage.value === 'control') {
    return exp.next_step?.id === 'open_control'
      ? t('stage.control.claim')
      : t('stage.control.needPlayerClaim')
  }
  if (stage.value === 'verdict' && exp.delta) {
    const headline = verdictHeadlineOf(exp.delta, gamesNeededForPower(exp))
    return t(`stage.${headline.key}`, headline.params ?? {})
  }
  if (exp.next_step?.id === 'review_decisions') {
    return t('stage.harvest.reviewClaim', { n: s.train_usable_decisions })
  }
  if (s.train_usable_decisions <= 0) return t('stage.harvest.noneClaim')
  return t('stage.harvest.claim', { n: s.train_usable_decisions })
})

const actionLabel = computed(() => {
  if (stage.value === 'empty') return t('stage.empty.action')
  if (stage.value === 'collecting') return t('stage.collecting.action')
  if (stage.value === 'control') {
    return props.experiment.next_step?.id === 'open_control'
      ? t('stage.control.action')
      : t('stage.control.needPlayerAction')
  }
  if (stage.value === 'verdict') {
    const delta = props.experiment.delta
    if (delta && !delta.can_conclude) {
      return delta.relation === 'vs_source'
        ? t('stage.verdictAction.collectHere')
        : t('stage.verdictAction.collectControl')
    }
    return t('experiment.openDetail')
  }
  if (props.experiment.next_step?.id === 'review_decisions') {
    return t('stage.harvest.reviewAction')
  }
  if (summary.value.train_usable_decisions <= 0) return t('stage.harvest.noneAction')
  return t('stage.harvest.action')
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
    class="flex flex-wrap items-center justify-between gap-ink-3 rounded-ink-md border border-ink-border bg-ink-surface px-ink-4 py-ink-3 transition-colors hover:bg-ink-paper-elevated/80"
  >
    <button type="button" class="min-w-0 flex-1 text-left" @click="emit('open')">
      <div class="flex flex-wrap items-center gap-ink-2">
        <h3 class="truncate text-body font-semibold text-ink-text">{{ experiment.name }}</h3>
        <UiBadge :variant="EXPERIMENT_STATUS_VARIANT[summary.status]" size="xs">
          {{ experimentStatusLabel(summary.status) }}
        </UiBadge>
        <UiBadge v-if="isBenchmarkExperiment(experiment)" variant="muted" size="xs">
          {{ t('experiment.modeBenchmark') }}
        </UiBadge>
      </div>
      <p class="mt-ink-1 max-w-2xl text-body text-ink-text-secondary">{{ claim }}</p>
      <div class="mt-ink-2 flex flex-wrap items-center gap-ink-3 text-caption text-ink-text-muted">
        <span class="tabular-nums">{{ progress }}</span>
        <NameChips :names="playerNames" :max="3" />
      </div>
    </button>
    <UiButton size="sm" :variant="canWatch ? 'primary' : 'secondary'" @click="onPrimary">
      {{ actionLabel }}
    </UiButton>
  </article>
</template>
