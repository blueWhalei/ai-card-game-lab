<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { showApiError } from '@/utils/error'
import { tracesApi, type AggregatedMetrics, type Trace } from '@/api/traces'
import { actionTypeLabel, parseTraceDecision } from '@/utils/traceOutput'
import { formatDateTime, formatPercentage } from '@/utils/format'
import TraceDetail from '@/components/trace/TraceDetail.vue'
import ResponseTimeChart from '@/components/trace/ResponseTimeChart.vue'
import TraceMetrics from '@/components/trace/TraceMetrics.vue'
import WorkbenchFilterBar from '@/components/common/WorkbenchFilterBar.vue'
import type { WorkbenchLocalFilters } from '@/components/common/WorkbenchFilterBar.vue'
import CompactRecordList from '@/components/common/CompactRecordList.vue'
import type { CompactRecord } from '@/components/common/CompactRecordList.vue'
import KpiStrip from '@/components/common/KpiStrip.vue'
import type { KpiItem } from '@/components/common/KpiStrip.vue'
import UiButton from '@/components/ui/Button.vue'
import UiEmpty from '@/components/ui/Empty.vue'
import UiSkeletonList from '@/components/ui/SkeletonList.vue'
import UiTabs from '@/components/ui/Tabs.vue'
import UiPagination from '@/components/ui/Pagination.vue'
import { DEFAULT_PAGE_SIZE, parsePageSize, type PageSizeOption } from '@/utils/pagination'

type TracePane = 'records' | 'trend'

const PANE_VALUES: TracePane[] = ['records', 'trend']

const props = withDefaults(
  defineProps<{
    experimentId?: string
    embedded?: boolean
  }>(),
  {
    experimentId: undefined,
    embedded: false,
  },
)

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const traces = ref<Trace[]>([])
const listTotal = ref(0)
const metrics = ref<AggregatedMetrics | null>(null)
const loading = ref(false)
const selectedTrace = ref<Trace | null>(null)

const localPage = ref(1)
const localPageSize = ref<PageSizeOption>(DEFAULT_PAGE_SIZE)
const localPane = ref<TracePane>('records')
const localFilters = ref<WorkbenchLocalFilters>({})

const routeGameId = computed(() => {
  const v = route.query.game_id
  return typeof v === 'string' && v ? v : undefined
})
const routeExperimentId = computed(() => {
  const v = route.query.experiment_id
  return typeof v === 'string' && v ? v : undefined
})
const routePlayerId = computed(() => {
  const v = route.query.player_id
  return typeof v === 'string' && v ? v : undefined
})
const routeModel = computed(() => {
  const v = route.query.model
  return typeof v === 'string' && v ? v : undefined
})
const routeParserOk = computed(() => {
  const v = route.query.parser_ok
  if (v === 'true') return true
  if (v === 'false') return false
  return undefined
})
const routePage = computed(() => {
  const raw = route.query.page
  const n = typeof raw === 'string' ? parseInt(raw, 10) : 1
  return Number.isFinite(n) && n >= 1 ? n : 1
})
const routePageSize = computed(() => parsePageSize(route.query.page_size))
const routePane = computed<TracePane>(() => {
  const raw = route.query.view
  return typeof raw === 'string' && PANE_VALUES.includes(raw as TracePane)
    ? (raw as TracePane)
    : 'records'
})

const effectiveExperimentId = computed(() =>
  props.embedded ? props.experimentId : routeExperimentId.value,
)
const gameId = computed(() =>
  props.embedded ? localFilters.value.game_id || undefined : routeGameId.value,
)
const playerId = computed(() =>
  props.embedded
    ? localFilters.value.player_id || undefined
    : routePlayerId.value,
)
const model = computed(() =>
  props.embedded ? localFilters.value.model || undefined : routeModel.value,
)
const parserOk = computed(() => {
  if (props.embedded) {
    const v = localFilters.value.parser_ok
    if (v === 'true') return true
    if (v === 'false') return false
    return undefined
  }
  return routeParserOk.value
})
const page = computed(() => (props.embedded ? localPage.value : routePage.value))
const pageSize = computed(() =>
  props.embedded ? localPageSize.value : routePageSize.value,
)
const pane = computed(() => (props.embedded ? localPane.value : routePane.value))

const tabs = computed(() => [
  { value: 'records', label: t('trace.tabList') },
  { value: 'trend', label: t('trace.tabTrend') },
])

