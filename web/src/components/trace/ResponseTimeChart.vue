<script setup lang="ts">
import { ref, onBeforeUnmount, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { ScatterChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { tracesApi, type Trace, type AggregatedMetrics, type TraceFilters } from '@/api/traces'
import { formatDateTime } from '@/utils/format'
import { traceLatency } from '@/utils/traceMetrics'
import { useTheme } from '@/composables/useTheme'
import UiSpinner from '@/components/ui/Spinner.vue'
import UiButton from '@/components/ui/Button.vue'
import TraceMetrics from './TraceMetrics.vue'

use([CanvasRenderer, ScatterChart, GridComponent, TooltipComponent])
const { t } = useI18n()
const { theme } = useTheme()
const chartColors = computed(() => {
  // Theme changes invalidate canvas colors after CSS tokens have been applied.
  const mode = theme.value
  const style = getComputedStyle(document.documentElement)
  return {
    mode,
    point: style.getPropertyValue('--ink-primary').trim(),
    text: style.getPropertyValue('--ink-text-secondary').trim(),
    border: style.getPropertyValue('--ink-border').trim(),
  }
})
const props = defineProps<{
  gameId?: string
  experimentId?: string
  playerId?: string
  model?: string
  parserOk?: boolean
}>()
const traces = ref<Trace[]>([])
const total = ref(0)
const metrics = ref<AggregatedMetrics | null>(null)
const loading = ref(false)
const failed = ref(false)
const window = ref<{ start: string; end: string } | null>(null)
const timeRange = ref<'1h' | '24h' | '7d'>('24h')
let requestId = 0
const rangeOptions = computed(() => [
  { value: '1h' as const, label: t('trace.range1h') },
  { value: '24h' as const, label: t('trace.range24h') },
  { value: '7d' as const, label: t('trace.range7d') },
])
const filters = computed<TraceFilters>(() => ({
  game_id: props.gameId,
  experiment_id: props.experimentId,
  player_id: props.playerId,
  model: props.model,
  parser_ok: props.parserOk,
}))
type ChartPoint = { value: [number, number]; round: number; player: string }
const chartData = computed<ChartPoint[]>(() =>
  traces.value
    .flatMap((trace) => {
      const ms = traceLatency(trace.metrics.response_time_ms)
      const time = Date.parse(trace.created_at)
      return ms === null || !Number.isFinite(time)
        ? []
        : [
            {
              value: [time, ms] as [number, number],
              round: trace.round_number,
              player: trace.player_id,
            },
          ]
    })
    .sort((a, b) => a.value[0] - b.value[0]),
)
const chartOption = computed(() => ({
  textStyle: { color: chartColors.value.text },
  tooltip: {
    trigger: 'item' as const,
    renderMode: 'richText' as const,
    formatter: (params: { data: ChartPoint }) => {
      const point = params.data
      return [
        formatDateTime(new Date(point.value[0]).toISOString()),
        `${t('trace.tooltipMs')} ${point.value[1]} ms`,
        t('trace.tooltipRound', { n: point.round }),
        t('trace.tooltipPlayer', { id: point.player }),
      ].join('\n')
    },
  },
  grid: { left: 16, right: 24, bottom: 24, containLabel: true },
  xAxis: {
    type: 'time' as const,
    axisLabel: { color: chartColors.value.text },
    axisLine: { lineStyle: { color: chartColors.value.border } },
    min: window.value ? Date.parse(window.value.start) : undefined,
    max: window.value ? Date.parse(window.value.end) : undefined,
  },
  yAxis: {
    type: 'value' as const,
    name: t('trace.seriesMs'),
    min: 0,
    axisLabel: { color: chartColors.value.text },
    splitLine: { lineStyle: { color: chartColors.value.border } },
  },
  series: [
    {
      name: t('trace.series'),
      type: 'scatter' as const,
      symbolSize: 6,
      data: chartData.value,
      itemStyle: { color: chartColors.value.point },
    },
  ],
}))
async function fetchData() {
  const id = ++requestId
  loading.value = true
  failed.value = false
  traces.value = []
  total.value = 0
  metrics.value = null
  const end = Date.now()
  const hours = { '1h': 1, '24h': 24, '7d': 168 }[timeRange.value]
  window.value = {
    start: new Date(end - hours * 3600000).toISOString(),
    end: new Date(end).toISOString(),
  }
  const params = { ...filters.value, start_time: window.value.start, end_time: window.value.end }
  try {
    const [records, aggregate] = await Promise.all([
      tracesApi.list({ ...params, page: 1, page_size: 200 }),
      tracesApi.metrics(params),
    ])
    if (id !== requestId) return
    traces.value = records.data.items
    total.value = records.data.total
    metrics.value = aggregate.data
  } catch {
    if (id === requestId) failed.value = true
  } finally {
    if (id === requestId) loading.value = false
  }
}
watch([filters, timeRange], fetchData, { deep: true, immediate: true })
onBeforeUnmount(() => {
  requestId++
})
</script>

<template>
  <section class="space-y-ink-4">
    <div class="ink-card relative">
      <UiSpinner v-if="loading" overlay :label="t('common.loading')" />
      <div class="mb-ink-4 flex flex-wrap items-center justify-between gap-ink-3">
        <h3 class="text-body font-semibold text-ink-text">{{ t('trace.trendTitle') }}</h3>
        <div class="flex flex-wrap gap-ink-2">
          <UiButton
            v-for="range in rangeOptions"
            :key="range.value"
            size="sm"
            :aria-pressed="timeRange === range.value"
            :variant="timeRange === range.value ? 'primary' : 'secondary'"
            @click="timeRange = range.value"
            >{{ range.label }}</UiButton
          >
          <UiButton size="sm" variant="ghost" :disabled="loading" @click="fetchData">{{
            t('trace.refresh')
          }}</UiButton>
        </div>
      </div>
      <p v-if="window" class="text-caption text-ink-text-secondary">
        {{
          t('trace.timeWindow', {
            start: formatDateTime(window.start),
            end: formatDateTime(window.end),
          })
        }}
      </p>
      <div v-if="failed" role="alert" class="my-ink-4 space-y-ink-3">
        <p class="text-body text-ink-danger">{{ t('trace.trendFailed') }}</p>
        <UiButton size="sm" @click="fetchData">{{ t('common.retry') }}</UiButton>
      </div>
      <template v-else-if="!loading">
        <p class="mt-ink-2 text-caption text-ink-text-secondary">
          {{
            t('trace.chartScope', {
              points: chartData.length,
              loaded: traces.length,
              total,
              excluded: traces.length - chartData.length,
            })
          }}
        </p>
        <p v-if="total > traces.length" class="mt-ink-2 text-caption text-ink-text-secondary">
          {{ t('trace.truncated') }}
        </p>
        <div
          v-if="chartData.length"
          class="h-[300px]"
          role="img"
          :aria-label="t('trace.trendTitle')"
        >
          <VChart :option="chartOption" autoresize />
        </div>
        <p v-else class="py-ink-6 text-body text-ink-text-muted">{{ t('trace.noTimedValues') }}</p>
      </template>
    </div>
    <TraceMetrics v-if="metrics && !loading && !failed" :metrics="metrics" />
  </section>
</template>
