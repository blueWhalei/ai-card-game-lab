<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ExperimentDelta, ExperimentVerdictKey } from '@/api/experimentApi'
import { formatDeltaPp, formatWinRateCi } from '@/utils/experimentWorkbench'
import ExperimentScenarioBars from '@/components/experiment/ExperimentScenarioBars.vue'
import MetricHint from '@/components/common/MetricHint.vue'
import UiButton from '@/components/ui/Button.vue'

const props = defineProps<{
  delta: ExperimentDelta
  verdictKey: ExperimentVerdictKey
  /** Extra decisive games that would lift the pair out of low power. */
  gamesNeeded: number
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

const claim = computed(() => t(`stage.verdict.${props.verdictKey}`))

/** What to do about the missing evidence, in a number the user can act on. */
const evidenceLine = computed(() => {
  const reason = props.delta.inconclusive_reason
  if (!reason) return t('stage.evidence.sufficient', { n: props.delta.paired_n })
  if (reason === 'peer_not_ready') return t('stage.evidence.peerPending')
  if (reason === 'low_power') {
    return props.gamesNeeded > 0
      ? t('stage.evidence.lowPowerNeed', { n: props.delta.paired_n, need: props.gamesNeeded })
      : t('stage.evidence.lowPower', { n: props.delta.paired_n })
  }
  return t('stage.evidence.noData')
})

const supportLine = computed(() => {
  const parts = [
    t('stage.support.paired', { n: props.delta.paired_n }),
    t('stage.support.interval', {
      range: formatWinRateCi(props.delta.this_landlord_win_rate_ci ?? undefined),
    }),
  ]
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

    <p class="ink-verdict-number mt-ink-3" :class="{ 'is-weak': weak }">
      {{ formatDeltaPp(delta.landlord_win_rate_diff) }}
    </p>
    <p class="mt-ink-1 flex flex-wrap items-center gap-ink-1 text-caption text-ink-text-muted">
      {{ supportLine }}
      <MetricHint
        :plain="t('metricHint.overallDelta.plain')"
        :formula="t('metricHint.overallDelta.formula')"
      />
    </p>

    <p class="mt-ink-4 max-w-2xl text-lead text-ink-text-secondary">{{ evidenceLine }}</p>

    <div class="mt-ink-6 flex flex-wrap items-center gap-ink-3">
      <UiButton
        v-if="actionLabel"
        size="lg"
        :disabled="actionDisabled"
        @click="emit('action')"
      >
        {{ actionLabel }}
      </UiButton>
      <UiButton variant="secondary" @click="emit('compare')">
        {{ t('experiment.compareFull') }}
      </UiButton>
    </div>

    <div class="mt-ink-6 max-w-xl">
      <ExperimentScenarioBars :diffs="delta.scenario_diffs" />
    </div>
  </section>
</template>
