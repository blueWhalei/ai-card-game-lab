<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { AggregatedMetrics } from '@/api/traces'
import { formatPercentage } from '@/utils/format'

const props = defineProps<{
  metrics: AggregatedMetrics
}>()

const { t } = useI18n()

const successCount = computed(() => props.metrics.langchain_success_count ?? 0)

const successRate = computed(() => {
  if (props.metrics.total_traces === 0) return 0
  return successCount.value / props.metrics.total_traces
})
</script>

<template>
  <div class="ink-card">
    <h3 class="mb-4 text-sm font-semibold text-ink-text">{{ t('trace.metrics') }}</h3>
    <div class="grid grid-cols-2 gap-4 md:grid-cols-4">
      <div>
        <div class="text-xl font-semibold tabular-nums text-ink-text">
          {{ Math.round(metrics.avg_response_time_ms) }}
        </div>
        <div class="text-xs text-ink-text-muted">{{ t('trace.avgMs') }}</div>
      </div>
      <div>
        <div class="text-xl font-semibold tabular-nums text-ink-text">
          {{ Math.round(metrics.min_response_time_ms) }}
        </div>
        <div class="text-xs text-ink-text-muted">{{ t('trace.minMs') }}</div>
      </div>
      <div>
        <div class="text-xl font-semibold tabular-nums text-ink-text">
          {{ Math.round(metrics.max_response_time_ms) }}
        </div>
        <div class="text-xs text-ink-text-muted">{{ t('trace.maxMs') }}</div>
      </div>
      <div>
        <div class="text-xl font-semibold tabular-nums text-ink-text">
          {{ formatPercentage(successRate) }}
        </div>
        <div class="text-xs text-ink-text-muted">
          {{ t('trace.parseRatio', { ok: successCount, total: metrics.total_traces }) }}
        </div>
      </div>
    </div>
  </div>
</template>
