<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { tracesApi, type Trace, type AggregatedMetrics } from '@/api/traces'
import { formatDateTime } from '@/utils/format'
import { showApiError } from '@/utils/error'
import UiSpinner from '@/components/ui/Spinner.vue'
import UiButton from '@/components/ui/Button.vue'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

const { t } = useI18n()

const props = defineProps<{
  gameId?: string
  experimentId?: string
  playerId?: string
  model?: string
  parserOk?: boolean
}>()

const traces = ref<Trace[]>([])
const metrics = ref<AggregatedMetrics | null>(null)
const loading = ref(false)
const timeRange = ref<'1h' | '24h' | '7d'>('24h')

const rangeOptions = computed(() => [
  { value: '1h' as const, label: t('trace.range1h') },
  { value: '24h' as const, label: t('trace.range24h') },
  { value: '7d' as const, label: t('trace.range7d') },
])

const listParams = computed(() => {
  const params: {
    game_id?: string
    experiment_id?: string
    player_id?: string
    model?: string
    parser_ok?: boolean
    page: number
    page_size: number
  } = { page: 1, page_size: 100 }
  if (props.gameId) params.game_id = props.gameId
  else if (props.experimentId) params.experiment_id = props.experimentId
  if (props.playerId) params.player_id = props.playerId
  if (props.model) params.model = props.model
  if (props.parserOk !== undefined) params.parser_ok = props.parserOk
  return params
})

const chartData = computed(() => {
  const now = Date.now()
  let cutoff = now

  switch (timeRange.value) {
    case '1h':
      cutoff = now - 60 * 60 * 1000
      break
    case '24h':
      cutoff = now - 24 * 60 * 60 * 1000
      break
    case '7d':
      cutoff = now - 7 * 24 * 60 * 60 * 1000
      break
  }

  const filtered = traces.value.filter((t) => new Date(t.created_at).getTime() > cutoff)

  return filtered
    .filter((t) => Number.isFinite(t.metrics?.response_time_ms))
    .map((t) => ({
      time: formatDateTime(t.created_at),
      responseTime: t.metrics.response_time_ms,
      round: t.round_number,
      player: t.player_id,
    }))
    .reverse()
})

type ChartPoint = {
  value: number
  time: string
  round: number
  player: string
}

const chartOption = computed(() => {
  const points: ChartPoint[] = chartData.value.map((d) => ({
    value: d.responseTime,
    time: d.time,
    round: d.round,
    player: d.player,
  }))

  return {
    tooltip: {
      trigger: 'axis' as const,
      formatter: (params: Array<{ data: ChartPoint }>) => {
        const data = params[0]?.data
        if (!data) return ''
        return `
        <div style="padding: 8px;">
          <div style="font-weight: 600; margin-bottom: 4px;">${data.time}</div>
          <div>${t('trace.tooltipMs')} <span style="color: #1a6b5c; font-weight: 600;">${data.value.toFixed(0)}ms</span></div>
          <div>${t('trace.tooltipRound', { n: data.round })}</div>
          <div>${t('trace.tooltipPlayer', { id: data.player })}</div>
        </div>
      `
      },
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true,
    },
    xAxis: {
      type: 'category' as const,
      data: points.map((d) => d.time),
      axisLabel: {
        rotate: 45,
        fontSize: 10,
        color: '#86868b',
      },
      axisLine: {
        lineStyle: { color: '#d2d2d7' },
      },
    },
    yAxis: {
      type: 'value' as const,
      name: t('trace.seriesMs'),
      nameTextStyle: {
        color: '#86868b',
        fontSize: 11,
      },
      axisLabel: {
        color: '#86868b',
        fontSize: 11,
      },
      splitLine: {
        lineStyle: { color: '#f5f5f7' },
      },
    },
    series: [
      {
        name: t('trace.series'),
        type: 'line' as const,
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        data: points,
        lineStyle: {
          color: '#1a6b5c',
          width: 2,
        },
        itemStyle: {
          color: '#1a6b5c',
        },
        areaStyle: {
          color: {
            type: 'linear' as const,
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(26, 107, 92, 0.28)' },
              { offset: 1, color: 'rgba(26, 107, 92, 0.04)' },
            ],
          },
        },
      },
    ],
  }
})

async function fetchData() {
  loading.value = true
  try {
    const params = listParams.value
    const metricsOnly = {
      game_id: params.game_id,
      experiment_id: params.experiment_id,
      player_id: params.player_id,
      model: params.model,
      parser_ok: params.parser_ok,
    }
    const [tracesRes, metricsRes] = await Promise.all([
      tracesApi.list(params),
      tracesApi.metrics(metricsOnly),
    ])

    traces.value = tracesRes.data.items
    metrics.value = metricsRes.data
  } catch (e: unknown) {
    showApiError(e, t('trace.trendFailed'))
  } finally {
    loading.value = false
  }
}

watch(listParams, fetchData, { deep: true })
onMounted(fetchData)
</script>

<template>
  <div class="relative rounded-ink-md border border-ink-border bg-ink-surface p-5">
    <UiSpinner v-if="loading" overlay :label="t('common.loading')" />
    <div class="mb-4 flex items-center justify-between">
      <h3 class="text-xs font-semibold uppercase tracking-wider text-ink-text-muted">
        {{ t('trace.trendTitle') }}
      </h3>
      <div class="flex gap-2">
        <UiButton
          v-for="range in rangeOptions"
          :key="range.value"
          size="sm"
          :variant="timeRange === range.value ? 'primary' : 'secondary'"
          @click="timeRange = range.value"
        >
          {{ range.label }}
        </UiButton>
      </div>
    </div>

    <div v-if="chartData.length > 0" class="h-[300px]">
      <VChart :option="chartOption" autoresize />
    </div>
    <div v-else class="flex h-[300px] items-center justify-center text-ink-text-muted">
      {{ t('common.noData') }}
    </div>

    <!-- Quick Stats -->
    <div v-if="metrics" class="mt-4 grid grid-cols-3 gap-4 border-t border-ink-border pt-4">
      <div class="text-center">
        <div class="text-lg font-semibold text-ink-text">
          {{ metrics.avg_response_time_ms.toFixed(0) }}ms
        </div>
        <div class="text-xs text-ink-text-muted">{{ t('trace.avgResponse') }}</div>
      </div>
      <div class="text-center">
        <div class="text-lg font-semibold text-ink-success">
          {{ metrics.min_response_time_ms.toFixed(0) }}ms
        </div>
        <div class="text-xs text-ink-text-muted">{{ t('trace.minResponse') }}</div>
      </div>
      <div class="text-center">
        <div class="text-lg font-semibold text-ink-danger">
          {{ metrics.max_response_time_ms.toFixed(0) }}ms
        </div>
        <div class="text-xs text-ink-text-muted">{{ t('trace.maxResponse') }}</div>
      </div>
    </div>
  </div>
</template>
