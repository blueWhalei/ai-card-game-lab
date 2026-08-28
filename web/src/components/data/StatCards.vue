<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { useDataStore } from '@/stores/useDataStore'
import { showApiError } from '@/utils/error'
import UiSpinner from '@/components/ui/Spinner.vue'

use([CanvasRenderer, BarChart, PieChart, GridComponent, TooltipComponent, LegendComponent])

const INK_PRIMARY = '#1a6b5c'
const INK_SUCCESS = '#2d7a4f'
const INK_ACCENT = '#c47a1a'

const store = useDataStore()

onMounted(async () => {
  try {
    await store.fetchStatsOnce()
  } catch (e: unknown) {
    showApiError(e, '加载统计失败')
  }
})

const stats = computed(() => store.stats)

const hasTokensByModel = computed(
  () => Object.keys(stats.value?.tokens_by_model ?? {}).length > 0,
)
const hasWinsByRole = computed(() => Object.keys(stats.value?.wins_by_role ?? {}).length > 0)
const hasModelUsage = computed(() => Object.keys(stats.value?.models_usage ?? {}).length > 0)
const hasWinRates = computed(() => (stats.value?.ai_win_rates ?? []).length > 0)
const hasResponseByModel = computed(
  () => Object.keys(stats.value?.response_time_by_model ?? {}).length > 0,
)

const modelUsageOption = computed(() => {
  const usage = stats.value?.models_usage ?? {}
  const entries = Object.entries(usage)
  return {
    tooltip: { trigger: 'item' },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        data: entries.map(([name, value]) => ({ name, value })),
      },
    ],
  }
})

const tokensByModelOption = computed(() => {
  const data = stats.value?.tokens_by_model ?? {}
  const names = Object.keys(data)
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 16, top: 24, bottom: 40 },
    xAxis: { type: 'category', data: names, axisLabel: { rotate: 30 } },
    yAxis: { type: 'value', name: 'tokens' },
    series: [{ type: 'bar', data: names.map((n) => data[n] ?? 0), itemStyle: { color: INK_PRIMARY } }],
  }
})

const winsByRoleOption = computed(() => {
  const data = stats.value?.wins_by_role ?? {}
  return {
    tooltip: { trigger: 'item' },
    series: [
      {
        type: 'pie',
        radius: '65%',
        data: Object.entries(data).map(([name, value]) => ({ name, value })),
      },
    ],
  }
})

const winRateOption = computed(() => {
  const rows = stats.value?.ai_win_rates ?? []
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 16, top: 24, bottom: 40 },
    xAxis: { type: 'category', data: rows.map((r) => r.model), axisLabel: { rotate: 30 } },
    yAxis: { type: 'value', max: 1, axisLabel: { formatter: (v: number) => `${(v * 100).toFixed(0)}%` } },
    series: [
      {
        type: 'bar',
        data: rows.map((r) => r.win_rate),
        itemStyle: { color: INK_SUCCESS },
      },
    ],
  }
})

const responseByModelOption = computed(() => {
  const data = stats.value?.response_time_by_model ?? {}
  const names = Object.keys(data)
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 16, top: 24, bottom: 40 },
    xAxis: { type: 'category', data: names, axisLabel: { rotate: 30 } },
    yAxis: { type: 'value', name: 'ms' },
    series: [{ type: 'bar', data: names.map((n) => data[n] ?? 0), itemStyle: { color: INK_ACCENT } }],
  }
})
</script>

