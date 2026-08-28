<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { useDataStore } from '@/stores/useDataStore'
import { showApiError } from '@/utils/error'
import { formatPercentage } from '@/utils/format'
import type { ModelWinRate } from '@/api/dataApi'
import UiSpinner from '@/components/ui/Spinner.vue'
import UiTable from '@/components/ui/Table.vue'
import type { TableColumn } from '@/components/ui/Table.vue'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent])

const INK_PRIMARY = '#1a6b5c'

const store = useDataStore()

onMounted(async () => {
  try {
    await store.fetchStatsOnce()
  } catch (e: unknown) {
    showApiError(e, '加载 AI 性能失败')
  }
})

const rows = computed(() => store.stats?.ai_win_rates ?? [])

const columns: TableColumn<ModelWinRate & Record<string, unknown>>[] = [
  { key: 'model', label: '模型' },
  { key: 'games', label: '对局数' },
  { key: 'wins', label: '胜场' },
  {
    key: 'win_rate',
    label: '胜率',
    render: (row) => formatPercentage(row.win_rate as number),
  },
]

const chartOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 48, right: 16, top: 24, bottom: 48 },
  xAxis: {
    type: 'category',
    data: rows.value.map((r) => r.model),
    axisLabel: { rotate: 25 },
  },
  yAxis: {
    type: 'value',
    max: 1,
    axisLabel: { formatter: (v: number) => `${(v * 100).toFixed(0)}%` },
  },
  series: [
    {
      name: '胜率',
      type: 'bar',
      data: rows.value.map((r) => r.win_rate),
      itemStyle: { color: INK_PRIMARY },
    },
  ],
}))

const tableRows = computed(() =>
  rows.value.map((r) => ({ ...r }) as ModelWinRate & Record<string, unknown>),
)
</script>

<template>
  <div class="relative min-h-[120px] space-y-6">
    <UiSpinner v-if="store.statsLoading" overlay label="加载中…" />

    <div class="ink-card">
      <h3 class="mb-4 text-base font-semibold text-ink-text">模型胜率对比</h3>
      <VChart v-if="rows.length" class="h-72 w-full" :option="chartOption" autoresize />
      <div v-else class="py-12 text-center text-ink-text-muted">暂无 AI 胜率数据</div>
    </div>

    <div class="ink-card">
      <h3 class="mb-4 text-base font-semibold text-ink-text">明细</h3>
      <UiTable :columns="columns" :rows="tableRows" row-key="model" />
    </div>
  </div>
</template>
