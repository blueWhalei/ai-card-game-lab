<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { toast } from '@/components/ui/toast'
import { showApiError } from '@/utils/error'
import { formatDateTime, formatPercentage } from '@/utils/format'
import {
  puzzleApi,
  type PuzzleBaselineKind,
  type PuzzlePackSummary,
  type PuzzlePreview,
  type PuzzleProbeReport,
  type PuzzleRunReport,
} from '@/api/puzzleApi'
import CompactRecordList from '@/components/common/CompactRecordList.vue'
import type { CompactRecord } from '@/components/common/CompactRecordList.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import UiButton from '@/components/ui/Button.vue'
import UiInput from '@/components/ui/Input.vue'
import UiSelect from '@/components/ui/Select.vue'
import UiSkeletonList from '@/components/ui/SkeletonList.vue'
import UiSpinner from '@/components/ui/Spinner.vue'

const props = defineProps<{
  experimentId?: string
}>()

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const packs = ref<PuzzlePackSummary[]>([])
const loading = ref(false)
const extracting = ref(false)
const detailLoading = ref(false)
const running = ref(false)
const probing = ref(false)

const selectedId = ref<string | null>(null)
const manifest = ref<PuzzlePackSummary | null>(null)
const preview = ref<PuzzlePreview[]>([])
const previewLimit = ref(5)

const extractIdInput = ref('')
const baselineKind = ref<PuzzleBaselineKind>('heuristic')
const runReport = ref<PuzzleRunReport | null>(null)
const probeReport = ref<PuzzleProbeReport | null>(null)
const showRunRows = ref(false)

const baselineOptions = computed(() => [
  { label: t('puzzle.baselineHeuristic'), value: 'heuristic' },
  { label: t('puzzle.baselineRandom'), value: 'random' },
  { label: t('puzzle.baselineFirst'), value: 'first' },
])

const effectiveExtractId = computed(
  () => props.experimentId?.trim() || extractIdInput.value.trim(),
)

const packRecords = computed<CompactRecord[]>(() =>
  packs.value.map((pack) => ({
    id: pack.pack_id,
    primary: pack.pack_id,
    secondary: t('puzzle.puzzleCount', { n: pack.puzzle_count }),
    meta: `${t('puzzle.sourceExperiment')} ${pack.source_experiment_id}`,
    trailing: formatDateTime(pack.created_at),
  })),
)

const routePackId = computed(() => {
  const v = route.query.pack_id
  return typeof v === 'string' && v ? v : ''
})

