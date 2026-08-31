<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { ExperimentSummary } from '@/api/experimentApi'
import { formatWinRate } from '@/utils/experimentWorkbench'

defineProps<{
  summary: ExperimentSummary
  configLabel: (id: string) => string
}>()

const { t } = useI18n()

function formatAvgMs(ms: number, traceCount: number): string {
  if (traceCount <= 0) return t('common.dash')
  return `${Math.round(ms)}ms`
}
</script>

<template>
  <section class="space-y-2">
    <p
      v-if="(summary.total_games ?? 0) === 0"
      class="rounded-ink-md border border-dashed border-ink-border bg-ink-surface px-4 py-6 text-center text-sm text-ink-text-muted"
    >
      {{ t('playersTab.empty') }}
    </p>
    <div v-else class="overflow-x-auto rounded-ink-md border border-ink-border">
      <table class="w-full min-w-[32rem] text-left text-sm">
        <thead class="bg-ink-surface-muted text-ink-text-muted">
          <tr>
            <th class="px-3 py-2 font-medium">{{ t('playersTab.colPlayer') }}</th>
            <th class="px-3 py-2 font-medium">{{ t('playersTab.colWins') }}</th>
            <th class="px-3 py-2 font-medium">{{ t('playersTab.colWinRate') }}</th>
            <th class="px-3 py-2 font-medium">{{ t('playersTab.colUsable') }}</th>
            <th class="px-3 py-2 font-medium">{{ t('playersTab.colAvgResponse') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="stat in summary.player_stats ?? []"
            :key="stat.player_id"
            class="border-t border-ink-border bg-ink-surface"
          >
            <td class="px-3 py-2 font-medium text-ink-text" :title="configLabel(stat.player_id)">
              {{ configLabel(stat.player_id) }}
            </td>
            <td class="px-3 py-2 tabular-nums">{{ stat.wins }}</td>
            <td class="px-3 py-2 tabular-nums">{{ formatWinRate(stat.win_rate) }}</td>
            <td class="px-3 py-2 tabular-nums">{{ stat.train_usable_decisions }}</td>
            <td class="px-3 py-2 tabular-nums">
              {{ formatAvgMs(stat.avg_response_time_ms, stat.trace_count) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
