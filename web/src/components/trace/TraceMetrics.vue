<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { AggregatedMetrics } from '@/api/traces'
import { formatPercentage } from '@/utils/format'
import { traceLatency } from '@/utils/traceMetrics'

const props = defineProps<{ metrics: AggregatedMetrics }>()
const { t } = useI18n()
const successRate = computed(() =>
  props.metrics.parser_evaluated_count > 0
    ? props.metrics.parser_success_count / props.metrics.parser_evaluated_count
    : null,
)
function latency(value: number | null): string {
  const valid = traceLatency(value)
  return valid === null
    ? t('trace.notRecorded')
    : valid.toLocaleString(undefined, { maximumFractionDigits: 2 })
}
</script>

<template>
  <section class="ink-card" :aria-label="t('trace.metrics')">
    <h3 class="mb-ink-4 text-body font-semibold text-ink-text">
      {{ t('trace.metricCount', { n: metrics.total_traces }) }}
    </h3>
    <dl class="grid grid-cols-2 gap-ink-4 md:grid-cols-4">
      <div
        v-for="item in [
          { label: 'avgMs', value: metrics.avg_response_time_ms },
          { label: 'minMs', value: metrics.min_response_time_ms },
          { label: 'maxMs', value: metrics.max_response_time_ms },
        ]"
        :key="item.label"
      >
        <dt class="text-caption text-ink-text-muted">{{ t(`trace.${item.label}`) }}</dt>
        <dd class="text-title font-semibold tabular-nums text-ink-text">
          {{ latency(item.value) }}
        </dd>
      </div>
      <div>
        <dt class="text-caption text-ink-text-muted">
          {{
            t('trace.parseRatio', {
              ok: metrics.parser_success_count,
              total: metrics.parser_evaluated_count,
            })
          }}
        </dt>
        <dd class="text-title font-semibold tabular-nums text-ink-text">
          {{ successRate === null ? t('trace.notRecorded') : formatPercentage(successRate) }}
        </dd>
      </div>
    </dl>
    <p class="mt-ink-4 text-caption text-ink-text-secondary">
      {{
        t('trace.metricDenominators', {
          valid: metrics.response_time_count,
          excluded: metrics.total_traces - metrics.response_time_count,
          known: metrics.parser_evaluated_count,
          unknown: metrics.total_traces - metrics.parser_evaluated_count,
        })
      }}
    </p>
    <p class="mt-ink-2 text-caption text-ink-text-muted">{{ t('trace.inferenceScope') }}</p>
  </section>
</template>
