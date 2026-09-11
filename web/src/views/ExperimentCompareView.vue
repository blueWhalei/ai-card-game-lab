<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Icon } from '@iconify/vue'
import {
  experimentApi,
  isBenchmarkExperiment,
  type Experiment,
  type ExperimentCompareRow,
  type ExperimentPairedSummary,
  type ExperimentCompareResult,
  type ComparisonSnapshot,
  type ComparisonSnapshotSummary,
} from '@/api/experimentApi'
import { experimentConfigApi, type ExperimentConfig } from '@/api/experimentConfigApi'
import { showApiError } from '@/utils/error'
import {
  formatWinRate,
  formatWinRateCi,
  EXPERIMENT_SCENARIO_IDS,
} from '@/utils/experimentWorkbench'
import { formatExperimentProgress } from '@/utils/experimentStage'
import {
  compareMetricsForEngine,
  formatDelta,
  metricUnit,
  type CompareMetricDef,
} from '@/utils/compareMatrix'
import { systemApi } from '@/api/systemApi'
import { defaultEngineId, engineById, type EngineInfo } from '@/utils/engineSlots'
import ComparisonResearch from '@/components/experiment/ComparisonResearch.vue'
import ComparisonAudit from '@/components/experiment/ComparisonAudit.vue'
import UiInput from '@/components/ui/Input.vue'
import { downloadJson } from '@/utils/jsonFile'
import UiButton from '@/components/ui/Button.vue'
import UiBadge from '@/components/ui/Badge.vue'
import UiSpinner from '@/components/ui/Spinner.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const loading = ref(true)
const comparing = ref(false)
const experiments = ref<Experiment[]>([])
const configs = ref<ExperimentConfig[]>([])
const engines = ref<EngineInfo[]>([])
const selectedIds = ref<string[]>([])
const rows = ref<ExperimentCompareRow[]>([])
const pairedSummary = ref<ExperimentPairedSummary | null>(null)
const result = ref<ExperimentCompareResult | null>(null)
const allowedChanges = ref<string[]>([])
const snapshot = ref<ComparisonSnapshot | null>(null)
const snapshots = ref<ComparisonSnapshotSummary[]>([])
const moreSnapshots = ref(false)
const snapshotTitle = ref('')
const saving = ref(false)
let requestVersion = 0
const dirty = computed(
  () =>
    rows.value.map((r) => r.id).join(',') !== selectedIds.value.join(',') ||
    JSON.stringify([...(result.value?.protocol_review?.allowed_changes ?? [])].sort()) !==
      JSON.stringify([...allowedChanges.value].sort()),
)
function applyResult(data: ExperimentCompareResult) {
  result.value = data
  rows.value = data.experiments
  pairedSummary.value = data.paired_summary ?? null
}
async function loadSnapshots(append = false) {
  try {
    const res = await experimentApi.listComparisons(append ? snapshots.value.length : 0)
    snapshots.value = append ? [...snapshots.value, ...res.data] : res.data
    moreSnapshots.value = res.data.length === 30
  } catch (e) {
    showApiError(e, t('compare.audit.loadFailed'))
  }
}
async function openSnapshot(id: string) {
  const version = ++requestVersion
  comparing.value = true
  try {
    const res = await experimentApi.getComparison(id)
    if (version !== requestVersion) return
    snapshot.value = res.data
    applyResult(res.data.result)
    selectedIds.value = res.data.result.experiments.map((r) => r.id)
    allowedChanges.value = [...(res.data.result.protocol_review?.allowed_changes ?? [])]
    snapshotTitle.value = res.data.title
    await router.replace({ query: { snapshot: id } })
  } catch (e) {
    showApiError(e, t('compare.audit.loadFailed'))
  } finally {
    if (version === requestVersion) comparing.value = false
  }
}
async function saveSnapshot() {
  if (!canCompare.value || dirty.value || !snapshotTitle.value.trim() || saving.value) return
  saving.value = true
  const version = ++requestVersion
  try {
    const res = await experimentApi.saveComparison(
      [...selectedIds.value],
      snapshotTitle.value.trim(),
      [...allowedChanges.value],
    )
    if (version !== requestVersion) return
    snapshot.value = res.data
    applyResult(res.data.result)
    await router.replace({ query: { snapshot: res.data.id } })
    await loadSnapshots()
  } catch (e) {
    showApiError(e, t('compare.audit.saveFailed'))
  } finally {
    saving.value = false
  }
}

