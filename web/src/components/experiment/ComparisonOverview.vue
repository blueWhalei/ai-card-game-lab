<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ExperimentCompareResult } from '@/api/experimentApi'
import PairedSample from './PairedSample.vue'
import { metricLabel, seatLabel } from '@/utils/researchOutcome'
import { formatDeltaPp } from '@/utils/experimentWorkbench'

const props = defineProps<{ result: ExperimentCompareResult }>()
const { t } = useI18n()
const paired = computed(() => props.result.paired_summary)
const variant = computed(() =>
  props.result.experiments.find((run) => run.id === paired.value?.control_id),
)
const seats = computed(() => variant.value?.protocol?.solver.players)
const outcome = computed(
  () => paired.value && metricLabel(t, paired.value.primary_metric, seats.value),
)
const hasPairs = computed(
  () => (paired.value?.shared_seeds ?? 0) > 0 && paired.value?.win_rate_diff != null,
)
const interval = computed(() => paired.value?.paired_ci)
const warning = computed(() => {
  if (!props.result.protocol_review?.controlled) return 'focus.descriptive'
  if (props.result.coverage?.deal_purpose === 'holdout' && props.result.coverage.excluded_n)
    return 'focus.incompleteHoldout'
  if (paired.value?.low_power) return 'focus.lowPower'
  if (!interval.value) return 'focus.noInterval'
  if (interval.value[0] <= 0 && interval.value[1] >= 0) return 'focus.uncertain'
  return 'focus.estimateOnly'
})
function runName(id: string | undefined) {
  return props.result.experiments.find((run) => run.id === id)?.name ?? id ?? t('common.dash')
}
// Display the server-provided estimate and interval on a fixed -100…+100 pp scale.
function position(value: number) {
  return `${Math.max(0, Math.min(100, (value + 1) * 50))}%`
}
</script>

<template>
  <section class="space-y-ink-6 py-ink-6" :aria-label="t('promptDesign.metric')">
    <div v-if="paired?.affected_player_ids.length" class="space-y-ink-2">
      <p class="text-body">{{ variant?.protocol?.design?.hypothesis }}</p>
      <p class="text-caption text-ink-text-muted">
        {{
          t('promptDesign.affected', {
            seats: paired.affected_player_ids.map((id) => seatLabel(id, seats)).join(', '),
          })
        }}
      </p>
      <p v-if="!hasPairs" class="text-caption">{{ outcome }}</p>
    </div>
    <PairedSample
      v-if="result.experiments.length === 2 && paired && result.coverage"
      :purpose="result.coverage.deal_purpose"
      :effective="result.coverage.effective_n"
      :excluded="result.coverage.excluded_n"
      :counts="paired.outcome_counts"
      :a="runName(paired.source_id)"
      :b="runName(paired.control_id)"
    />
    <template v-if="result.experiments.length === 2 && hasPairs">
      <div class="flex flex-wrap items-baseline justify-between gap-ink-3">
        <p class="break-words text-caption text-ink-text-muted">
          {{
            t('focus.differenceOrder', {
              control: runName(paired!.control_id),
              source: runName(paired!.source_id),
            })
          }}
        </p>
      </div>
      <div class="grid items-center gap-ink-6 md:grid-cols-2">
        <div>
          <p class="text-caption text-ink-text-muted">
            {{ t('focus.pairMetric', { metric: outcome }) }}
          </p>
          <p class="mt-ink-2 text-verdict font-normal tabular-nums text-ink-text">
            {{ formatDeltaPp(paired!.win_rate_diff!) }}
          </p>
        </div>
        <div v-if="interval" class="space-y-ink-3">
          <div class="relative mx-ink-2 h-8" aria-hidden="true">
            <div class="absolute inset-x-0 top-1/2 border-t border-ink-border" />
            <div class="absolute inset-y-0 left-1/2 border-l border-dashed border-ink-text-muted" />
            <div
              class="absolute top-1/2 h-1 -translate-y-1/2 rounded-full bg-ink-primary/40"
              :style="{
                left: position(interval[0]),
                width: `${Math.max(0, interval[1] - interval[0]) * 50}%`,
              }"
            />
            <div
              class="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-ink-surface bg-ink-primary ring-1 ring-ink-primary"
              :style="{ left: position(paired!.win_rate_diff!) }"
            />
          </div>
          <div aria-hidden="true" class="flex justify-between text-caption text-ink-text-muted">
            <span>−100 pp</span><span>0</span><span>+100 pp</span>
          </div>
          <p class="text-caption text-ink-text-secondary">
            {{
              t('focus.interval', {
                low: formatDeltaPp(interval[0]),
                high: formatDeltaPp(interval[1]),
              })
            }}
          </p>
        </div>
      </div>
      <p class="max-w-3xl text-body text-ink-text-secondary">{{ t(warning) }}</p>
      <p
        v-if="paired?.primary_metric.kind === 'landlord_win_rate'"
        class="text-caption text-ink-text-muted"
      >
        {{ t('focus.pairScope') }}
      </p>
      <p
        v-else-if="(paired?.affected_player_ids.length ?? 0) > 1"
        class="text-caption text-ink-text-muted"
      >
        {{ t('promptDesign.sharedChange') }}
      </p>
    </template>
    <template v-else>
      <h2 class="text-headline font-semibold text-ink-text">
        {{ t(result.experiments.length > 2 ? 'focus.multiRun' : 'focus.noPairs') }}
      </h2>
      <p class="max-w-2xl text-body text-ink-text-secondary">
        {{ t(result.experiments.length > 2 ? 'focus.multiRunHint' : 'focus.noPairsHint') }}
      </p>
      <p v-if="!result.protocol_review?.controlled" class="text-caption text-ink-text-secondary">
        {{ t('focus.descriptive') }}
      </p>
    </template>
  </section>
</template>
