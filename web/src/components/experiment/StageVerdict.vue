<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ExperimentDelta, ExperimentVerdictKey } from '@/api/experimentApi'
import { metricLabel } from '@/utils/researchOutcome'
import { formatDeltaPp, formatPValue, formatWinRateCi } from '@/utils/experimentWorkbench'
import { verdictHeadlineOf } from '@/utils/experimentStage'
import PairedSample from './PairedSample.vue'
import MetricHint from '@/components/common/MetricHint.vue'
import UiButton from '@/components/ui/Button.vue'

const props = defineProps<{
  runName: string
  delta: ExperimentDelta
  players?: { id: string; name: string }[]
  verdictKey: ExperimentVerdictKey
  actionLabel?: string
  actionDisabled?: boolean
}>()

const emit = defineEmits<{
  action: []
  compare: []
  openPeer: []
}>()

const { t } = useI18n()

const weak = computed(() => !props.delta.can_conclude)

const headline = computed(() => verdictHeadlineOf(props.delta))

const metric = computed(() => metricLabel(t, props.delta.primary_metric, props.players))
const claim = computed(() =>
  t(`stage.${headline.value.key}`, { ...headline.value.params, metric: metric.value }),
)

/** Supporting line under a weak headline — names the provisional delta. */
const supportDetail = computed(() => {
  if (!weak.value) {
    return t('stage.evidence.sufficient', { n: props.delta.paired_n })
  }
  const key = props.verdictKey
  if (key === 'stronger' || key === 'weaker' || key === 'even') {
    return t('stage.diffSoFar', {
      delta: formatDeltaPp(props.delta.win_rate_diff),
      claim: t(`stage.verdict.${key}`, { metric: metric.value }),
    })
  }
  return ''
})

const supportLine = computed(() => {
  const parts = [
    t('stage.support.interval', {
      range: formatWinRateCi(props.delta.this_win_rate_ci ?? undefined),
    }),
  ]
  if (props.delta.paired_p != null) {
    parts.push(t('stage.support.pairedP', { p: formatPValue(props.delta.paired_p) }))
  }
  if (props.delta.paired_ci && props.delta.paired_ci.length >= 2) {
    const [lo, hi] = props.delta.paired_ci
    parts.push(
      t('stage.support.pairedCi', {
        range: `${formatDeltaPp(lo)}…${formatDeltaPp(hi)}`,
      }),
    )
  }
  return parts.join(' · ')
})
</script>

<template>
  <section id="experiment-verdict" class="ink-section py-ink-6">
    <p class="text-caption text-ink-text-muted">
      {{
        t(delta.relation === 'vs_source' ? 'experiment.deltaVsSource' : 'experiment.deltaVsControl')
      }}
      ·
      <button type="button" class="text-ink-primary hover:underline" @click="emit('openPeer')">
        {{ delta.peer_name }}
      </button>
    </p>

    <h2 class="ink-verdict-claim mt-ink-2" :class="{ 'is-weak': weak }">{{ claim }}</h2>

    <p v-if="weak" class="mt-ink-3 text-title font-normal tabular-nums text-ink-text-muted">
      {{ metric }} ·
      {{ t(delta.difference_basis === 'unpaired' ? 'stage.unpairedDiff' : 'stage.diffLabel') }}
      {{ formatDeltaPp(delta.win_rate_diff) }}
    </p>
    <p v-else class="ink-verdict-number mt-ink-3">
      {{ formatDeltaPp(delta.win_rate_diff) }}
    </p>

    <p class="mt-ink-1 flex flex-wrap items-center gap-ink-1 text-caption text-ink-text-muted">
      {{ supportLine }}
      <MetricHint
        :plain="t('metricHint.overallDelta.plain')"
        :formula="t('metricHint.overallDelta.formula')"
      />
    </p>

    <p
      v-if="
        delta.primary_metric.kind === 'seat_team_win_rate' && delta.affected_player_ids.length > 1
      "
      class="text-caption text-ink-text-secondary"
    >
      {{ t('promptDesign.sharedChange') }}
    </p>

    <p v-if="supportDetail" class="mt-ink-4 max-w-2xl text-lead text-ink-text-secondary">
      {{ supportDetail }}
    </p>

    <details class="mt-ink-4 text-caption">
      <summary class="cursor-pointer">
        {{ t(`focus.purpose.${delta.deal_purpose}`) }} ·
        {{ t('focus.paired', { n: delta.paired_n }) }}
      </summary>
      <PairedSample
        :purpose="delta.deal_purpose"
        :effective="delta.paired_n"
        :excluded="delta.paired_excluded_n"
        :counts="delta.outcome_counts"
        :a="delta.relation === 'vs_source' ? delta.peer_name : runName"
        :b="delta.relation === 'vs_source' ? runName : delta.peer_name"
      />
    </details>
    <div class="mt-ink-6 flex flex-wrap items-center gap-ink-3">
      <UiButton size="lg" @click="emit('compare')">
        {{ t('experiment.compareFull') }}
      </UiButton>
      <UiButton
        v-if="actionLabel"
        variant="secondary"
        :disabled="actionDisabled"
        @click="emit('action')"
      >
        {{ actionLabel }}
      </UiButton>
    </div>
  </section>
</template>
