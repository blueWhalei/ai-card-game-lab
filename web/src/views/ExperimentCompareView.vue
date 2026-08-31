<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  experimentApi,
  type Experiment,
  type ExperimentCompareRow,
} from '@/api/experimentApi'
import { experimentConfigApi, type ExperimentConfig } from '@/api/experimentConfigApi'
import { showApiError } from '@/utils/error'
import { formatWinRate, formatWinRateCi } from '@/utils/experimentWorkbench'
import UiButton from '@/components/ui/Button.vue'
import UiCheckbox from '@/components/ui/Checkbox.vue'
import UiSpinner from '@/components/ui/Spinner.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const loading = ref(true)
const comparing = ref(false)
const experiments = ref<Experiment[]>([])
const configs = ref<ExperimentConfig[]>([])
const selectedIds = ref<string[]>([])
const rows = ref<ExperimentCompareRow[]>([])

function configName(id: string): string {
  return configs.value.find((c) => c.id === id)?.name ?? id
}

const canCompare = computed(
  () => selectedIds.value.length >= 2 && selectedIds.value.length <= 5,
)

function toggleId(id: string, checked: boolean): void {
  if (checked) {
    if (selectedIds.value.includes(id) || selectedIds.value.length >= 5) return
    selectedIds.value = [...selectedIds.value, id]
    return
  }
  selectedIds.value = selectedIds.value.filter((x) => x !== id)
}

function idsFromQuery(): string[] {
  const raw = route.query.ids
  if (typeof raw !== 'string' || !raw) return []
  return raw.split(',').map((s) => s.trim()).filter(Boolean)
}

async function runCompare(ids: string[]): Promise<void> {
  if (ids.length < 2) {
    rows.value = []
    return
  }
  comparing.value = true
  try {
    const res = await experimentApi.compare(ids)
    rows.value = res.data.experiments
  } catch (e: unknown) {
    showApiError(e, t('compare.failed'))
    rows.value = []
  } finally {
    comparing.value = false
  }
}

async function submit(): Promise<void> {
  const ids = selectedIds.value
  void router.replace({ query: { ids: ids.join(',') } })
  await runCompare(ids)
}

onMounted(async () => {
  loading.value = true
  try {
    const [expRes, cfgRes] = await Promise.all([
      experimentApi.list(),
      experimentConfigApi.list(),
    ])
    experiments.value = expRes.data ?? []
    configs.value = cfgRes.data ?? []
    const fromQuery = idsFromQuery()
    selectedIds.value =
      fromQuery.length >= 2 ? fromQuery : experiments.value.slice(0, 2).map((e) => e.id)
    if (selectedIds.value.length >= 2) {
      await runCompare(selectedIds.value)
    }
  } catch (e: unknown) {
    showApiError(e, t('experiment.loadFailed'))
  } finally {
    loading.value = false
  }
})

watch(
  () => route.query.ids,
  (ids) => {
    if (typeof ids === 'string' && ids && ids !== selectedIds.value.join(',')) {
      selectedIds.value = ids.split(',').map((s) => s.trim()).filter(Boolean)
    }
  },
)
</script>