const playerMatrixMode = ref<'win_rate' | 'paired_wins'>('win_rate')

const activeEngine = computed(() => {
  const gt = rows.value[0]?.game_type ?? experiments.value[0]?.game_type
  if (gt) return engineById(engines.value, gt)
  return engineById(engines.value, defaultEngineId(engines.value))
})

const visibleMetrics = computed(() =>
  compareMetricsForEngine(activeEngine.value?.eval_metric_ids ?? []),
)

function configName(id: string): string {
  return configs.value.find((c) => c.id === id)?.name ?? id
}

const canCompare = computed(() => selectedIds.value.length >= 2 && selectedIds.value.length <= 5)

function toggleId(id: string): void {
  if (saving.value) return
  if (selectedIds.value.includes(id)) {
    selectedIds.value = selectedIds.value.filter((x) => x !== id)
    return
  }
  if (selectedIds.value.length >= 5) return
  selectedIds.value = [...selectedIds.value, id]
}

function idsFromQuery(): string[] {
  const raw = route.query.ids
  if (typeof raw !== 'string' || !raw) return []
  return raw
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
}

async function runCompare(ids: string[]): Promise<void> {
  if (ids.length < 2) {
    rows.value = []
    result.value = null
    pairedSummary.value = null
    return
  }
  const version = ++requestVersion
  comparing.value = true
  try {
    const res = await experimentApi.compare(ids, [...allowedChanges.value])
    if (version !== requestVersion) return
    snapshot.value = null
    applyResult(res.data)
  } catch (e: unknown) {
    if (version !== requestVersion) return
    showApiError(e, t('compare.failed'))
    result.value = null
    rows.value = []
    pairedSummary.value = null
  } finally {
    if (version === requestVersion) comparing.value = false
  }
}

async function submit(): Promise<void> {
  const ids = [...selectedIds.value]
  void router.replace({ query: { ids: ids.join(',') } })
  await runCompare(ids)
}

function metricLabel(id: string): string {
  const map: Record<string, string> = {
    finished: t('compare.colFinished'),
    landlord: t('compare.colLandlordWinRate'),
    pairedLandlord: t('compare.colPairedLandlord'),
    pairedN: t('compare.colPaired'),
    p50: t('compare.colP50'),
    p95: t('compare.colP95'),
    tokens: t('compare.colTokensPerGame'),
    train: t('compare.colTrainRate'),
    parser: t('compare.colParser'),
  }
  return map[id] ?? id
}

function cellFor(
  row: ExperimentCompareRow,
  metric: CompareMetricDef,
): {
  value: number | null
  display: string
} {
  const dash = t('common.dash')
  switch (metric.id) {
    case 'finished':
      return { value: row.finished_games, display: String(row.finished_games) }
    case 'landlord': {
      if ((row.decisive_games ?? 0) <= 0) return { value: null, display: dash }
      const rate = formatWinRate(row.landlord_win_rate ?? 0)
      const ci = formatWinRateCi(row.landlord_win_rate_ci)
      const n = row.decisive_games ?? row.credibility?.decisive_n
      const parts = [rate]
      if (ci !== '—') parts.push(ci)
      if (n != null) parts.push(`n=${n}`)
      return {
        value: row.landlord_win_rate ?? 0,
        display: parts.join(' · '),
      }
    }
    case 'pairedN':
      return {
        value: row.paired_n ?? 0,
        display: String(row.paired_n ?? 0),
      }
    case 'pairedLandlord': {
      if ((row.paired_n ?? 0) <= 0) return { value: null, display: dash }
      const rate = formatWinRate(row.paired_landlord_win_rate ?? 0)
      return {
        value: row.paired_landlord_win_rate ?? 0,
        display: `${rate} · n=${row.paired_n}`,
      }
    }
    case 'p50':
      return (row.p50_response_ms ?? 0) > 0
        ? {
            value: row.p50_response_ms ?? 0,
            display: `${Math.round(row.p50_response_ms ?? 0)}ms`,
          }
        : { value: null, display: dash }
    case 'p95':
      return (row.p95_response_ms ?? 0) > 0
        ? {
            value: row.p95_response_ms ?? 0,
            display: `${Math.round(row.p95_response_ms ?? 0)}ms`,
          }
        : { value: null, display: dash }
    case 'tokens':
      return (row.tokens_per_game ?? 0) > 0
        ? {
            value: row.tokens_per_game ?? 0,
            display: String(Math.round(row.tokens_per_game ?? 0)),
          }
        : { value: null, display: dash }
    case 'train':
      return {
        value: row.train_usable_rate,
        display: formatWinRate(row.train_usable_rate),
      }
    case 'parser':
      return {
        value: row.parser_success_rate,
        display: formatWinRate(row.parser_success_rate),
      }
    default:
      return { value: null, display: dash }
  }
}

