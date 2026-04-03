<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { tracesApi, type Trace, type AggregatedMetrics } from '@/api/traces'
import { formatDateTime } from '@/utils/format'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

const props = defineProps<{
  gameId?: string
}>()

const traces = ref<Trace[]>([])
const metrics = ref<AggregatedMetrics | null>(null)
const loading = ref(false)
const timeRange = ref<'1h' | '24h' | '7d'>('24h')

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
  
  const filtered = traces.value.filter(t => new Date(t.created_at).getTime() > cutoff)
  
  return filtered.map(t => ({
    time: formatDateTime(t.created_at),
    responseTime: t.metrics.response_time_ms,
    round: t.round_number,
    player: t.player_id,
  })).reverse()
})

const chartOption = computed(() => ({
  tooltip: {
    trigger: 'axis',
    formatter: (params: Array<{ data: { time: string; responseTime: number; round: number; player: string } }>) => {
      const data = params[0]?.data
      if (!data) return ''
      return `
        <div style="padding: 8px;">
          <div style="font-weight: 600; margin-bottom: 4px;">${data.time}</div>
          <div>响应时间: <span style="color: #0071e3; font-weight: 600;">${data.responseTime.toFixed(0)}ms</span></div>
          <div>轮次: R${data.round}</div>
          <div>玩家: ${data.player}</div>
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
    type: 'category',
    data: chartData.value.map(d => d.time),
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
    type: 'value',
    name: '响应时间 (ms)',
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
  series: [{
    name: '响应时间',
    type: 'line',
    smooth: true,
    symbol: 'circle',
    symbolSize: 6,
    data: chartData.value,
    lineStyle: {
      color: '#0071e3',
      width: 2,
    },
    itemStyle: {
      color: '#0071e3',
    },
    areaStyle: {
      color: {
        type: 'linear',
        x: 0,
        y: 0,
        x2: 0,
        y2: 1,
        colorStops: [
          { offset: 0, color: 'rgba(0, 113, 227, 0.3)' },
          { offset: 1, color: 'rgba(0, 113, 227, 0.05)' },
        ],
      },
    },
  }],
}))

async function fetchData() {
  loading.value = true
  try {
    const params: Record<string, string> = {}
    if (props.gameId) {
      params.game_id = props.gameId
    }
    
    const [tracesRes, metricsRes] = await Promise.all([
      tracesApi.list({ ...params, limit: 100 }),
      tracesApi.metrics(params),
    ])
    
    traces.value = tracesRes.data.data || []
    metrics.value = metricsRes.data.data
  } catch (e) {
    console.error('Failed to fetch trace data:', e)
  } finally {
    loading.value = false
  }
}

watch(() => props.gameId, fetchData)
onMounted(fetchData)
</script>

<template>
  <div v-loading="loading" class="apple-card">
    <div class="mb-4 flex items-center justify-between">
      <h3 class="text-xs font-semibold uppercase tracking-wider text-[#86868b]">AI 响应时间趋势</h3>
      <div class="flex gap-2">
        <button
          v-for="range in ['1h', '24h', '7d'] as const"
          :key="range"
          class="rounded-full px-3 py-1 text-xs font-medium transition-all"
          :class="timeRange === range ? 'bg-[#0071e3] text-white' : 'bg-[#f5f5f7] text-[#424245] hover:bg-[#e8e8ed]'"
          @click="timeRange = range"
        >
          {{ range === '1h' ? '1小时' : range === '24h' ? '24小时' : '7天' }}
        </button>
      </div>
    </div>
    
    <div v-if="chartData.length > 0" class="h-[300px]">
      <VChart :option="chartOption" autoresize />
    </div>
    <div v-else class="flex h-[300px] items-center justify-center text-[#86868b]">
      暂无数据
    </div>
    
    <!-- Quick Stats -->
    <div v-if="metrics" class="mt-4 grid grid-cols-3 gap-4 border-t border-[#f5f5f7] pt-4">
      <div class="text-center">
        <div class="text-lg font-semibold text-[#1d1d1f]">{{ metrics.avg_response_time_ms.toFixed(0) }}ms</div>
        <div class="text-xs text-[#86868b]">平均响应</div>
      </div>
      <div class="text-center">
        <div class="text-lg font-semibold text-[#4a9c2d]">{{ metrics.min_response_time_ms.toFixed(0) }}ms</div>
        <div class="text-xs text-[#86868b]">最小响应</div>
      </div>
      <div class="text-center">
        <div class="text-lg font-semibold text-[#ff3b30]">{{ metrics.max_response_time_ms.toFixed(0) }}ms</div>
        <div class="text-xs text-[#86868b]">最大响应</div>
      </div>
    </div>
  </div>
</template>
