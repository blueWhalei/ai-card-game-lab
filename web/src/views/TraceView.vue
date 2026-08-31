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
import UiSpinner from '@/components/ui/Spinner.vue'
import UiBadge from '@/components/ui/Badge.vue'
import UiEmpty from '@/components/ui/Empty.vue'
import UiTabs from '@/components/ui/Tabs.vue'
import UiPagination from '@/components/ui/Pagination.vue'
import { DEFAULT_PAGE_SIZE, parsePageSize } from '@/utils/pagination'

type TracePane = 'records' | 'trend'

const PANE_VALUES: TracePane[] = ['records', 'trend']

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const traces = ref<Trace[]>([])
const listTotal = ref(0)
const metrics = ref<AggregatedMetrics | null>(null)
const loading = ref(false)
const selectedTrace = ref<Trace | null>(null)

const gameId = computed(() => {
  const v = route.query.game_id
  return typeof v === 'string' && v ? v : undefined
})
const experimentId = computed(() => {
  const v = route.query.experiment_id
  return typeof v === 'string' && v ? v : undefined
})
const playerId = computed(() => {
  const v = route.query.player_id
  return typeof v === 'string' && v ? v : undefined
})
const model = computed(() => {
  const v = route.query.model
  return typeof v === 'string' && v ? v : undefined
})
const parserOk = computed(() => {
  const v = route.query.parser_ok
  if (v === 'true') return true
  if (v === 'false') return false
  return undefined
})
const page = computed(() => {
  const raw = route.query.page
  const n = typeof raw === 'string' ? parseInt(raw, 10) : 1
  return Number.isFinite(n) && n >= 1 ? n : 1
})
const pageSize = computed(() => parsePageSize(route.query.page_size))

const pane = computed<TracePane>(() => {
  const raw = route.query.view
  return typeof raw === 'string' && PANE_VALUES.includes(raw as TracePane)
    ? (raw as TracePane)
    : 'records'
})

const tabs = computed(() => [
  { value: 'records', label: t('trace.tabList') },
  { value: 'trend', label: t('trace.tabTrend') },
])

const playerCandidates = computed(() =>
  [...new Set(traces.value.map((t) => t.player_id).filter(Boolean))],
)
const modelCandidates = computed(() =>
  [...new Set(traces.value.map((t) => t.model).filter(Boolean))],
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
  else if (experimentId.value) params.experiment_id = experimentId.value
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
  else if (experimentId.value) params.experiment_id = experimentId.value
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
      traces.value.find((t) => t.id === selectedTrace.value?.id) ?? traces.value[0] ?? null
  } catch (e: unknown) {
    showApiError(e, t('trace.loadFailed'))
  } finally {
    loading.value = false
  }
}

function selectTrace(trace: Trace) {
  selectedTrace.value = trace
}

function setPage(next: number): void {
  patchQuery({ page: next <= 1 ? undefined : String(next) })
}

function setPageSize(next: number): void {
  patchQuery({
    page: undefined,
    page_size: next === DEFAULT_PAGE_SIZE ? undefined : String(next),
  })
}

function setPane(next: string): void {
  const paneNext = PANE_VALUES.includes(next as TracePane) ? (next as TracePane) : 'records'
  patchQuery({ view: paneNext === 'records' ? undefined : paneNext })
}

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

watch(filterParams, fetchTraces, { deep: true })

onMounted(fetchTraces)
</script>

<template>
  <div class="page-container space-y-5">
    <WorkbenchFilterBar
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
      <div
        v-if="metrics && metrics.total_traces > 0"
        class="flex flex-wrap gap-x-6 gap-y-1 text-sm text-ink-text-secondary"
      >
        <span>{{ t('trace.items', { n: listTotal }) }}</span>
        <span>
          {{ t('trace.avgResponse') }}
          <span class="tabular-nums text-ink-text">{{ Math.round(metrics.avg_response_time_ms) }}</span>
          ms
        </span>
        <span>
          {{ t('trace.parseOk') }}
          <span class="tabular-nums text-ink-text">{{ formatPercentage(parserRate) }}</span>
        </span>
      </div>

      <div class="grid grid-cols-1 gap-6 lg:grid-cols-5">
        <div class="lg:col-span-2">
          <div class="rounded-ink-md border border-ink-border bg-ink-surface p-4">
            <div class="mb-3 flex items-baseline justify-between gap-2">
              <h3 class="text-sm font-semibold text-ink-text">{{ t('trace.listTitle') }}</h3>
              <span class="text-xs text-ink-text-muted">{{ t('trace.thisPage', { n: traces.length }) }}</span>
            </div>

            <div class="relative max-h-[min(70vh,640px)] overflow-y-auto">
              <UiSpinner v-if="loading" overlay :label="t('common.loading')" />
              <UiEmpty
                v-if="!loading && traces.length === 0"
                :title="experimentId || gameId ? t('trace.emptyFiltered') : t('trace.empty')"
                :description="
                  experimentId || gameId ? t('trace.emptyFilteredHint') : t('trace.emptyHint')
                "
              />

              <div v-else-if="!loading" class="divide-y divide-ink-border">
                <button
                  v-for="trace in traces"
                  :key="trace.id"
                  type="button"
                  class="w-full px-1 py-2.5 text-left transition-colors"
                  :class="
                    selectedTrace?.id === trace.id
                      ? 'bg-ink-primary-muted'
                      : 'hover:bg-ink-surface-muted'
                  "
                  :aria-pressed="selectedTrace?.id === trace.id"
                  @click="selectTrace(trace)"
                >
                  <div class="flex items-center justify-between gap-2">
                    <span class="text-sm font-medium text-ink-text">{{ decisionOf(trace) }}</span>
                    <span class="tabular-nums text-xs text-ink-text-muted">
                      {{ Math.round(trace.metrics.response_time_ms) }}ms
                    </span>
                  </div>
                  <div class="mt-1 flex items-center justify-between text-xs text-ink-text-muted">
                    <span>R{{ trace.round_number }} · {{ trace.player_id }}</span>
                    <UiBadge
                      :variant="trace.metrics.used_langchain_parser ? 'success' : 'warning'"
                    >
                      {{
                        trace.metrics.used_langchain_parser
                          ? t('filter.parseOk')
                          : t('filter.ruleFallback')
                      }}
                    </UiBadge>
                  </div>
                  <div class="mt-0.5 text-xs text-ink-text-muted">
                    {{ formatDateTime(trace.created_at) }}
                  </div>
                </button>
              </div>
            </div>
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
        :experiment-id="experimentId"
        :player-id="playerId"
        :model="model"
        :parser-ok="parserOk"
      />
    </template>
  </div>
</template>
