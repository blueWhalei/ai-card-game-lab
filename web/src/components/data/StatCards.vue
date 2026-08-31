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
      <section class="ink-card">
        <h3 class="mb-4 text-sm font-semibold text-ink-text">{{ t('data.scale') }}</h3>
        <div class="grid grid-cols-2 gap-4 md:grid-cols-4">
          <div>
            <div class="text-2xl font-semibold text-ink-text">{{ stats.total_games }}</div>
            <div class="text-xs text-ink-text-muted">{{ t('data.totalGames') }}</div>
          </div>
          <div>
            <div class="text-2xl font-semibold text-ink-text">{{ stats.total_rounds }}</div>
            <div class="text-xs text-ink-text-muted">{{ t('data.totalRounds') }}</div>
          </div>
          <div>
            <div class="text-2xl font-semibold text-ink-text">
              {{ Math.round(stats.avg_response_time_ms) }}
            </div>
            <div class="text-xs text-ink-text-muted">{{ t('data.avgResponseMs') }}</div>
          </div>
          <div>
            <div class="text-2xl font-semibold text-ink-text">
              {{ Object.keys(stats.games_by_type || {}).length }}
            </div>
            <div class="text-xs text-ink-text-muted">{{ t('data.gameKinds') }}</div>
          </div>
        </div>
      </section>

      <section class="ink-card">
        <h3 class="mb-4 text-sm font-semibold text-ink-text">{{ t('data.tokenUsage') }}</h3>
        <div class="grid grid-cols-2 gap-4 md:grid-cols-4">
          <div>
            <div class="text-xl font-semibold text-ink-text">
              {{ stats.total_tokens.toLocaleString() }}
            </div>
            <div class="text-xs text-ink-text-muted">{{ t('data.totalTokens') }}</div>
          </div>
          <div>
            <div class="text-xl font-semibold text-ink-text">
              {{ stats.total_prompt_tokens.toLocaleString() }}
            </div>
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
                stats.total_rounds ? Math.round(stats.total_tokens / stats.total_rounds) : 0
              }}
            </div>
            <div class="text-xs text-ink-text-muted">{{ t('data.avgTokensRound') }}</div>
          </div>
        </div>
      </section>

      <section class="ink-card">
        <h3 class="mb-4 text-sm font-semibold text-ink-text">{{ t('data.completion') }}</h3>
        <div class="mb-4 grid grid-cols-2 gap-4 md:grid-cols-3">
          <div>
            <div class="text-xl font-semibold text-ink-text">
              {{ stats.avg_game_rounds.toFixed(1) }}
            </div>
            <div class="text-xs text-ink-text-muted">{{ t('data.avgRounds') }}</div>
          </div>
          <div>
            <div class="text-xl font-semibold text-ink-text">{{ stats.games_with_winner }}</div>
            <div class="text-xs text-ink-text-muted">{{ t('data.decidedGames') }}</div>
          </div>
          <div>
            <div class="text-xl font-semibold text-ink-text">
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
