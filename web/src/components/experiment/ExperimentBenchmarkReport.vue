<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Experiment } from '@/api/experimentApi'
import { formatWinRate, formatWinRateCi } from '@/utils/experimentWorkbench'
import MetricHint from '@/components/common/MetricHint.vue'

const props = defineProps<{
  experiment: Experiment
  configLabel: (id: string) => string
}>()

const { t } = useI18n()

const coverage = computed(() => props.experiment.benchmark)
const summary = computed(() => props.experiment.summary)
const incomplete = computed(() => !coverage.value?.complete)
const rateWeak = computed(
  () => incomplete.value || Boolean(summary.value.credibility?.low_power),
)

const usableRate = computed(() => {
  const rate = summary.value.train_usable_rate
  if (rate == null) return t('common.dash')
  return formatWinRate(rate)
})

const seats = computed(() =>
  (summary.value.player_stats ?? [])
    .filter((stat) => (stat.games_as_landlord ?? 0) > 0)
    .map((stat) => `${props.configLabel(stat.player_id)} ${formatWinRate(stat.landlord_win_rate ?? 0)}`),
)
</script>

<template>
  <section v-if="coverage" class="ink-section">
    <h2 class="ink-section-title">{{ t('stage.benchmark.title') }}</h2>

    <p class="mt-ink-3 text-lead">
      <span :class="incomplete ? 'font-normal text-ink-text-muted' : 'font-semibold text-ink-text'">
        {{
          t('stage.benchmark.lead', {
            total: coverage.seed_total,
            finished: coverage.seed_finished,
          })
        }}
      </span>
      <span class="mx-ink-1 text-ink-text-muted">·</span>
      <span
        class="tabular-nums"
        :class="rateWeak ? 'font-normal text-ink-text-muted' : 'font-semibold text-ink-text'"
      >
        {{
          t('stage.benchmark.rate', {
            rate: formatWinRate(summary.landlord_win_rate ?? 0),
            ci: formatWinRateCi(summary.landlord_win_rate_ci),
          })
        }}
      </span>
      <span class="ml-ink-1 inline-flex items-center gap-ink-1 align-middle">
        <MetricHint
          :plain="t('metricHint.landlord.plain')"
          :formula="t('metricHint.landlord.formula')"
        />
        <MetricHint :plain="t('metricHint.ci.plain')" :formula="t('metricHint.ci.formula')" />
      </span>
    </p>

    <p class="mt-ink-3 flex flex-wrap items-baseline gap-x-ink-3 gap-y-ink-1 text-body text-ink-text-secondary">
      <span class="inline-flex items-baseline gap-ink-1">
        {{ t('stage.benchmark.parser', { rate: formatWinRate(summary.parser_success_rate ?? 0) }) }}
        <MetricHint :plain="t('metricHint.parser.plain')" :formula="t('metricHint.parser.formula')" />
      </span>
      <span class="inline-flex items-baseline gap-ink-1">
        {{
          t('stage.benchmark.usable', {
            n: summary.train_usable_decisions,
            rate: usableRate,
          })
        }}
        <MetricHint :plain="t('metricHint.usable.plain')" :formula="t('metricHint.usable.formula')" />
      </span>
      <span class="inline-flex items-baseline gap-ink-1 tabular-nums">
        {{ t('stage.benchmark.p50', { ms: Math.round(summary.p50_response_ms ?? 0) }) }}
        <MetricHint :plain="t('metricHint.latency.plain')" :formula="t('metricHint.latency.formula')" />
      </span>
      <span class="inline-flex items-baseline gap-ink-1 tabular-nums">
        {{ t('stage.benchmark.tokens', { n: Math.round(summary.tokens_per_game ?? 0) }) }}
        <MetricHint :plain="t('metricHint.tokens.plain')" :formula="t('metricHint.tokens.formula')" />
      </span>
    </p>

    <p
      v-if="coverage.seed_failed > 0 || coverage.seed_running > 0"
      class="mt-ink-2 text-caption text-ink-text-muted"
    >
      <span v-if="coverage.seed_failed > 0">
        {{ t('stage.benchmark.failed', { n: coverage.seed_failed }) }}
      </span>
      <span v-if="coverage.seed_failed > 0 && coverage.seed_running > 0"> · </span>
      <span v-if="coverage.seed_running > 0">
        {{ t('stage.benchmark.running', { n: coverage.seed_running }) }}
      </span>
    </p>

    <p v-if="seats.length > 0" class="mt-ink-2 text-caption text-ink-text-muted">
      {{ t('stage.benchmark.seats') }}
      {{ seats.join(' · ') }}
    </p>

    <p v-if="incomplete && coverage.seed_remaining > 0" class="mt-ink-3 text-body text-ink-text-secondary">
      {{ t('stage.benchmark.incomplete', { n: coverage.seed_remaining }) }}
    </p>
  </section>
</template>