type MatrixRow = {
  metric: CompareMetricDef
  label: string
  cells: Array<{
    display: string
    delta: string | null
  }>
}

const matrixRows = computed((): MatrixRow[] => {
  if (rows.value.length === 0) return []
  return visibleMetrics.value.map((metric) => {
    const raw = rows.value.map((row) => cellFor(row, metric))
    const referenceValue = raw[0]?.value ?? null
    const unit = metricUnit(metric.id)
    return {
      metric,
      label: metricLabel(metric.id),
      cells: raw.map((c) => ({
        display: c.display,
        delta: formatDelta(c.value, referenceValue, unit),
      })),
    }
  })
})

function scenarioLabel(id: string): string {
  const map: Record<string, string> = {
    bidding: t('experiment.scenarioBidding'),
    playing: t('experiment.scenarioPlaying'),
    endgame: t('experiment.scenarioEndgame'),
    bomb: t('experiment.scenarioBomb'),
  }
  return map[id] ?? id
}

const showScenarioMatrix = computed(() =>
  rows.value.some((row) =>
    EXPERIMENT_SCENARIO_IDS.some((id) => (row.scenario_scores?.[id]?.n ?? 0) > 0),
  ),
)

const scenarioMatrixRows = computed((): MatrixRow[] => {
  if (!showScenarioMatrix.value) return []
  return EXPERIMENT_SCENARIO_IDS.map((id) => {
    const raw = rows.value.map((row) => {
      const score = row.scenario_scores?.[id]
      const n = score?.n ?? 0
      if (n <= 0) return { value: null as number | null, display: t('common.dash') }
      const train = formatWinRate(score?.train_usable_rate ?? 0)
      const parser =
        (score?.parser_n ?? 0) > 0
          ? formatWinRate(score?.parser_success_rate ?? 0)
          : t('common.dash')
      return {
        value: score?.train_usable_rate ?? 0,
        display: `${train} · n=${n} · ${t('compare.colParser')} ${parser}`,
      }
    })
    const referenceValue = raw[0]?.value ?? null
    return {
      metric: { id: `scenario-${id}`, kind: 'higher' as const },
      label: scenarioLabel(id),
      cells: raw.map((c) => ({
        display: c.display,
        delta: formatDelta(c.value, referenceValue, 'rate'),
      })),
    }
  })
})

const playerIds = computed(() => {
  const ids = new Set<string>()
  for (const row of rows.value) {
    for (const stat of row.player_stats) ids.add(stat.player_id)
  }
  return [...ids]
})

type PlayerMatrixRow = {
  playerId: string
  name: string
  cells: Array<{ display: string }>
}

const playerMatrix = computed((): PlayerMatrixRow[] => {
  return playerIds.value.map((pid) => {
    const rates = rows.value.map((row) => {
      const stat = row.player_stats.find((s) => s.player_id === pid)
      if (!stat) return null
      if (playerMatrixMode.value === 'paired_wins') {
        if ((row.paired_n ?? 0) <= 0) return null
        const wins = stat.paired_wins ?? 0
        return { value: wins, display: String(wins) }
      }
      if (row.games_with_winner <= 0) return null
      return { value: stat.win_rate, display: formatWinRate(stat.win_rate) }
    })
    return {
      playerId: pid,
      name: configName(pid),
      cells: rates.map((r) => ({
        display: r?.display ?? t('common.dash'),
      })),
    }
  })
})