const playerCandidates = computed(() =>
  [...new Set(traces.value.map((row) => row.player_id).filter(Boolean))],
)
const modelCandidates = computed(() =>
  [...new Set(traces.value.map((row) => row.model).filter(Boolean))],
)

const filterParams = computed(() => {
  const params: {
    game_id?: string
    experiment_id?: string
    player_id?: string
    model?: string
    parser_ok?: boolean
    page: number
    page_size: number
  } = { page: page.value, page_size: pageSize.value }
  if (gameId.value) params.game_id = gameId.value
  else if (effectiveExperimentId.value) params.experiment_id = effectiveExperimentId.value
  if (playerId.value) params.player_id = playerId.value
  if (model.value) params.model = model.value
  if (parserOk.value !== undefined) params.parser_ok = parserOk.value
  return params
})

const metricsParams = computed(() => {
  const params: {
    game_id?: string
    experiment_id?: string
    player_id?: string
    model?: string
    parser_ok?: boolean
  } = {}
  if (gameId.value) params.game_id = gameId.value
  else if (effectiveExperimentId.value) params.experiment_id = effectiveExperimentId.value
  if (playerId.value) params.player_id = playerId.value
  if (model.value) params.model = model.value
  if (parserOk.value !== undefined) params.parser_ok = parserOk.value
  return params
})

const parserRate = computed(() => {
  if (!metrics.value || metrics.value.total_traces === 0) return 0
  return (metrics.value.langchain_success_count ?? 0) / metrics.value.total_traces
})

function decisionOf(trace: Trace): string {
  return actionTypeLabel(parseTraceDecision(trace.output_data).actionType)
}

async function fetchTraces() {
  loading.value = true
  try {
    const [listRes, metricsRes] = await Promise.all([
      tracesApi.list(filterParams.value),
      tracesApi.metrics(metricsParams.value),
    ])
    traces.value = listRes.data.items
    listTotal.value = listRes.data.total
    metrics.value = metricsRes.data ?? null
    selectedTrace.value =
      traces.value.find((row) => row.id === selectedTrace.value?.id) ??
      traces.value[0] ??
      null
  } catch (e: unknown) {
    showApiError(e, t('trace.loadFailed'))
  } finally {
    loading.value = false
  }
}

function selectTraceById(id: string): void {
  const trace = traces.value.find((row) => row.id === id)
  if (trace) selectedTrace.value = trace
}

const compactRecords = computed((): CompactRecord[] =>
  traces.value.map((trace) => ({
    id: trace.id,
    primary: decisionOf(trace),
    secondary: `R${trace.round_number} · ${trace.player_id}`,
    meta: formatDateTime(trace.created_at),
    trailing: `${Math.round(trace.metrics.response_time_ms)}ms`,
    badge: trace.metrics.used_langchain_parser ? t('filter.parseOk') : t('filter.ruleFallback'),
    badgeTone: trace.metrics.used_langchain_parser ? 'success' : 'warning',
  })),
)

const kpiItems = computed((): KpiItem[] => {
  if (!metrics.value || metrics.value.total_traces <= 0) return []
  return [
    {
      id: 'count',
      label: t('trace.kpiCount'),
      value: String(listTotal.value),
    },
    {
      id: 'avg',
      label: t('trace.kpiAvgMs'),
      value: String(Math.round(metrics.value.avg_response_time_ms)),
    },
    {
      id: 'parser',
      label: t('trace.kpiParse'),
      value: formatPercentage(parserRate.value),
    },
  ]
})

function patchQuery(updates: Record<string, string | undefined>): void {
  const q: Record<string, string> = {}
  for (const [k, v] of Object.entries(route.query)) {
    if (typeof v === 'string' && v) q[k] = v
  }
  for (const [k, v] of Object.entries(updates)) {
    if (!v) delete q[k]
    else q[k] = v
  }
  void router.replace({ query: q })
}

function setPage(next: number): void {
  if (props.embedded) {
    localPage.value = next
    return
  }
  patchQuery({ page: next <= 1 ? undefined : String(next) })
}

function setPageSize(next: number): void {
  if (props.embedded) {
    localPage.value = 1
    localPageSize.value = parsePageSize(next)
    return
  }
  patchQuery({
    page: undefined,
    page_size: next === DEFAULT_PAGE_SIZE ? undefined : String(next),
  })
}