async function fetchPacks(): Promise<void> {
  loading.value = true
  try {
    const res = await puzzleApi.listPacks()
    packs.value = res.data
    const prefer = routePackId.value || selectedId.value
    if (prefer && packs.value.some((p) => p.pack_id === prefer)) {
      await selectPack(prefer)
    } else if (!selectedId.value && packs.value[0]) {
      await selectPack(packs.value[0].pack_id)
    } else if (selectedId.value && !packs.value.some((p) => p.pack_id === selectedId.value)) {
      selectedId.value = null
      manifest.value = null
      preview.value = []
      runReport.value = null
      probeReport.value = null
    }
  } catch (e: unknown) {
    showApiError(e, t('puzzle.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function selectPack(packId: string): Promise<void> {
  selectedId.value = packId
  runReport.value = null
  probeReport.value = null
  showRunRows.value = false
  previewLimit.value = 5
  if (route.query.pack_id !== packId) {
    void router.replace({
      path: route.path,
      query: { ...route.query, pack_id: packId },
    })
  }
  detailLoading.value = true
  try {
    const res = await puzzleApi.getPack(packId, previewLimit.value)
    manifest.value = res.data.manifest
    preview.value = res.data.preview
  } catch (e: unknown) {
    showApiError(e, t('puzzle.loadFailed'))
    manifest.value = null
    preview.value = []
  } finally {
    detailLoading.value = false
  }
}

async function loadMorePreview(): Promise<void> {
  if (!selectedId.value) return
  previewLimit.value = Math.min(50, previewLimit.value + 15)
  detailLoading.value = true
  try {
    const res = await puzzleApi.getPack(selectedId.value, previewLimit.value)
    preview.value = res.data.preview
  } catch (e: unknown) {
    showApiError(e, t('puzzle.loadFailed'))
  } finally {
    detailLoading.value = false
  }
}

async function extractPack(): Promise<void> {
  const experimentId = effectiveExtractId.value
  if (!experimentId) {
    toast.warning(t('puzzle.extractNeedId'))
    return
  }
  extracting.value = true
  try {
    const res = await puzzleApi.extract({ experiment_id: experimentId })
    toast.success(
      t('puzzle.extractDone', {
        id: res.data.pack_id,
        n: res.data.puzzle_count,
      }),
    )
    await fetchPacks()
    await selectPack(res.data.pack_id)
  } catch (e: unknown) {
    showApiError(e, t('error.operationFailed'))
  } finally {
    extracting.value = false
  }
}

async function runBaseline(): Promise<void> {
  if (!selectedId.value) return
  running.value = true
  probeReport.value = null
  try {
    const res = await puzzleApi.run(selectedId.value, {
      baseline_kind: baselineKind.value,
      seed: 0,
    })
    runReport.value = res.data
    toast.success(t('puzzle.runDone'))
  } catch (e: unknown) {
    showApiError(e, t('error.operationFailed'))
  } finally {
    running.value = false
  }
}

async function runProbe(): Promise<void> {
  if (!selectedId.value) return
  probing.value = true
  try {
    const res = await puzzleApi.probe(selectedId.value, {
      baseline_kind: baselineKind.value,
      seed: 0,
      n_trials: 3,
    })
    probeReport.value = res.data
    toast.success(t('puzzle.probeDone'))
  } catch (e: unknown) {
    showApiError(e, t('error.operationFailed'))
  } finally {
    probing.value = false
  }
}

function previewPhase(row: PuzzlePreview): string {
  return row.observation?.phase || '—'
}

onMounted(() => {
  if (props.experimentId) {
    extractIdInput.value = props.experimentId
  }
  void fetchPacks()
})

watch(
  () => props.experimentId,
  (id) => {
    if (id) extractIdInput.value = id
  },
)
</script>

<template>
  <div class="page-container space-y-ink-4">
    <p class="max-w-3xl text-body text-ink-text-secondary">{{ t('puzzle.intro') }}</p>

    <div class="flex flex-wrap items-end gap-ink-3">
      <div v-if="!experimentId" class="min-w-[14rem] flex-1">
        <label class="mb-1.5 block text-caption font-medium text-ink-text">
          {{ t('puzzle.experimentIdPh') }}
        </label>
        <UiInput v-model="extractIdInput" :placeholder="t('puzzle.experimentIdPh')" class="w-full" />
      </div>
      <UiButton :loading="extracting" @click="extractPack">{{ t('puzzle.extract') }}</UiButton>
      <UiButton variant="secondary" :loading="loading" @click="fetchPacks">
        {{ t('puzzle.refresh') }}
      </UiButton>
    </div>

    <div class="relative grid gap-ink-4 lg:grid-cols-[minmax(0,18rem)_minmax(0,1fr)]">
      <UiSpinner v-if="loading && packs.length === 0" overlay :label="t('common.loading')" />

      <section class="min-w-0">
        <EmptyState
          v-if="!loading && packs.length === 0"
          :title="t('puzzle.emptyTitle')"
          :description="t('puzzle.emptyHint')"
        />
        <UiSkeletonList v-else-if="loading && packs.length === 0" :rows="6" />
        <CompactRecordList
          v-else
          :records="packRecords"
          :selected-id="selectedId"
          @select="selectPack"
        />
      </section>

      <section class="min-w-0 space-y-ink-4">
        <div
          v-if="!selectedId"
          class="rounded-ink-md border border-ink-border px-ink-4 py-ink-6 text-body text-ink-text-muted"
        >
          {{ t('puzzle.detailEmpty') }}
        </div>

        <template v-else>
          <div class="relative space-y-ink-3 rounded-ink-md border border-ink-border p-ink-4">
            <UiSpinner v-if="detailLoading" overlay :label="t('common.loading')" />
            <template v-if="manifest">
              <div class="flex flex-wrap items-baseline justify-between gap-ink-2">
                <h2 class="text-title font-semibold text-ink-text">{{ manifest.pack_id }}</h2>
                <p class="text-caption text-ink-text-muted">
                  {{ formatDateTime(manifest.created_at) }} · {{ manifest.game_type }}
                </p>
              </div>
              <p class="text-caption text-ink-text-secondary">
                {{ t('puzzle.sourceExperiment') }}
                <RouterLink
                  class="text-ink-primary hover:underline"
                  :to="`/experiments/${manifest.source_experiment_id}`"
                >
                  {{ manifest.source_experiment_id }}
                </RouterLink>
                · {{ t('puzzle.puzzleCount', { n: manifest.puzzle_count }) }}
              </p>

              <div class="flex flex-wrap items-end gap-ink-3">
                <div class="min-w-[10rem]">
                  <label class="mb-1.5 block text-caption font-medium text-ink-text">
                    {{ t('puzzle.baseline') }}
                  </label>
                  <UiSelect
                    v-model="baselineKind"
                    :options="baselineOptions"
                    class="w-full"
                  />
                </div>
                <UiButton :loading="running" @click="runBaseline">{{ t('puzzle.run') }}</UiButton>
                <UiButton variant="secondary" :loading="probing" @click="runProbe">
                  {{ t('puzzle.probe') }}
                </UiButton>
              </div>

              <p v-if="runReport" class="text-body text-ink-text">
                {{
                  t('puzzle.runSummary', {
                    acc: formatPercentage(runReport.summary.accuracy),
                    loss: runReport.summary.mean_ev_loss.toFixed(3),
                    n: runReport.summary.n,
                  })
                }}
              </p>
              <p v-if="probeReport" class="text-body text-ink-text">
                {{
                  t('puzzle.probeSummary', {
                    cons: formatPercentage(probeReport.summary.consistency),
                    base: formatPercentage(probeReport.summary.base_accuracy),
                    pert: formatPercentage(probeReport.summary.pert_accuracy),
                  })
                }}
              </p>

              <div v-if="runReport" class="space-y-ink-2">
                <button
                  type="button"
                  class="text-caption text-ink-primary hover:underline"
                  @click="showRunRows = !showRunRows"
                >
                  {{ showRunRows ? t('puzzle.hideRows') : t('puzzle.showRows') }}
                </button>
                <ul
                  v-if="showRunRows"
                  class="max-h-48 space-y-ink-1 overflow-y-auto text-caption text-ink-text-secondary"
                >
                  <li v-for="row in runReport.puzzles" :key="row.puzzle_id" class="tabular-nums">
                    {{ row.puzzle_id }} ·
                    {{ row.hit ? t('puzzle.hit') : t('puzzle.miss') }} ·
                    {{ row.chosen_action_id }} → {{ row.best_action_id }} ·
                    ev_loss {{ row.ev_loss.toFixed(3) }}
                  </li>
                </ul>
              </div>
            </template>
          </div>

          <div class="space-y-ink-2">
            <div class="flex flex-wrap items-center justify-between gap-ink-2">
              <h3 class="text-body font-medium text-ink-text">{{ t('puzzle.preview') }}</h3>
              <UiButton
                v-if="manifest && preview.length < manifest.puzzle_count"
                variant="ghost"
                size="sm"
                :loading="detailLoading"
                @click="loadMorePreview"
              >
                {{ t('puzzle.loadMorePreview') }}
              </UiButton>
            </div>
            <ul class="divide-y divide-ink-border rounded-ink-md border border-ink-border">
              <li
                v-for="row in preview"
                :key="row.puzzle_id"
                class="px-ink-3 py-ink-2 text-caption"
              >
                <div class="flex flex-wrap items-baseline gap-ink-2">
                  <span class="font-medium text-ink-text">{{ row.puzzle_id }}</span>
                  <span class="text-ink-text-muted">
                    {{ t('puzzle.phase') }} {{ previewPhase(row) }}
                  </span>
                  <span class="text-ink-text-muted">
                    {{ t('puzzle.legalCount', { n: row.legal_action_count }) }}
                  </span>
                  <span v-if="row.truncated" class="text-ink-text-muted">
                    {{ t('puzzle.truncated') }}
                  </span>
                </div>
                <p class="mt-ink-1 text-ink-text-secondary">
                  {{ t('puzzle.bestAction') }}
                  <span class="font-mono">{{ row.best_action_id }}</span>
                  · spread {{ row.spread.toFixed(3) }}
                </p>
              </li>
            </ul>
          </div>
        </template>
      </section>
    </div>
  </div>
</template>