const pairedDiffDisplay = computed((): string | null => {
  const ps = pairedSummary.value
  if (!ps || ps.landlord_win_rate_diff == null) return null
  const sign = ps.landlord_win_rate_diff >= 0 ? '+' : ''
  const pp = (ps.landlord_win_rate_diff * 100).toFixed(1)
  return t('compare.pairedDiff', {
    diff: `${sign}${pp}`,
    n: ps.shared_seeds,
  })
})

async function resolveInitialIds(): Promise<string[]> {
  const fromQuery = idsFromQuery()
  if (fromQuery.length >= 2) return fromQuery

  const fromExpId = route.query.from
  if (typeof fromExpId === 'string' && fromExpId) {
    try {
      const res = await experimentApi.get(fromExpId)
      const suggested = res.data.validation?.suggested_compare_ids ?? []
      if (suggested.length >= 2) return suggested
    } catch {
      /* fall through */
    }
  }
  return experiments.value.slice(0, 2).map((e) => e.id)
}

const showLowPowerHint = computed(
  () =>
    rows.value.some((r) => r.credibility?.low_power === true) ||
    pairedSummary.value?.low_power === true,
)

onMounted(async () => {
  loading.value = true
  try {
    const [expRes, cfgRes, engineRes] = await Promise.all([
      experimentApi.list(),
      experimentConfigApi.list(),
      systemApi.listEngines().catch(() => null),
    ])
    experiments.value = expRes.data ?? []
    configs.value = cfgRes.data ?? []
    engines.value = engineRes?.data ?? []
    await loadSnapshots()
    if (typeof route.query.snapshot === 'string') {
      await openSnapshot(route.query.snapshot)
      return
    }
    selectedIds.value = await resolveInitialIds()
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
      selectedIds.value = ids
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean)
    }
  },
)
</script>

