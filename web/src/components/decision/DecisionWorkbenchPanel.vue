<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { toast } from '@/components/ui/toast'
import { showApiError } from '@/utils/error'
import { decisionApi, type DecisionPoint, type DecisionStats } from '@/api/decision'
import { dataApi } from '@/api/dataApi'
import { formatDateTime } from '@/utils/format'
import WorkbenchFilterBar from '@/components/common/WorkbenchFilterBar.vue'
import type { WorkbenchLocalFilters } from '@/components/common/WorkbenchFilterBar.vue'
import CompactRecordList from '@/components/common/CompactRecordList.vue'
import type { CompactRecord } from '@/components/common/CompactRecordList.vue'
import UiButton from '@/components/ui/Button.vue'
import UiCheckbox from '@/components/ui/Checkbox.vue'
import UiBadge from '@/components/ui/Badge.vue'
import UiEmpty from '@/components/ui/Empty.vue'
import UiSkeletonList from '@/components/ui/SkeletonList.vue'
import UiInput from '@/components/ui/Input.vue'
import UiPagination from '@/components/ui/Pagination.vue'
import { DEFAULT_PAGE_SIZE, parsePageSize, type PageSizeOption } from '@/utils/pagination'

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
const lastRegisteredName = ref('')
const decisionPoints = ref<DecisionPoint[]>([])
const listTotal = ref(0)
const loading = ref(false)
const exporting = ref(false)
const registering = ref(false)
const selectedPoint = ref<DecisionPoint | null>(null)
const stats = ref<DecisionStats | null>(null)
const howToOpen = ref(false)
const exportIncludeThinking = ref(false)
const datasetName = ref('')

/** Embedded: local pagination + filters (no route writes). */
const localPage = ref(1)
const localPageSize = ref<PageSizeOption>(DEFAULT_PAGE_SIZE)
const localFilters = ref<WorkbenchLocalFilters>({ train_usable: 'true' })

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
const routeOutcome = computed(() => {
  const v = route.query.outcome
  return typeof v === 'string' && v ? v : undefined
})
const routeGamePhase = computed(() => {
  const v = route.query.game_phase
  return typeof v === 'string' && v ? v : undefined
})
const routeTrainUsable = computed(() => {
  const v = route.query.train_usable
  if (v === 'true') return true
  if (v === 'false') return false
  return undefined
})
const routeMinQuality = computed(() => {
  const q = route.query.min_quality
  return typeof q === 'string' && q ? parseFloat(q) : undefined
})
const routePage = computed(() => {
  const raw = route.query.page
  const n = typeof raw === 'string' ? parseInt(raw, 10) : 1
  return Number.isFinite(n) && n >= 1 ? n : 1
})
const routePageSize = computed(() => parsePageSize(route.query.page_size))

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
const outcome = computed(() =>
  props.embedded ? localFilters.value.outcome || undefined : routeOutcome.value,
)
const gamePhase = computed(() =>
  props.embedded
    ? localFilters.value.game_phase || undefined
    : routeGamePhase.value,
)
const trainUsableFilter = computed(() => {
  if (props.embedded) {
    const v = localFilters.value.train_usable
    if (v === 'true') return true
    if (v === 'false') return false
    return undefined
  }
  return routeTrainUsable.value
})
const minQuality = computed(() => {
  if (props.embedded) {
    const q = localFilters.value.min_quality
    return q ? parseFloat(q) : undefined
  }
  return routeMinQuality.value
})
const page = computed(() => (props.embedded ? localPage.value : routePage.value))
const pageSize = computed(() =>
  props.embedded ? localPageSize.value : routePageSize.value,
)

const playerCandidates = computed(() =>
  [...new Set(decisionPoints.value.map((p) => p.player_id).filter(Boolean))],
)

