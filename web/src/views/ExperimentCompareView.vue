<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
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
import ComparisonOverview from '@/components/experiment/ComparisonOverview.vue'
import UiDialog from '@/components/ui/Dialog.vue'
import UiInput from '@/components/ui/Input.vue'
import { downloadJson } from '@/utils/jsonFile'
import UiButton from '@/components/ui/Button.vue'
import UiBadge from '@/components/ui/Badge.vue'
import HeaderToggles from '@/components/common/HeaderToggles.vue'
import { formatDateTime } from '@/utils/format'
import UiSpinner from '@/components/ui/Spinner.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const panel = ref<'selection' | 'audit' | 'metrics' | 'save' | 'history' | null>(null)
const loading = ref(true)
const comparing = ref(false)
const experiments = ref<Experiment[]>([])
const configs = ref<ExperimentConfig[]>([])
const playerNames = computed(() => Object.fromEntries(configs.value.map((c) => [c.id, c.name])))
const engines = ref<EngineInfo[]>([])
const selectedIds = ref<string[]>([])
const studyId = computed(() => {
  const owners = selectedIds.value.map(
    (id) => experiments.value.find((run) => run.id === id)?.study_id,
  )
  return owners.length && owners[0] && owners.every((owner) => owner === owners[0])
    ? owners[0]
    : null
})
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
  allowedChanges.value = [...(data.protocol_review?.allowed_changes ?? [])]
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
    if (res.data.result.metric_version !== 'paired-cohort-v5') {
      showApiError(null, t('compare.audit.unsupportedVersion'))
      return
    }
    snapshot.value = res.data
    applyResult(res.data.result)
    selectedIds.value = res.data.result.experiments.map((r) => r.id)
    allowedChanges.value = [...(res.data.result.protocol_review?.allowed_changes ?? [])]
    snapshotTitle.value = res.data.title
    await router.replace({
      query: route.query.snapshot === id ? { ...route.query, snapshot: id } : { snapshot: id },
    })
    panel.value = null
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
    panel.value = null
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
  if (result.value && !dirty.value) panel.value = null
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
      if (!row.decision_count) return { value: null, display: dash }
      return {
        value: row.train_usable_rate,
        display: `${formatWinRate(row.train_usable_rate)} · n=${row.decision_count}`,
      }
    case 'parser':
      if (!row.parser_n) return { value: null, display: dash }
      return {
        value: row.parser_success_rate,
        display: `${formatWinRate(row.parser_success_rate)} · n=${row.parser_n}`,
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

const metricGroups = computed(() =>
  [
    {
      label: t('focus.gameOutcomes'),
      rows: matrixRows.value.filter((row) => !row.metric.diagnostic),
    },
    {
      label: t('focus.runDiagnostics'),
      rows: matrixRows.value.filter((row) => row.metric.diagnostic),
    },
  ].filter((group) => group.rows.length),
)

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

const canInspectScenarios = computed(
  () =>
    snapshot.value &&
    rows.value.length === 2 &&
    rows.value.every((row) => row.game_type === 'doudizhu'),
)
async function inspectScenario(id: string) {
  const scenario = EXPERIMENT_SCENARIO_IDS.find((value) => `scenario-${value}` === id)
  if (!scenario || !canInspectScenarios.value) return
  await router.replace({
    query: {
      ...route.query,
      scenario,
      ...(route.query.scenario === scenario ? {} : { seed: undefined, turn: undefined }),
    },
  })
  panel.value = null
  await nextTick()
  document.getElementById('comparison-evidence')?.scrollIntoView({ block: 'start' })
}

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
        display: t('paired.formatDiagnostics', {
          train,
          usable: score?.train_usable_n ?? 0,
          n,
          parser,
          ok: score?.parser_ok ?? 0,
          parser_n: score?.parser_n ?? 0,
        }),
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
        if (stat.paired_wins == null) return null
        const wins = stat.paired_wins
        return { value: wins, display: String(wins) }
      }
      if (stat.win_rate == null) return null
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
    } else {
      panel.value = 'selection'
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
  <div class="page-container space-y-ink-6">
    <RouterLink
      v-if="typeof route.query.report_id === 'string'"
      :to="{
        name: 'research-report',
        params: { id: route.query.report_id },
        query: {
          evidence: route.query.evidence,
          puzzle_evidence: route.query.puzzle_evidence,
          trace_evidence: route.query.trace_evidence,
        },
      }"
      class="inline-block text-body text-ink-primary hover:underline"
      >{{ t('report.back') }}</RouterLink
    >
    <header class="flex flex-wrap items-center justify-between gap-ink-3">
      <UiButton
        variant="ghost"
        size="sm"
        @click="router.push(studyId ? `/research/${studyId}` : '/experiments')"
        >{{ t(studyId ? 'study.back' : 'compare.back') }}</UiButton
      >
      <div class="flex flex-wrap gap-ink-2">
        <UiButton
          variant="ghost"
          size="sm"
          :disabled="saving || comparing"
          @click="panel = 'selection'"
          >{{ t('focus.chooseRuns') }}</UiButton
        >
        <UiButton
          variant="ghost"
          size="sm"
          :disabled="saving || comparing"
          @click="panel = 'history'"
          >{{ t('compare.audit.saved') }}</UiButton
        >
        <HeaderToggles class="hidden md:flex" />
      </div>
    </header>
    <div v-if="loading || comparing" class="flex justify-center py-ink-8">
      <UiSpinner :label="t('common.loading')" />
    </div>
    <template v-else>
      <section class="space-y-ink-3">
        <h1 class="max-w-3xl text-headline font-semibold tracking-tight text-ink-text">
          {{ t(result ? 'focus.compareTitle' : 'focus.compareEmpty') }}
        </h1>
        <nav
          v-if="rows.length"
          class="flex flex-wrap gap-ink-3"
          :aria-label="t('compare.colExperiment')"
        >
          <RouterLink
            v-for="row in rows"
            :key="row.id"
            :to="`/experiments/${row.id}`"
            class="break-words text-body text-ink-primary hover:underline"
            >{{ row.name }}</RouterLink
          >
        </nav>
        <p v-if="snapshot" class="text-caption text-ink-text-muted">
          {{ t('compare.audit.snapshotAt', { time: formatDateTime(snapshot.created_at) }) }}
        </p>
      </section>
      <div v-if="dirty && rows.length" role="status" class="space-y-ink-3">
        <p class="text-body text-ink-text-secondary">{{ t('compare.audit.dirty') }}</p>
        <UiButton :disabled="!canCompare || saving" @click="submit">{{
          t('compare.submit')
        }}</UiButton>
      </div>
      <template v-else-if="result">
        <div class="flex flex-wrap gap-ink-3">
          <UiButton variant="ghost" size="sm" @click="panel = 'audit'">{{
            t('compare.audit.title')
          }}</UiButton>
          <UiButton variant="ghost" size="sm" @click="panel = 'metrics'">{{
            t('focus.metrics')
          }}</UiButton>
        </div>
        <ComparisonOverview :result="result" />
        <ComparisonResearch
          v-if="snapshot"
          :key="snapshot.id"
          :comparison-id="snapshot.id"
          :paired="rows.length === 2 && rows.every((row) => row.game_type === 'doudizhu')"
          :player-names="playerNames"
        />
        <section v-else class="space-y-ink-3 border-t border-ink-border pt-ink-6">
          <UiButton @click="panel = 'save'">{{ t('focus.freezeEvidence') }}</UiButton>
          <p class="max-w-2xl text-caption text-ink-text-secondary">{{ t('focus.freezeHint') }}</p>
        </section>
        <UiButton v-if="snapshot" variant="ghost" @click="panel = 'save'"
          >{{ t('compare.audit.export') }} / {{ t('compare.audit.save') }}</UiButton
        >
      </template>
      <section v-else class="space-y-ink-4">
        <p class="text-body text-ink-text-secondary">{{ t('focus.compareEmptyHint') }}</p>
        <UiButton @click="panel = 'selection'">{{ t('compare.pickRange') }}</UiButton>
      </section>
    </template>
    <UiDialog
      :open="panel === 'selection'"
      placement="side"
      :title="t('compare.pickRange')"
      @update:open="!$event && (panel = null)"
    >
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

      <template #footer
        ><UiButton :disabled="!canCompare || saving" :loading="comparing" @click="submit">{{
          t('compare.submit')
        }}</UiButton></template
      >
    </UiDialog>
    <UiDialog
      :open="panel === 'history'"
      placement="side"
      :title="t('compare.audit.saved')"
      @update:open="!$event && (panel = null)"
    >
      <section>
        <p v-if="!snapshots.length" class="mt-3 text-caption text-ink-text-secondary">
          {{ t('compare.audit.noSnapshots') }}
        </p>
        <ul class="mt-3 space-y-2">
          <li v-for="item in snapshots" :key="item.id">
            <UiButton variant="ghost" :disabled="saving || comparing" @click="openSnapshot(item.id)"
              >{{ item.title }} · {{ formatDateTime(item.created_at) }}</UiButton
            >
          </li>
        </ul>
        <UiButton v-if="moreSnapshots" variant="secondary" @click="loadSnapshots(true)">{{
          t('compare.audit.more')
        }}</UiButton>
      </section>
    </UiDialog>
    <UiDialog
      :open="panel === 'audit'"
      placement="side"
      :title="t('compare.audit.title')"
      @update:open="!$event && (panel = null)"
    >
      <ComparisonAudit
        v-if="result"
        :result="result"
        v-model:allowed="allowedChanges"
        :readonly="saving || comparing"
      />
      <template v-if="dirty" #footer
        ><UiButton :disabled="!canCompare || saving" :loading="comparing" @click="submit">{{
          t('compare.submit')
        }}</UiButton></template
      >
    </UiDialog>
    <UiDialog
      :open="panel === 'save'"
      placement="side"
      :title="t('compare.audit.name')"
      @update:open="!$event && (panel = null)"
    >
      <section class="space-y-3 rounded-ink-md border border-ink-border bg-ink-surface p-4">
        <p v-if="snapshot" class="text-body font-medium">
          {{ t('compare.audit.snapshotAt', { time: formatDateTime(snapshot.created_at) }) }}
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
    </UiDialog>
    <UiDialog
      :open="panel === 'metrics'"
      placement="side"
      :title="t('focus.metrics')"
      @update:open="!$event && (panel = null)"
    >
      <div class="space-y-ink-6">
        <p v-if="showLowPowerHint" class="text-caption text-ink-text-secondary">
          {{ t('compare.lowPowerHint') }}
        </p>
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
            <tbody v-for="group in metricGroups" :key="group.label">
              <tr>
                <th
                  scope="rowgroup"
                  :colspan="rows.length + 1"
                  class="bg-ink-surface-muted px-3 py-2 text-left font-semibold"
                >
                  {{ group.label }}
                </th>
              </tr>
              <tr
                v-for="mrow in group.rows"
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

        <p v-if="showScenarioMatrix" class="text-caption text-ink-text-secondary">
          {{ t('paired.matrixScope') }}
        </p>
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
                  <button
                    v-if="canInspectScenarios"
                    type="button"
                    class="mt-ink-2 block text-caption text-ink-primary underline"
                    @click="inspectScenario(mrow.metric.id)"
                  >
                    {{ t('paired.inspectScenario') }}
                  </button>
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
      </div>
    </UiDialog>
  </div>
</template>