<template>
  <div class="page-container space-y-6">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <button
        type="button"
        class="inline-flex items-center gap-1 text-sm text-ink-text-secondary hover:text-ink-text"
        @click="router.push('/')"
      >
        {{ t('compare.back') }}
      </button>
      <UiButton :disabled="!canCompare || saving" :loading="comparing" @click="submit">
        {{ t('compare.submit') }}
      </UiButton>
    </div>

    <div v-if="loading" class="flex justify-center py-16">
      <UiSpinner :label="t('common.loading')" />
    </div>

    <template v-else>
      <section class="space-y-2">
        <div class="flex items-center justify-between">
          <h2 class="text-sm font-semibold text-ink-text">{{ t('compare.pickRange') }}</h2>
          <span class="text-sm text-ink-text-secondary">{{ selectedIds.length }}/5</span>
        </div>
        <div
          v-if="experiments.length === 0"
          class="rounded-ink border border-dashed border-ink-border px-4 py-8 text-center text-sm text-ink-text-secondary"
        >
          {{ t('compare.empty') }}
        </div>
        <div v-else class="flex flex-wrap gap-2">
          <button
            v-for="exp in experiments"
            :key="exp.id"
            type="button"
            class="inline-flex max-w-full items-center gap-1.5 rounded-ink border px-2.5 py-1.5 text-left text-sm transition-colors"
            :class="
              selectedIds.includes(exp.id)
                ? 'border-ink-primary bg-ink-primary-muted text-ink-primary'
                : 'border-ink-border bg-ink-surface text-ink-text hover:bg-ink-surface-muted'
            "
            :disabled="!selectedIds.includes(exp.id) && selectedIds.length >= 5"
            @click="toggleId(exp.id)"
          >
            <Icon
              :icon="selectedIds.includes(exp.id) ? 'lucide:check' : 'lucide:plus'"
              class="h-3.5 w-3.5 shrink-0"
            />
            <span class="min-w-0 truncate font-medium">{{ exp.name }}</span>
            <span class="shrink-0 text-caption opacity-70">
              {{
                formatExperimentProgress(exp.summary.finished_games, exp.summary.target_games, t)
              }}
            </span>
          </button>
        </div>
      </section>

      <details class="rounded-ink-md border border-ink-border p-4">
        <summary class="cursor-pointer text-body font-medium">
          {{ t('compare.audit.saved') }}
        </summary>
        <p v-if="!snapshots.length" class="mt-3 text-caption text-ink-text-secondary">
          {{ t('compare.audit.noSnapshots') }}
        </p>
        <ul class="mt-3 space-y-2">
          <li v-for="item in snapshots" :key="item.id">
            <UiButton variant="ghost" :disabled="saving || comparing" @click="openSnapshot(item.id)"
              >{{ item.title }} · {{ item.created_at }}</UiButton
            >
          </li>
        </ul>
        <UiButton v-if="moreSnapshots" variant="secondary" @click="loadSnapshots(true)">{{
          t('compare.audit.more')
        }}</UiButton>
      </details>
      <p v-if="dirty && rows.length" role="status" class="text-body text-ink-text-secondary">
        {{ t('compare.audit.dirty') }}
      </p>
      <div v-if="comparing" class="flex justify-center py-8">
        <UiSpinner :label="t('common.loading')" />
      </div>

      <section v-else-if="rows.length > 0" class="space-y-4">
        <ComparisonAudit
          v-if="result"
          :result="result"
          v-model:allowed="allowedChanges"
          :readonly="saving"
        />
        <section class="space-y-3 rounded-ink-md border border-ink-border bg-ink-surface p-4">
          <p v-if="snapshot" class="text-body font-medium">
            {{ t('compare.audit.snapshotAt', { time: snapshot.created_at }) }}
          </p>
          <p class="text-caption text-ink-text-secondary">{{ t('compare.audit.snapshotHint') }}</p>
          <label class="block text-caption"
            >{{ t('compare.audit.name')
            }}<UiInput v-model="snapshotTitle" :maxlength="120" :disabled="saving"
          /></label>
          <div class="flex flex-wrap gap-2">
            <UiButton
              :disabled="dirty || !snapshotTitle.trim() || comparing"
              :loading="saving"
              @click="saveSnapshot"
              >{{ t('compare.audit.save') }}</UiButton
            >
            <UiButton
              v-if="snapshot"
              variant="secondary"
              @click="downloadJson(`comparison-${snapshot.id}.json`, snapshot)"
              >{{ t('compare.audit.export') }}</UiButton
            >
          </div>
        </section>
        <ComparisonResearch
          v-if="snapshot && !dirty"
          :key="snapshot.id"
          :comparison-id="snapshot.id"
        />
        <div
          v-if="pairedDiffDisplay"
          class="rounded-ink-md border border-ink-primary/25 bg-ink-primary-muted/30 px-3 py-2.5 text-sm text-ink-text"
        >
          {{ pairedDiffDisplay }}
          <UiBadge v-if="pairedSummary?.low_power" variant="muted" class="ml-2">
            {{ t('experiment.lowPowerShort') }}
          </UiBadge>
        </div>
        <div
          v-if="showLowPowerHint"
          class="rounded-ink-md border border-ink-border bg-ink-surface-muted/50 px-3 py-2.5 text-sm text-ink-text-secondary"
        >
          {{ t('compare.lowPowerHint') }}
        </div>
        <div class="overflow-x-auto rounded-ink-md border border-ink-border">
          <table class="w-full text-left text-sm">
            <thead class="bg-ink-surface-muted text-ink-text">
              <tr>
                <th class="sticky left-0 z-10 bg-ink-surface-muted px-3 py-2 font-medium">
                  {{ t('compare.colMetric') }}
                </th>
                <th v-for="row in rows" :key="row.id" class="px-3 py-2 font-medium">
                  <div class="flex flex-wrap items-center justify-center gap-1">
                    <button
                      type="button"
                      class="font-medium text-ink-primary hover:underline"
                      @click="router.push(`/experiments/${row.id}`)"
                    >
                      {{ row.name }}
                    </button>
                    <UiBadge v-if="isBenchmarkExperiment(row)" variant="accent" class="text-xs">
                      {{ t('experiment.modeBenchmark') }}
                    </UiBadge>
                  </div>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="mrow in matrixRows"
                :key="mrow.metric.id"
                class="border-t border-ink-border bg-ink-surface"
                :class="mrow.metric.core ? '' : 'hidden xl:table-row'"
              >
                <th
                  class="sticky left-0 z-10 bg-ink-surface px-3 py-1.5 text-left text-xs font-medium whitespace-nowrap text-ink-text-secondary"
                >
                  {{ mrow.label }}
                </th>
                <td
                  v-for="(cell, i) in mrow.cells"
                  :key="`${mrow.metric.id}-${i}`"
                  class="px-3 py-1.5 tabular-nums whitespace-nowrap"
                >
                  <span class="text-ink-text">
                    {{ cell.display }}
                  </span>
                  <span v-if="cell.delta" class="ml-1.5 text-xs text-ink-text-muted">
                    ({{ cell.delta }})
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div
          v-if="showScenarioMatrix"
          class="overflow-x-auto rounded-ink-md border border-ink-border"
        >
          <table class="w-full text-left text-sm">
            <thead class="bg-ink-surface-muted text-ink-text">
              <tr>
                <th class="sticky left-0 z-10 bg-ink-surface-muted px-3 py-2 font-medium">
                  {{ t('compare.scenarioTitle') }}
                </th>
                <th v-for="row in rows" :key="`sc-${row.id}`" class="px-3 py-2 font-medium">
                  {{ row.name }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="mrow in scenarioMatrixRows"
                :key="mrow.metric.id"
                class="border-t border-ink-border bg-ink-surface"
              >
                <th
                  class="sticky left-0 z-10 bg-ink-surface px-3 py-1.5 text-left text-xs font-medium whitespace-nowrap text-ink-text-secondary"
                >
                  {{ mrow.label }}
                </th>
                <td
                  v-for="(cell, i) in mrow.cells"
                  :key="`${mrow.metric.id}-${i}`"
                  class="px-3 py-1.5 tabular-nums whitespace-nowrap"
                >
                  <span class="text-ink-text">
                    {{ cell.display }}
                  </span>
                  <span v-if="cell.delta" class="ml-1.5 text-xs text-ink-text-muted">
                    ({{ cell.delta }})
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <p v-if="rows.some((r) => (r.paired_n ?? 0) > 0)" class="text-sm text-ink-text-secondary">
          {{ t('compare.pairedHint') }}
        </p>

        <details class="group rounded-ink-md border border-ink-border">
          <summary
            class="flex cursor-pointer list-none items-center gap-2 bg-ink-surface-muted px-3 py-2 text-sm font-semibold marker:content-none [&::-webkit-details-marker]:hidden"
          >
            <Icon
              icon="lucide:chevron-right"
              class="h-3.5 w-3.5 shrink-0 text-ink-text-secondary transition-transform group-open:rotate-90"
            />
            {{ t('compare.playerMatrix') }}
          </summary>
          <div class="flex gap-2 border-t border-ink-border px-3 py-2">
            <button
              type="button"
              class="rounded-[6px] px-2.5 py-1 text-xs font-medium"
              :class="
                playerMatrixMode === 'win_rate'
                  ? 'bg-ink-surface text-ink-text shadow-[var(--ink-shadow)]'
                  : 'text-ink-text-secondary hover:text-ink-text'
              "
              @click="playerMatrixMode = 'win_rate'"
            >
              {{ t('compare.colWinRate') }}
            </button>
            <button
              type="button"
              class="rounded-[6px] px-2.5 py-1 text-xs font-medium"
              :class="
                playerMatrixMode === 'paired_wins'
                  ? 'bg-ink-surface text-ink-text shadow-[var(--ink-shadow)]'
                  : 'text-ink-text-secondary hover:text-ink-text'
              "
              @click="playerMatrixMode = 'paired_wins'"
            >
              {{ t('compare.colPairedWins') }}
            </button>
          </div>
          <div class="overflow-x-auto border-t border-ink-border">
            <table class="w-full text-left text-sm">
              <thead class="text-ink-text">
                <tr>
                  <th class="px-3 py-2 font-medium">{{ t('compare.colPlayer') }}</th>
                  <th v-for="row in rows" :key="`p-${row.id}`" class="px-3 py-2 font-medium">
                    {{ row.name }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="prow in playerMatrix"
                  :key="prow.playerId"
                  class="border-t border-ink-border"
                >
                  <td class="px-3 py-1.5 font-medium whitespace-nowrap">{{ prow.name }}</td>
                  <td
                    v-for="(cell, i) in prow.cells"
                    :key="`${prow.playerId}-${i}`"
                    class="px-3 py-1.5 tabular-nums text-ink-text"
                  >
                    {{ cell.display }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </details>
      </section>
    </template>
  </div>
</template>