function setPane(next: string): void {
  const paneNext = PANE_VALUES.includes(next as TracePane) ? (next as TracePane) : 'records'
  if (props.embedded) {
    localPane.value = paneNext
    return
  }
  patchQuery({ view: paneNext === 'records' ? undefined : paneNext })
}

function clearScope(): void {
  if (props.embedded) {
    localFilters.value = { ...localFilters.value, game_id: undefined }
    localPage.value = 1
    return
  }
  patchQuery({ experiment_id: undefined, game_id: undefined, page: undefined })
}

function onLocalFiltersUpdate(next: WorkbenchLocalFilters): void {
  localFilters.value = next
  localPage.value = 1
}

watch(filterParams, () => {
  void fetchTraces()
}, { deep: true })

onMounted(() => {
  void fetchTraces()
})
</script>

<template>
  <div :class="embedded ? 'space-y-3' : 'page-container space-y-5'">
    <WorkbenchFilterBar
      v-if="embedded && experimentId"
      mode="trace"
      :player-candidates="playerCandidates"
      :model-candidates="modelCandidates"
      :locked-experiment-id="experimentId"
      :filters="localFilters"
      @update:filters="onLocalFiltersUpdate"
    />
    <WorkbenchFilterBar
      v-else
      mode="trace"
      :player-candidates="playerCandidates"
      :model-candidates="modelCandidates"
    />

    <UiTabs
      :model-value="pane"
      :tabs="tabs"
      @update:model-value="setPane"
    />

    <template v-if="pane === 'records'">
      <KpiStrip
        v-if="kpiItems.length && !embedded"
        :items="kpiItems"
        class="md:!grid-cols-3"
      />

      <div
        :class="
          embedded
            ? 'grid grid-cols-1 gap-4 lg:grid-cols-5'
            : 'grid grid-cols-1 gap-6 lg:grid-cols-5'
        "
      >
        <div class="lg:col-span-2">
          <div
            class="rounded-ink-md border border-ink-border bg-ink-surface"
            :class="embedded ? 'p-3' : 'p-4'"
          >
            <div class="mb-2 flex items-baseline justify-between gap-2">
              <h3 class="text-sm font-semibold text-ink-text">{{ t('trace.listTitle') }}</h3>
              <span class="text-xs text-ink-text-muted">{{ t('trace.thisPage', { n: traces.length }) }}</span>
            </div>

            <UiSkeletonList v-if="loading" :rows="8" />
            <UiEmpty
              v-else-if="traces.length === 0"
              :title="
                effectiveExperimentId || gameId ? t('trace.emptyFiltered') : t('trace.empty')
              "
              :description="
                effectiveExperimentId || gameId
                  ? t('trace.emptyFilteredHint')
                  : t('trace.emptyHint')
              "
            >
              <UiButton
                v-if="(effectiveExperimentId || gameId) && !embedded"
                size="sm"
                variant="secondary"
                @click="clearScope"
              >
                {{ t('filter.clearScope') }}
              </UiButton>
              <UiButton v-else-if="!embedded" size="sm" @click="router.push('/')">
                {{ t('trace.emptyAction') }}
              </UiButton>
            </UiEmpty>
            <CompactRecordList
              v-else
              :records="compactRecords"
              :selected-id="selectedTrace?.id"
              :list-class="
                embedded ? '!h-[min(48vh,calc(100vh-26rem))]' : undefined
              "
              @select="selectTraceById"
            />
            <div v-if="listTotal > 0" class="mt-3 border-t border-ink-border pt-3">
              <UiPagination
                :page="page"
                :page-size="pageSize"
                :total="listTotal"
                class="justify-between"
                @update:page="setPage"
                @update:page-size="setPageSize"
              />
            </div>
          </div>
        </div>

        <div class="lg:col-span-3">
          <TraceDetail v-if="selectedTrace" :trace="selectedTrace" />
          <div v-else class="rounded-ink-md border border-ink-border bg-ink-surface p-5">
            <UiEmpty :title="t('trace.pickOne')" />
          </div>
        </div>
      </div>
    </template>

    <template v-else>
      <TraceMetrics v-if="metrics && metrics.total_traces > 0" :metrics="metrics" />
      <ResponseTimeChart
        :game-id="gameId"
        :experiment-id="effectiveExperimentId"
        :player-id="playerId"
        :model="model"
        :parser-ok="parserOk"
      />
    </template>
  </div>
</template>
