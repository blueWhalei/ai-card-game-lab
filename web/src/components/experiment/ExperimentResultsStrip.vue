<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ExperimentSummary } from '@/api/experimentApi'
import { formatWinRate, formatWinRateCi } from '@/utils/experimentWorkbench'
import KpiStrip from '@/components/common/KpiStrip.vue'
import type { KpiItem } from '@/components/common/KpiStrip.vue'

const props = defineProps<{
  summary: ExperimentSummary
}>()

const emit = defineEmits<{
  decisions: []
  training: []
  data: []
  compare: []
}>()

const { t } = useI18n()

function formatLatencyMs(ms: number): string {
  if (ms >= 1000) {
    const sec = ms / 1000
    return sec >= 10 ? `${Math.round(sec)}s` : `${sec.toFixed(1)}s`
  }
  return `${Math.round(ms)}ms`
}

const kpiItems = computed((): KpiItem[] => {
  const s = props.summary
  const dash = t('common.dash')
  const failed = s.status_counts?.failed ?? 0
  return [
    {
      id: 'usable',
      label: t('experiment.kpiUsable'),
      value: String(s.train_usable_decisions ?? 0),
      tone: 'primary',
      onClick: () => emit('decisions'),
    },
    {
      id: 'landlord',
      label: t('experiment.kpiLandlord'),
      value: (s.decisive_games ?? 0) > 0 ? formatWinRate(s.landlord_win_rate ?? 0) : dash,
      title: formatWinRateCi(s.landlord_win_rate_ci),
    },
    {
      id: 'parser',
      label: t('experiment.kpiParser'),
      value: (s.parser_n ?? 0) > 0 ? formatWinRate(s.parser_success_rate ?? 0) : dash,
    },
    {
      id: 'latency',
      label: t('experiment.kpiLatency'),
      value:
        (s.p50_response_ms ?? 0) > 0 || (s.p95_response_ms ?? 0) > 0
          ? `${formatLatencyMs(s.p50_response_ms ?? 0)} / ${formatLatencyMs(s.p95_response_ms ?? 0)}`
          : dash,
    },
    {
      id: 'tokens',
      label: t('experiment.kpiTokens'),
      value: (s.tokens_per_game ?? 0) > 0 ? String(Math.round(s.tokens_per_game ?? 0)) : dash,
      tone: failed > 0 ? 'danger' : 'default',
      title: failed > 0 ? t('experiment.failedCount', { n: failed }) : undefined,
    },
  ]
})

const showCompare = computed(
  () => (props.summary.train_usable_decisions ?? 0) > 0 || (props.summary.finished_games ?? 0) > 0,
)
</script>

<template>
  <section
    class="space-y-2 rounded-ink-md border border-ink-border/80 bg-ink-surface-muted/40 px-3 py-2.5"
  >
    <KpiStrip :items="kpiItems" class="md:grid-cols-5" />
    <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-text-secondary">
      <span class="font-medium text-ink-text">{{ t('experiment.resultsPipeline') }}</span>
      <button type="button" class="text-ink-primary hover:underline" @click="emit('decisions')">
        {{ t('nav.decisions') }}
      </button>
      <button type="button" class="text-ink-primary hover:underline" @click="emit('training')">
        {{ t('nav.training') }}
      </button>
      <button type="button" class="text-ink-primary hover:underline" @click="emit('data')">
        {{ t('nav.data') }}
      </button>
      <button
        v-if="showCompare"
        type="button"
        class="text-ink-primary hover:underline"
        @click="emit('compare')"
      >
        {{ t('experiment.compare') }}
      </button>
    </div>
  </section>
</template>