<template>
  <div class="relative min-h-[120px] space-y-6">
    <UiSpinner v-if="store.statsLoading" overlay label="加载中…" />

    <div v-if="!stats && !store.statsLoading" class="py-12 text-center text-ink-text-muted">
      暂无统计数据
    </div>

    <template v-else-if="stats">
      <section class="ink-card">
        <h3 class="mb-4 text-sm font-semibold text-ink-text">基础统计</h3>
        <div class="grid grid-cols-2 gap-4 md:grid-cols-4">
          <div>
            <div class="text-2xl font-semibold text-ink-text">{{ stats.total_games }}</div>
            <div class="text-xs text-ink-text-muted">总对局</div>
          </div>
          <div>
            <div class="text-2xl font-semibold text-ink-text">{{ stats.total_rounds }}</div>
            <div class="text-xs text-ink-text-muted">总回合</div>
          </div>
          <div>
            <div class="text-2xl font-semibold text-ink-text">
              {{ Math.round(stats.avg_response_time_ms) }}
            </div>
            <div class="text-xs text-ink-text-muted">平均响应 (ms)</div>
          </div>
          <div>
            <div class="text-2xl font-semibold text-ink-text">
              {{ Object.keys(stats.games_by_type || {}).length }}
            </div>
            <div class="text-xs text-ink-text-muted">游戏类型数</div>
          </div>
        </div>
      </section>

      <section class="ink-card">
        <h3 class="mb-4 text-sm font-semibold text-ink-text">Token 用量</h3>
        <div class="mb-4 grid grid-cols-2 gap-4 md:grid-cols-4">
          <div>
            <div class="text-xl font-semibold text-ink-text">{{ stats.total_tokens.toLocaleString() }}</div>
            <div class="text-xs text-ink-text-muted">总 Token</div>
          </div>
          <div>
            <div class="text-xl font-semibold text-ink-text">{{ stats.total_prompt_tokens.toLocaleString() }}</div>
            <div class="text-xs text-ink-text-muted">Prompt</div>
          </div>
          <div>
            <div class="text-xl font-semibold text-ink-text">
              {{ stats.total_completion_tokens.toLocaleString() }}
            </div>
            <div class="text-xs text-ink-text-muted">Completion</div>
          </div>
          <div>
            <div class="text-xl font-semibold text-ink-text">
              {{
                stats.total_rounds
                  ? Math.round(stats.total_tokens / stats.total_rounds)
                  : 0
              }}
            </div>
            <div class="text-xs text-ink-text-muted">每回合均 Token</div>
          </div>
        </div>
        <VChart
          v-if="hasTokensByModel"
          class="h-64 w-full"
          :option="tokensByModelOption"
          autoresize
        />
        <div v-else class="py-12 text-center text-ink-text-muted">暂无按模型 Token 数据</div>
      </section>

      <section class="ink-card">
        <h3 class="mb-4 text-sm font-semibold text-ink-text">对局质量</h3>
        <div class="mb-4 grid grid-cols-2 gap-4 md:grid-cols-3">
          <div>
            <div class="text-xl font-semibold text-ink-text">{{ stats.avg_game_rounds.toFixed(1) }}</div>
            <div class="text-xs text-ink-text-muted">平均回合数</div>
          </div>
          <div>
            <div class="text-xl font-semibold text-ink-text">{{ stats.games_with_winner }}</div>
            <div class="text-xs text-ink-text-muted">有胜者对局</div>
          </div>
          <div>
            <div class="text-xl font-semibold text-ink-text">
              {{
                stats.total_games
                  ? ((stats.games_with_winner / stats.total_games) * 100).toFixed(1)
                  : 0
              }}%
            </div>
            <div class="text-xs text-ink-text-muted">决出胜负率</div>
          </div>
        </div>
        <div class="grid gap-4 md:grid-cols-2">
          <VChart
            v-if="hasWinsByRole"
            class="h-56 w-full"
            :option="winsByRoleOption"
            autoresize
          />
          <div v-else class="flex h-56 items-center justify-center text-ink-text-muted">
            暂无阵营胜负分布
          </div>
          <VChart
            v-if="hasModelUsage"
            class="h-56 w-full"
            :option="modelUsageOption"
            autoresize
          />
          <div v-else class="flex h-56 items-center justify-center text-ink-text-muted">
            暂无模型用量分布
          </div>
        </div>
      </section>

      <section class="ink-card">
        <h3 class="mb-4 text-sm font-semibold text-ink-text">AI 表现 / 响应时间</h3>
        <div class="mb-4 grid grid-cols-2 gap-4">
          <div>
            <div class="text-xl font-semibold text-ink-text">{{ Math.round(stats.p50_response_ms) }}</div>
            <div class="text-xs text-ink-text-muted">P50 响应 (ms)</div>
          </div>
          <div>
            <div class="text-xl font-semibold text-ink-text">{{ Math.round(stats.p95_response_ms) }}</div>
            <div class="text-xs text-ink-text-muted">P95 响应 (ms)</div>
          </div>
        </div>
        <div class="grid gap-4 md:grid-cols-2">
          <VChart v-if="hasWinRates" class="h-56 w-full" :option="winRateOption" autoresize />
          <div v-else class="flex h-56 items-center justify-center text-ink-text-muted">
            暂无 AI 胜率数据
          </div>
          <VChart
            v-if="hasResponseByModel"
            class="h-56 w-full"
            :option="responseByModelOption"
            autoresize
          />
          <div v-else class="flex h-56 items-center justify-center text-ink-text-muted">
            暂无按模型响应时间
          </div>
        </div>
      </section>
    </template>
  </div>
</template>
