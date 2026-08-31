<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
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
const INK_ACCENT = '#c47a1a'

const { t } = useI18n()
const store = useDataStore()
const route = useRoute()
const experimentId = computed(() => {
  const v = route.query.experiment_id
  return typeof v === 'string' && v ? v : undefined
})

onMounted(async () => {
  try {
    await store.fetchStatsOnce(experimentId.value)
  } catch (e: unknown) {
    showApiError(e, t('data.aiFailed'))
  }
})
watch(experimentId, () => {
  void store.fetchStats(experimentId.value)
})

const stats = computed(() => store.stats)
const winRows = computed(() => stats.value?.ai_win_rates ?? [])
const tokenByModel = computed(() => stats.value?.tokens_by_model ?? {})
const responseByModel = computed(() => stats.value?.response_time_by_model ?? {})

const tokenNames = computed(() => Object.keys(tokenByModel.value))
const responseNames = computed(() => Object.keys(responseByModel.value))

const columns = computed(
  (): TableColumn<ModelWinRate & Record<string, unknown>>[] => [
    { key: 'model', label: t('data.colModel') },
    { key: 'games', label: t('data.colGames') },
    { key: 'wins', label: t('data.colWins') },
    {
      key: 'win_rate',
      label: t('data.winRate'),
      render: (row) => formatPercentage(row.win_rate as number),
    },
  ],
)

function barOption(
  names: string[],
  values: number[],
  seriesName: string,
  color: string,
  yAxis: { max?: number; name?: string; percent?: boolean },
): Record<string, unknown> {
  return {
    tooltip: {
      trigger: 'axis',
      valueFormatter: yAxis.percent
        ? (v: unknown) => `${(Number(v) * 100).toFixed(1)}%`
        : undefined,
    },
    grid: { left: 52, right: 16, top: 28, bottom: 56 },
    xAxis: {
      type: 'category',
      data: names,
      axisLabel: { rotate: 20 },
    },
    yAxis: {
      type: 'value',
      max: yAxis.max,
      name: yAxis.name,
      axisLabel: yAxis.percent
        ? { formatter: (v: number) => `${(v * 100).toFixed(0)}%` }
        : undefined,
    },
    series: [
      {
        name: seriesName,
        type: 'bar',
        barMaxWidth: 48,
        data: values,
        itemStyle: { color },
      },
    ],
  }
}

const winRateOption = computed(() =>
  barOption(
    winRows.value.map((r) => r.model),
    winRows.value.map((r) => r.win_rate),
    t('data.winRate'),
    INK_PRIMARY,
    { max: 1, percent: true },
  ),
)

const tokensOption = computed(() =>
  barOption(
    tokenNames.value,
    tokenNames.value.map((n) => tokenByModel.value[n] ?? 0),
    'Token',
    INK_PRIMARY,
    { name: 'tokens' },
  ),
)

const latencyOption = computed(() =>
  barOption(
    responseNames.value,
    responseNames.value.map((n) => responseByModel.value[n] ?? 0),
    t('data.avgResponse'),
    INK_ACCENT,
    { name: 'ms' },
  ),
)

const tableRows = computed(() =>
  winRows.value.map((r) => ({ ...r }) as ModelWinRate & Record<string, unknown>),
)
</script>

<template>
  <div class="relative min-h-[120px] space-y-6">
    <UiSpinner v-if="store.statsLoading" overlay :label="t('common.loading')" />

    <section v-if="stats" class="ink-card">
      <h3 class="mb-4 text-base font-semibold text-ink-text">{{ t('data.latency') }}</h3>
      <div class="grid grid-cols-2 gap-4 md:grid-cols-3">
        <div>
          <div class="text-xl font-semibold text-ink-text">
            {{ Math.round(stats.p50_response_ms) }}
          </div>
          <div class="text-xs text-ink-text-muted">{{ t('data.p50') }}</div>
        </div>
        <div>
          <div class="text-xl font-semibold text-ink-text">
            {{ Math.round(stats.p95_response_ms) }}
          </div>
          <div class="text-xs text-ink-text-muted">{{ t('data.p95') }}</div>
        </div>
        <div>
          <div class="text-xl font-semibold text-ink-text">
            {{ Math.round(stats.avg_response_time_ms) }}
          </div>
          <div class="text-xs text-ink-text-muted">{{ t('data.avgResponseMs') }}</div>
        </div>
      </div>
    </section>

    <section class="ink-card">
      <h3 class="mb-1 text-base font-semibold text-ink-text">{{ t('data.modelWinRate') }}</h3>
      <p class="mb-4 text-xs text-ink-text-muted">{{ t('data.modelWinHint') }}</p>
      <div v-if="winRows.length" class="h-72 w-full">
        <VChart class="h-full w-full" :option="winRateOption" autoresize />
      </div>
      <div v-else class="py-12 text-center text-ink-text-muted">{{ t('data.noWinRate') }}</div>
      <div class="mt-4">
        <UiTable
          :columns="columns"
          :rows="tableRows"
          row-key="model"
          :empty-text="t('data.noModelGames')"
        />
      </div>
    </section>

    <div class="grid gap-6 md:grid-cols-2">
      <section class="ink-card">
        <h3 class="mb-1 text-base font-semibold text-ink-text">{{ t('data.tokensByModel') }}</h3>
        <p class="mb-4 text-xs text-ink-text-muted">{{ t('data.tokensHint') }}</p>
        <div v-if="tokenNames.length" class="h-56 w-full">
          <VChart class="h-full w-full" :option="tokensOption" autoresize />
        </div>
        <div v-else class="flex h-56 items-center justify-center text-ink-text-muted">
          {{ t('data.noTokens') }}
        </div>
      </section>

      <section class="ink-card">
        <h3 class="mb-1 text-base font-semibold text-ink-text">{{ t('data.latencyByModel') }}</h3>
        <p class="mb-4 text-xs text-ink-text-muted">{{ t('data.latencyHint') }}</p>
        <div v-if="responseNames.length" class="h-56 w-full">
          <VChart class="h-full w-full" :option="latencyOption" autoresize />
        </div>
        <div v-else class="flex h-56 items-center justify-center text-ink-text-muted">
          {{ t('data.noLatency') }}
        </div>
      </section>
    </div>
  </div>
</template>
