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
import UiSpinner from '@/components/ui/Spinner.vue'
import UiButton from '@/components/ui/Button.vue'
import UiCheckbox from '@/components/ui/Checkbox.vue'
import UiBadge from '@/components/ui/Badge.vue'
import UiEmpty from '@/components/ui/Empty.vue'
import UiInput from '@/components/ui/Input.vue'
import UiPagination from '@/components/ui/Pagination.vue'
import { DEFAULT_PAGE_SIZE, parsePageSize } from '@/utils/pagination'

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
const outcome = computed(() => {
  const v = route.query.outcome
  return typeof v === 'string' && v ? v : undefined
})
const gamePhase = computed(() => {
  const v = route.query.game_phase
  return typeof v === 'string' && v ? v : undefined
})
const trainUsableFilter = computed(() => {
  const v = route.query.train_usable
  if (v === 'true') return true
  if (v === 'false') return false
  return undefined
})
const minQuality = computed(() => {
  const q = route.query.min_quality
  return typeof q === 'string' && q ? parseFloat(q) : undefined
})
const page = computed(() => {
  const raw = route.query.page
  const n = typeof raw === 'string' ? parseInt(raw, 10) : 1
  return Number.isFinite(n) && n >= 1 ? n : 1
})
const pageSize = computed(() => parsePageSize(route.query.page_size))

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
    else if (experimentId.value) params.experiment_id = experimentId.value
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
  patchQuery({ page: next <= 1 ? undefined : String(next) })
}

function setPageSize(next: number): void {
  patchQuery({
    page: undefined,
    page_size: next === DEFAULT_PAGE_SIZE ? undefined : String(next),
  })
}

async function fetchStats() {
  try {
    const res = await decisionApi.stats(
      experimentId.value && !gameId.value ? { experiment_id: experimentId.value } : undefined,
    )
    stats.value = res.data
  } catch (e: unknown) {
    showApiError(e, t('decision.statsFailed'))
  }
}

function exportScopeParams() {
  const base = {
    game_id: gameId.value,
    experiment_id: gameId.value ? undefined : experimentId.value,
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

function selectPoint(point: DecisionPoint) {
  selectedPoint.value = point
}

function formatCards(cards: string[]): string {
  return cards.join(', ')
}

function formatAction(action: { action_type: string; cards: string[] } | null): string {
  if (!action) return t('common.none')
  if (action.action_type === 'PASS') return t('action.PASS')
  return `${action.action_type} [${action.cards.join(', ')}]`
}

function getQualityVariant(score: number): 'success' | 'warning' | 'danger' {
  if (score >= 0.7) return 'success'
  if (score >= 0.5) return 'warning'
  return 'danger'
}

watch(
  [gameId, experimentId, playerId, outcome, gamePhase, minQuality, trainUsableFilter, page, pageSize],
  () => {
    fetchDecisionPoints()
  },
)

watch(experimentId, () => {
  void fetchStats()
})

onMounted(() => {
  fetchDecisionPoints()
  fetchStats()
})
</script>

<template>
  <div class="page-container">
    <div class="mb-4 space-y-3">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <button
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
        <div class="flex flex-wrap items-center gap-2">
          <UiCheckbox v-model="exportIncludeThinking" :label="t('decision.includeThinking')" />
          <UiInput
            v-model="datasetName"
            :placeholder="t('decision.datasetNamePh')"
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
        v-show="howToOpen"
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
        <UiButton size="sm" @click="router.push('/training')">{{ t('decision.goTrain') }}</UiButton>
      </div>

      <WorkbenchFilterBar mode="decision" :player-candidates="playerCandidates" />

      <p
        v-if="stats"
        class="flex flex-wrap gap-x-3 gap-y-1 text-xs text-ink-text-muted tabular-nums"
      >
        <span>{{ t('decision.total', { n: stats.total }) }}</span>
        <span>{{ t('decision.avgQuality', { n: stats.avg_quality.toFixed(2) }) }}</span>
        <span class="text-ink-success">{{ t('decision.wins', { n: stats.outcome_counts.win || 0 }) }}</span>
        <span class="text-ink-danger">{{ t('decision.losses', { n: stats.outcome_counts.lose || 0 }) }}</span>
      </p>
    </div>

    <div class="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <div class="lg:col-span-1">
        <div class="rounded-ink-md border border-ink-border bg-ink-surface p-5">
          <div class="mb-4 border-b border-ink-border pb-3">
            <div class="flex flex-wrap items-baseline justify-between gap-2">
              <h3 class="text-base font-semibold text-ink-text">{{ t('decision.listTitle') }}</h3>
              <span class="text-xs text-ink-text-muted">{{ t('decision.totalItems', { n: listTotal }) }}</span>
            </div>
            <p v-if="gameId" class="mt-1 text-xs text-ink-text-muted">
              {{ t('decision.thisGame', { id: gameId }) }}
            </p>
            <p v-else-if="experimentId" class="mt-1 text-xs text-ink-text-muted">
              {{ t('decision.thisExperiment', { id: experimentId }) }}
            </p>
          </div>

          <div class="relative max-h-[600px] overflow-y-auto">
            <UiSpinner v-if="loading" overlay :label="t('common.loading')" />
            <UiEmpty
              v-if="!loading && decisionPoints.length === 0"
              :title="experimentId || gameId ? t('decision.emptyFiltered') : t('decision.empty')"
              :description="
                experimentId || gameId ? t('decision.emptyFilteredHint') : t('decision.emptyHint')
              "
            />

            <div v-else-if="!loading" class="space-y-2">
              <button
                v-for="point in decisionPoints"
                :key="point.id"
                type="button"
                class="w-full rounded-ink-md p-3 text-left transition-colors"
                :class="
                  selectedPoint?.id === point.id
                    ? 'bg-ink-primary-muted'
                    : 'hover:bg-ink-surface-muted'
                "
                :aria-pressed="selectedPoint?.id === point.id"
                @click="selectPoint(point)"
              >
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-2">
                    <UiBadge variant="muted">R{{ point.round_number }}</UiBadge>
                    <span class="text-sm font-medium text-ink-text">{{ point.player_id }}</span>
                    <UiBadge :variant="point.train_usable ? 'success' : 'muted'">
                      {{ point.train_usable ? t('filter.trainable') : t('filter.notTrainable') }}
                    </UiBadge>
                  </div>
                  <UiBadge
                    :variant="getQualityVariant(point.quality_score)"
                    :title="t('decision.qualityTitle')"
                  >
                    {{ t('decision.qualityScore', { n: point.quality_score.toFixed(2) }) }}
                  </UiBadge>
                </div>
                <div class="mt-2 text-xs text-ink-text-muted">
                  {{ formatAction(point.chosen_action) }}
                </div>
                <div class="mt-1 text-xs text-ink-text-muted">
                  {{ formatDateTime(point.created_at) }}
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

      <div class="lg:col-span-2">
        <div v-if="selectedPoint" class="rounded-ink-md border border-ink-border bg-ink-surface p-5">
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
                    v-if="selectedPoint.outcome"
                    :variant="selectedPoint.outcome === 'win' ? 'success' : 'danger'"
                  >
                    {{ selectedPoint.outcome === 'win' ? t('filter.win') : t('filter.lose') }}
                  </UiBadge>
                  <span v-else class="text-ink-text-muted">{{ t('decision.outcomeUnknown') }}</span>
                  <span class="text-xs text-ink-text-muted">
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