<template>
  <div class="page-container space-y-6">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <button
          type="button"
          class="mb-2 inline-flex items-center gap-1 text-sm text-ink-text-muted hover:text-ink-text"
          @click="router.push('/')"
        >
          {{ t('compare.back') }}
        </button>
        <h1 class="page-title mb-1">{{ t('compare.title') }}</h1>
        <p class="page-subtitle mb-0 mt-0">
          {{ t('compare.subtitle') }}
        </p>
      </div>
      <UiButton :disabled="!canCompare" :loading="comparing" @click="submit">
        {{ t('compare.submit') }}
      </UiButton>
    </div>

    <div v-if="loading" class="flex justify-center py-16">
      <UiSpinner />
    </div>

    <template v-else>
      <section class="space-y-2">
        <div class="flex items-center justify-between">
          <h2 class="text-sm font-semibold text-ink-text">{{ t('compare.pickRange') }}</h2>
          <span class="text-xs text-ink-text-muted">{{ selectedIds.length }}/5</span>
        </div>
        <div
          v-if="experiments.length === 0"
          class="rounded-ink border border-dashed border-ink-border px-4 py-8 text-center text-sm text-ink-text-muted"
        >
          {{ t('compare.empty') }}
        </div>
        <div v-else class="max-h-56 space-y-2 overflow-y-auto rounded-ink-md border border-ink-border p-3">
          <label
            v-for="exp in experiments"
            :key="exp.id"
            class="flex items-start gap-2 rounded-ink px-2 py-1.5 hover:bg-ink-surface-muted"
          >
            <UiCheckbox
              :model-value="selectedIds.includes(exp.id)"
              :disabled="!selectedIds.includes(exp.id) && selectedIds.length >= 5"
              class="mt-0.5"
              @update:model-value="(v) => toggleId(exp.id, Boolean(v))"
            />
            <span class="min-w-0 flex-1">
              <span class="block text-sm font-medium text-ink-text">{{ exp.name }}</span>
              <span class="text-xs text-ink-text-muted">
                {{
                  t('compare.gamesUsable', {
                    finished: exp.summary.finished_games,
                    target: exp.summary.target_games,
                    n: exp.summary.train_usable_decisions,
                  })
                }}
              </span>
            </span>
          </label>
        </div>
      </section>

      <div v-if="comparing" class="flex justify-center py-8">
        <UiSpinner />
      </div>

      <section v-else-if="rows.length > 0" class="space-y-4">
        <div class="overflow-x-auto rounded-ink-md border border-ink-border">
          <table class="w-full min-w-[48rem] text-left text-sm">
            <thead class="bg-ink-surface-muted text-ink-text-muted">
              <tr>
                <th class="px-3 py-2 font-medium">{{ t('compare.colExperiment') }}</th>
                <th class="px-3 py-2 font-medium">{{ t('compare.colFinished') }}</th>
                <th class="px-3 py-2 font-medium">{{ t('compare.colAvgResponse') }}</th>
                <th class="px-3 py-2 font-medium">Token</th>
                <th class="px-3 py-2 font-medium">{{ t('compare.colTrainRate') }}</th>
                <th class="px-3 py-2 font-medium">{{ t('compare.colParser') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in rows"
                :key="row.id"
                class="border-t border-ink-border bg-ink-surface"
              >
                <td class="px-3 py-2">
                  <button
                    type="button"
                    class="font-medium text-ink-primary hover:underline"
                    @click="router.push(`/experiments/${row.id}`)"
                  >
                    {{ row.name }}
                  </button>
                </td>
                <td class="px-3 py-2 tabular-nums">
                  {{
                    t('compare.finishedWinners', {
                      finished: row.finished_games,
                      winners: row.games_with_winner,
                    })
                  }}
                </td>
                <td class="px-3 py-2 tabular-nums">
                  {{ row.avg_response_time_ms ? `${Math.round(row.avg_response_time_ms)}ms` : t('common.dash') }}
                </td>
                <td class="px-3 py-2 tabular-nums">{{ row.total_tokens || t('common.dash') }}</td>
                <td class="px-3 py-2 tabular-nums">{{ formatWinRate(row.train_usable_rate) }}</td>
                <td class="px-3 py-2 tabular-nums">{{ formatWinRate(row.parser_success_rate) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div
          v-for="row in rows"
          :key="`${row.id}-players`"
          class="overflow-x-auto rounded-ink-md border border-ink-border"
        >
          <h3 class="border-b border-ink-border bg-ink-surface-muted px-3 py-2 text-sm font-semibold">
            {{ t('compare.playerWinRate', { name: row.name }) }}
          </h3>
          <table class="w-full min-w-[32rem] text-left text-sm">
            <thead class="text-ink-text-muted">
              <tr>
                <th class="px-3 py-2 font-medium">{{ t('compare.colPlayer') }}</th>
                <th class="px-3 py-2 font-medium">{{ t('compare.colWins') }}</th>
                <th class="px-3 py-2 font-medium">{{ t('compare.colWinRate') }}</th>
                <th class="px-3 py-2 font-medium">{{ t('compare.colCi') }}</th>
                <th class="px-3 py-2 font-medium">{{ t('compare.colTrainable') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="stat in row.player_stats"
                :key="stat.player_id"
                class="border-t border-ink-border"
              >
                <td class="px-3 py-2">{{ configName(stat.player_id) }}</td>
                <td class="px-3 py-2 tabular-nums">{{ stat.wins }}</td>
                <td class="px-3 py-2 tabular-nums">{{ formatWinRate(stat.win_rate) }}</td>
                <td class="px-3 py-2 tabular-nums">{{ formatWinRateCi(stat.win_rate_ci) }}</td>
                <td class="px-3 py-2 tabular-nums">{{ stat.train_usable_decisions }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>