async function fetchDecisionPoints() {
  loading.value = true
  try {
    const params: {
      game_id?: string
      experiment_id?: string
      player_id?: string
      outcome?: string
      game_phase?: string
      min_quality?: number
      train_usable?: boolean
      page: number
      page_size: number
    } = { page: page.value, page_size: pageSize.value }
    if (gameId.value) params.game_id = gameId.value
    else if (effectiveExperimentId.value) params.experiment_id = effectiveExperimentId.value
    if (playerId.value) params.player_id = playerId.value
    if (outcome.value) params.outcome = outcome.value
    if (gamePhase.value) params.game_phase = gamePhase.value
    if (minQuality.value !== undefined && !Number.isNaN(minQuality.value)) {
      params.min_quality = minQuality.value
    }
    if (trainUsableFilter.value !== undefined) params.train_usable = trainUsableFilter.value
    const res = await decisionApi.list(params)
    decisionPoints.value = res.data.items
    listTotal.value = res.data.total
    selectedPoint.value =
      decisionPoints.value.find((p) => p.id === selectedPoint.value?.id) ??
      decisionPoints.value[0] ??
      null
  } catch (e: unknown) {
    showApiError(e, t('decision.loadFailed'))
  } finally {
    loading.value = false
  }
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

async function fetchStats() {
  try {
    const res = await decisionApi.stats(
      effectiveExperimentId.value && !gameId.value
        ? { experiment_id: effectiveExperimentId.value }
        : undefined,
    )
    stats.value = res.data
  } catch (e: unknown) {
    showApiError(e, t('decision.statsFailed'))
  }
}

function exportScopeParams() {
  const base = {
    game_id: gameId.value,
    experiment_id: gameId.value ? undefined : effectiveExperimentId.value,
    player_id: playerId.value,
    outcome: outcome.value,
    game_phase: gamePhase.value,
    min_quality: minQuality.value,
    include_thinking: exportIncludeThinking.value,
  }
  if (trainUsableFilter.value === undefined) {
    return { ...base, train_usable_only: false as const }
  }
  return { ...base, train_usable: trainUsableFilter.value }
}

async function exportChatml() {
  exporting.value = true
  try {
    const res = await decisionApi.export(exportScopeParams())
    const { filepath, count } = res.data
    if (!filepath || count === 0) {
      toast.warning(t('decision.nothingToExport'))
      return
    }
    toast.success(t('decision.exported', { count, path: filepath }))
  } catch (e: unknown) {
    showApiError(e, t('decision.exportFailed'))
  } finally {
    exporting.value = false
  }
}

async function registerAsDataset() {
  const name =
    datasetName.value.trim() ||
    `decisions-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}`
  registering.value = true
  try {
    const res = await dataApi.createDatasetFromDecisions({
      name,
      game_type: 'doudizhu',
      ...exportScopeParams(),
    })
    lastRegisteredName.value = res.data.name
    toast.success(
      t('decision.savedChatml', { name: res.data.name, count: res.data.sample_count }),
    )
    datasetName.value = ''
  } catch (e: unknown) {
    showApiError(e, t('decision.saveDatasetFailed'))
  } finally {
    registering.value = false
  }
}

function selectPointById(id: string): void {
  const point = decisionPoints.value.find((p) => p.id === id)
  if (point) selectedPoint.value = point
}

function formatCards(cards: string[]): string {
  return cards.join(', ')
}

function formatAction(action: { action_type: string; cards: string[] } | null): string {
  if (!action) return t('common.none')
  if (action.action_type === 'PASS') return t('action.PASS')
  return `${action.action_type} [${action.cards.join(', ')}]`
}

function outcomeLabel(o: string | null | undefined): string {
  if (o === 'win') return t('filter.win')
  if (o === 'lose') return t('filter.lose')
  return t('common.unknown')
}

function outcomeTone(o: string | null | undefined): 'success' | 'danger' | 'muted' {
  if (o === 'win') return 'success'
  if (o === 'lose') return 'danger'
  return 'muted'
}

const compactRecords = computed((): CompactRecord[] =>
  decisionPoints.value.map((point) => ({
    id: point.id,
    primary: `R${point.round_number}`,
    secondary: `${point.player_id} · ${formatAction(point.chosen_action)}`,
    meta: formatDateTime(point.created_at),
    badge: outcomeLabel(point.outcome),
    badgeTone: outcomeTone(point.outcome),
    trailing: point.train_usable ? t('filter.trainable') : undefined,
  })),
)

watch(
  [
    gameId,
    effectiveExperimentId,
    playerId,
    outcome,
    gamePhase,
    minQuality,
    trainUsableFilter,
    page,
    pageSize,
  ],
  () => {
    void fetchDecisionPoints()
  },
)

watch(effectiveExperimentId, () => {
  void fetchStats()
})

onMounted(() => {
  void fetchDecisionPoints()
  void fetchStats()
})
</script>

<template>
  <div :class="embedded ? 'space-y-3' : 'page-container'">
    <div :class="embedded ? 'space-y-2' : 'mb-4 space-y-3'">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <button
          v-if="!embedded"
          type="button"
          class="inline-flex items-center gap-1 text-xs text-ink-text-muted hover:text-ink-text"
          :aria-expanded="howToOpen"
          @click="howToOpen = !howToOpen"
        >
          <Icon
            :icon="howToOpen ? 'lucide:chevron-down' : 'lucide:chevron-right'"
            class="h-3.5 w-3.5"
          />
          {{ t('common.howTo') }}
        </button>
        <div v-else />
        <div class="flex flex-wrap items-center gap-2">
          <UiCheckbox v-model="exportIncludeThinking" :label="t('decision.includeThinking')" />
          <UiInput
            v-model="datasetName"
            :placeholder="t('decision.datasetNamePh')"
            :class="embedded ? 'w-40' : undefined"
          />
          <UiButton
            variant="primary"
            size="sm"
            :loading="registering"
            @click="registerAsDataset"
          >
            {{ registering ? t('decision.saving') : t('decision.saveDataset') }}
          </UiButton>
          <UiButton variant="secondary" size="sm" :loading="exporting" @click="exportChatml">
            {{ exporting ? t('decision.exporting') : t('decision.exportFile') }}
          </UiButton>
        </div>
      </div>

      <div
        v-if="!embedded && howToOpen"
        class="rounded-ink border border-ink-border bg-ink-paper-elevated/70 px-4 py-3 text-sm text-ink-text-secondary"
      >
        <ol class="list-decimal space-y-1 pl-5 leading-relaxed">
          <li>
            {{ t('decision.tip1pre') }}<strong class="font-medium text-ink-text">{{ t('decision.tip1strong') }}</strong>{{ t('decision.tip1post') }}
          </li>
          <li>{{ t('decision.tip2') }}</li>
          <li>{{ t('decision.tip3') }}</li>
        </ol>
      </div>

      <div
        v-if="lastRegisteredName"
        class="flex flex-wrap items-center justify-between gap-3 rounded-ink-md border border-ink-success/30 bg-ink-surface px-4 py-2.5"
      >
        <p class="text-sm text-ink-text">
          {{ t('decision.savedNamed', { name: lastRegisteredName }) }}
        </p>
        <UiButton
          size="sm"
          @click="
            router.push({
              path: '/training',
              query: effectiveExperimentId ? { experiment_id: effectiveExperimentId } : undefined,
            })
          "
        >
          {{ t('decision.goTrain') }}
        </UiButton>
      </div>

      <WorkbenchFilterBar
        v-if="embedded && experimentId"
        mode="decision"
        :player-candidates="playerCandidates"
        :locked-experiment-id="experimentId"
        :filters="localFilters"
        @update:filters="onLocalFiltersUpdate"
      />
      <WorkbenchFilterBar
        v-else
        mode="decision"
        :player-candidates="playerCandidates"
      />

      <p
        v-if="stats && !embedded"
        class="flex flex-wrap gap-x-3 gap-y-1 text-xs text-ink-text-muted tabular-nums"
      >
        <span>{{ t('decision.total', { n: stats.total }) }}</span>
        <span>{{ t('decision.avgQuality', { n: stats.avg_quality.toFixed(2) }) }}</span>
        <span class="text-ink-success">{{ t('decision.wins', { n: stats.outcome_counts.win || 0 }) }}</span>
        <span class="text-ink-danger">{{ t('decision.losses', { n: stats.outcome_counts.lose || 0 }) }}</span>
      </p>
    </div>

    <div :class="embedded ? 'grid grid-cols-1 gap-4 lg:grid-cols-3' : 'grid grid-cols-1 gap-6 lg:grid-cols-3'">
      <div class="lg:col-span-1">
        <div
          class="rounded-ink-md border border-ink-border bg-ink-surface"
          :class="embedded ? 'p-3' : 'p-4'"
        >
          <div class="mb-2 border-b border-ink-border pb-2">
            <div class="flex flex-wrap items-baseline justify-between gap-2">
              <h3 class="text-sm font-semibold text-ink-text">{{ t('decision.listTitle') }}</h3>
              <span class="text-xs text-ink-text-muted">{{ t('decision.totalItems', { n: listTotal }) }}</span>
            </div>
            <p v-if="gameId" class="mt-1 truncate text-xs text-ink-text-muted" :title="gameId">
              {{ t('decision.thisGame', { id: gameId }) }}
            </p>
            <p
              v-else-if="effectiveExperimentId && !embedded"
              class="mt-1 truncate text-xs text-ink-text-muted"
              :title="effectiveExperimentId"
            >
              {{
                t('filter.thisExperiment', {
                  name: effectiveExperimentId.slice(0, 12) + '…',
                })
              }}
            </p>
          </div>

          <UiSkeletonList v-if="loading" :rows="8" />
          <UiEmpty
            v-else-if="decisionPoints.length === 0"
            :title="
              effectiveExperimentId || gameId ? t('decision.emptyFiltered') : t('decision.empty')
            "
            :description="
              effectiveExperimentId || gameId
                ? t('decision.emptyFilteredHint')
                : t('decision.emptyHint')
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
              {{ t('decision.emptyAction') }}
            </UiButton>
          </UiEmpty>
          <CompactRecordList
            v-else
            :records="compactRecords"
            :selected-id="selectedPoint?.id"
            :list-class="
              embedded ? '!h-[min(48vh,calc(100vh-26rem))]' : undefined
            "
            @select="selectPointById"
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

      <div class="lg:col-span-2">
        <div
          v-if="selectedPoint"
          class="rounded-ink-md border border-ink-border bg-ink-surface"
          :class="embedded ? 'p-4' : 'p-5'"
        >
          <div class="mb-4 border-b border-ink-border pb-3">
            <h3 class="text-base font-semibold text-ink-text">{{ t('decision.detailTitle') }}</h3>
          </div>

          <div class="space-y-4">
            <div class="grid grid-cols-2 gap-4">
              <div>
                <div class="text-xs font-medium text-ink-text-muted">{{ t('decision.phase') }}</div>
                <div class="mt-1 text-sm text-ink-text">{{ selectedPoint.game_phase }}</div>
              </div>
              <div>
                <div class="text-xs font-medium text-ink-text-muted">{{ t('decision.trainOutcome') }}</div>
                <div class="mt-1 flex flex-wrap items-center gap-2 text-sm text-ink-text">
                  <UiBadge :variant="selectedPoint.train_usable ? 'success' : 'warning'">
                    {{
                      selectedPoint.train_usable
                        ? t('filter.trainable')
                        : t('decision.notTrainableReason')
                    }}
                  </UiBadge>
                  <UiBadge
                    :variant="
                      selectedPoint.outcome === 'win'
                        ? 'success'
                        : selectedPoint.outcome === 'lose'
                          ? 'danger'
                          : 'muted'
                    "
                  >
                    {{ outcomeLabel(selectedPoint.outcome) }}
                  </UiBadge>
                  <span
                    class="text-xs text-ink-text-muted"
                    :title="t('decision.qualityTitle')"
                  >
                    {{ t('decision.qualityLabel', { n: selectedPoint.quality_score.toFixed(2) }) }}
                  </span>
                </div>
              </div>
            </div>

            <div>
              <div class="text-xs font-medium text-ink-text-muted">{{ t('decision.hand') }}</div>
              <div class="mt-1 rounded-ink bg-ink-surface-muted p-2 font-mono text-sm">
                {{ formatCards(selectedPoint.hand_cards) }}
              </div>
            </div>

            <div v-if="selectedPoint.opponent_hands">
              <div class="text-xs font-medium text-ink-text-muted">{{ t('decision.oppLeft') }}</div>
              <div class="mt-1 text-sm text-ink-text">
                <span v-for="(count, pid) in selectedPoint.opponent_hands" :key="pid" class="mr-3">
                  {{ t('decision.oppCards', { id: pid, n: count }) }}
                </span>
              </div>
            </div>

            <div v-if="selectedPoint.last_action">
              <div class="text-xs font-medium text-ink-text-muted">{{ t('decision.lastPlay') }}</div>
              <div class="mt-1 text-sm text-ink-text">
                {{ selectedPoint.last_action.player }}: {{ formatAction(selectedPoint.last_action) }}
              </div>
            </div>

            <div>
              <div class="text-xs font-medium text-ink-text-muted">{{ t('decision.legal') }}</div>
              <div class="mt-1 flex flex-wrap gap-2">
                <span
                  v-for="(action, idx) in selectedPoint.legal_actions"
                  :key="idx"
                  class="rounded-ink bg-ink-surface-muted px-2 py-1 text-xs text-ink-text-secondary"
                >
                  {{ formatAction(action) }}
                </span>
              </div>
            </div>

            <div>
              <div class="text-xs font-medium text-ink-text-muted">{{ t('decision.chosen') }}</div>
              <div class="mt-1 rounded-ink bg-ink-primary-muted p-2 font-medium text-ink-text">
                {{ formatAction(selectedPoint.chosen_action) }}
              </div>
            </div>

            <div v-if="selectedPoint.thinking">
              <div class="text-xs font-medium text-ink-text-muted">{{ t('decision.thinking') }}</div>
              <div class="mt-1 rounded-ink bg-ink-surface-muted p-3 text-sm leading-relaxed text-ink-text-secondary">
                {{ selectedPoint.thinking }}
              </div>
            </div>
          </div>
        </div>

        <div v-else class="rounded-ink-md border border-ink-border bg-ink-surface p-5">
          <UiEmpty :title="t('decision.pickOne')" />
        </div>
      </div>
    </div>
  </div>
</template>
