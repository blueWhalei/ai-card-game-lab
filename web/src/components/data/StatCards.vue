<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { useDataStore } from '@/stores/useDataStore'
import { showApiError } from '@/utils/error'
import KpiStrip from '@/components/common/KpiStrip.vue'
import type { KpiItem } from '@/components/common/KpiStrip.vue'
import UiSpinner from '@/components/ui/Spinner.vue'

use([CanvasRenderer, PieChart, TooltipComponent, LegendComponent])

const { t } = useI18n()
const store = useDataStore()
const route = useRoute()
const experimentId = computed(() => {
  const v = route.query.experiment_id
  return typeof v === 'string' && v ? v : undefined
})

async function loadStats(): Promise<void> {
  try {
    await store.fetchStatsOnce(experimentId.value)
  } catch (e: unknown) {
    showApiError(e, t('data.statsFailed'))
  }
}

onMounted(() => {
  void loadStats()
})
watch(experimentId, () => {
  void store.fetchStats(experimentId.value)
})

const stats = computed(() => store.stats)

const hasWinsByRole = computed(() => Object.keys(stats.value?.wins_by_role ?? {}).length > 0)

const roleLabels = computed((): Record<string, string> => ({
  landlord: t('game.landlord'),
  peasant: t('game.peasant'),
  no_bid: t('game.noBid'),
}))

const corpusKpis = computed((): KpiItem[] => {
  const s = stats.value
  if (!s) return []
  return [
    { id: 'games', label: t('data.totalGames'), value: String(s.total_games) },
    { id: 'rounds', label: t('data.totalRounds'), value: String(s.total_rounds) },
    {
      id: 'tokens',
      label: t('data.totalTokens'),
      value: s.total_tokens.toLocaleString(),
    },
    {
      id: 'avgMs',
      label: t('data.avgResponseMs'),
      value: String(Math.round(s.avg_response_time_ms)),
    },
  ]
})

const winsByRoleOption = computed(() => {
  const data = stats.value?.wins_by_role ?? {}
  const labels = roleLabels.value
  return {
    tooltip: {
      trigger: 'item',
      formatter: t('data.pieGames', { b: '{b}', c: '{c}', d: '{d}' }),
    },
    legend: { bottom: 0 },
    series: [
      {
        type: 'pie',
        radius: '62%',
        center: ['50%', '42%'],
        data: Object.entries(data).map(([name, value]) => ({
          name: labels[name] ?? name,
          value,
        })),
      },
    ],
  }
})
</script>

<template>
  <div class="relative min-h-[120px] space-y-6">
    <UiSpinner v-if="store.statsLoading" overlay :label="t('common.loading')" />

    <div v-if="!stats && !store.statsLoading" class="py-12 text-center text-ink-text-muted">
      {{ t('data.noStats') }}
    </div>

    <template v-else-if="stats">
      <KpiStrip :items="corpusKpis" class="md:!grid-cols-4" />

      <section class="ink-card">
        <h3 class="mb-4 text-sm font-semibold text-ink-text">{{ t('data.completion') }}</h3>
        <div class="mb-4 grid grid-cols-2 gap-4 md:grid-cols-3">
          <div>
            <div class="text-xl font-semibold tabular-nums text-ink-text">
              {{ stats.avg_game_rounds.toFixed(1) }}
            </div>
            <div class="text-xs text-ink-text-muted">{{ t('data.avgRounds') }}</div>
          </div>
          <div>
            <div class="text-xl font-semibold tabular-nums text-ink-text">
              {{ stats.games_with_winner }}
            </div>
            <div class="text-xs text-ink-text-muted">{{ t('data.decidedGames') }}</div>
          </div>
          <div>
            <div class="text-xl font-semibold tabular-nums text-ink-text">
              {{
                stats.total_games
                  ? ((stats.games_with_winner / stats.total_games) * 100).toFixed(1)
                  : 0
              }}%
            </div>
            <div class="text-xs text-ink-text-muted">{{ t('data.decidedRate') }}</div>
          </div>
        </div>
        <h4 class="mb-2 text-xs font-medium text-ink-text-secondary">{{ t('data.roleDist') }}</h4>
        <div v-if="hasWinsByRole" class="h-56 w-full max-w-md">
          <VChart class="h-full w-full" :option="winsByRoleOption" autoresize />
        </div>
        <div v-else class="flex h-32 items-center text-ink-text-muted">{{ t('data.noRoleDist') }}</div>
      </section>
    </template>
  </div>
</template>
