<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { experimentApi } from '@/api/experimentApi'
import { experimentConfigApi, type ExperimentConfig } from '@/api/experimentConfigApi'
import type { SelectOption } from '@/components/ui/Select.vue'
import UiBadge from '@/components/ui/Badge.vue'
import UiButton from '@/components/ui/Button.vue'
import UiSelect from '@/components/ui/Select.vue'
import { mergeUniqueIds } from '@/utils/filterFacets'

/** Local filter bag when embedded (does not write route query). */
export type WorkbenchLocalFilters = {
  game_id?: string
  player_id?: string
  outcome?: string
  game_phase?: string
  min_quality?: string
  train_usable?: string
  model?: string
  parser_ok?: string
}

const props = withDefaults(
  defineProps<{
    mode: 'decision' | 'trace'
    /** Fallback player ids when not in an experiment (e.g. from loaded list). */
    playerCandidates?: string[]
    /** Fallback model ids from loaded traces. */
    modelCandidates?: string[]
    /** Lock scope to this experiment; filters stay local via `filters`. */
    lockedExperimentId?: string
    filters?: WorkbenchLocalFilters
  }>(),
  {
    playerCandidates: () => [],
    modelCandidates: () => [],
    lockedExperimentId: undefined,
    filters: undefined,
  },
)

const emit = defineEmits<{
  'update:filters': [WorkbenchLocalFilters]
}>()

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const configs = ref<ExperimentConfig[]>([])
const experimentPlayerIds = ref<string[]>([])
const experimentName = ref('')
const moreOpen = ref(false)

const localMode = computed(() => Boolean(props.lockedExperimentId))

function queryStr(key: string): string | undefined {
  const v = route.query[key]
  return typeof v === 'string' && v ? v : undefined
}

function localOrQuery(key: keyof WorkbenchLocalFilters): string {
  if (localMode.value) return props.filters?.[key] ?? ''
  return queryStr(key) ?? ''
}

const gameId = computed(() => {
  const v = localOrQuery('game_id')
  return v || undefined
})
const experimentId = computed(() => {
  if (props.lockedExperimentId) return props.lockedExperimentId
  return queryStr('experiment_id')
})
const playerId = computed(() => localOrQuery('player_id'))
const outcome = computed(() => localOrQuery('outcome'))
const model = computed(() => localOrQuery('model'))
const trainUsable = computed(() => {
  const v = localOrQuery('train_usable')
  if (v === 'true' || v === 'false') return v
  return props.mode === 'decision' ? 'true' : ''
})
const gamePhase = computed(() => localOrQuery('game_phase'))
const minQuality = computed(() => localOrQuery('min_quality'))
const parserOk = computed(() => localOrQuery('parser_ok'))

const scopeLabel = computed(() => {
  if (gameId.value) return t('filter.thisGame', { id: gameId.value })
  if (experimentId.value) {
    const name = experimentName.value.trim()
    return t('filter.thisExperiment', { name: name || experimentId.value })
  }
  return t('filter.all')
})

const scopeTitle = computed(() => {
  if (gameId.value) return gameId.value
  if (experimentId.value) {
    const name = experimentName.value.trim()
    return name ? `${name} (${experimentId.value})` : experimentId.value
  }
  return t('filter.noScope')
})

const hasScope = computed(() => Boolean(gameId.value || experimentId.value))
const canClearScope = computed(() => {
  if (localMode.value) return Boolean(gameId.value)
  return hasScope.value
})

const configName = (id: string): string =>
  configs.value.find((c) => c.id === id)?.name ?? id

const ALL = '__all__'

const facetScope = computed(() => `${gameId.value ?? ''}|${experimentId.value ?? ''}`)
const seenPlayers = ref<string[]>([])
const seenModels = ref<string[]>([])

watch(
  () => [facetScope.value, props.playerCandidates, playerId.value] as const,
  ([scope, ids, selected], prev) => {
    if (!prev || prev[0] !== scope) {
      seenPlayers.value = mergeUniqueIds(ids, [selected])
      return
    }
    seenPlayers.value = mergeUniqueIds(seenPlayers.value, ids, [selected])
  },
  { immediate: true },
)

watch(
  () => [facetScope.value, props.modelCandidates, model.value] as const,
  ([scope, ids, selected], prev) => {
    if (!prev || prev[0] !== scope) {
      seenModels.value = mergeUniqueIds(ids, [selected])
      return
    }
    seenModels.value = mergeUniqueIds(seenModels.value, ids, [selected])
  },
  { immediate: true },
)

const playerOptions = computed((): SelectOption[] => {
  const ids =
    experimentPlayerIds.value.length > 0
      ? mergeUniqueIds(experimentPlayerIds.value, [playerId.value])
      : seenPlayers.value
  return [
    { label: t('filter.allPlayers'), value: ALL },
    ...ids.map((id) => ({ label: configName(id), value: id })),
  ]
})

const outcomeOptions = computed((): SelectOption[] => [
  { label: t('filter.allOutcomes'), value: ALL },
  { label: t('filter.win'), value: 'win' },
  { label: t('filter.lose'), value: 'lose' },
])

const trainUsableOptions = computed((): SelectOption[] => [
  { label: t('filter.allTrain'), value: ALL },
  { label: t('filter.trainable'), value: 'true' },
  { label: t('filter.notTrainable'), value: 'false' },
])

const trainUsableModel = computed({
  get: () => {
    if (trainUsable.value === 'true' || trainUsable.value === 'false') return trainUsable.value
    return ALL
  },
  set: (v: string) => {
    patchFilters({ train_usable: v === ALL ? undefined : v })
  },
})

const modelOptions = computed((): SelectOption[] => {
  const ids = seenModels.value
  return [
    { label: t('filter.allModels'), value: ALL },
    ...ids.map((id) => ({ label: id, value: id })),
  ]
})

function patchLocal(patch: WorkbenchLocalFilters): void {
  const next: WorkbenchLocalFilters = { ...(props.filters ?? {}) }
  for (const [k, v] of Object.entries(patch) as [keyof WorkbenchLocalFilters, string | undefined][]) {
    if (v === undefined || v === '') delete next[k]
    else next[k] = v
  }
  emit('update:filters', next)
}

function patchQuery(patch: Record<string, string | undefined>): void {
  const next: Record<string, string> = {}
  for (const [k, v] of Object.entries(route.query)) {
    if (typeof v === 'string' && v) next[k] = v
  }
  for (const [k, v] of Object.entries(patch)) {
    if (v === undefined || v === '') delete next[k]
    else next[k] = v
  }
  if (!('page' in patch)) delete next.page
  void router.replace({ query: next })
}

function patchFilters(patch: WorkbenchLocalFilters): void {
  if (localMode.value) patchLocal(patch)
  else patchQuery(patch)
}

function clearScope(): void {
  if (localMode.value) {
    patchLocal({ game_id: undefined })
    return
  }
  patchQuery({ experiment_id: undefined, game_id: undefined })
}

function setPlayer(v: string): void {
  patchFilters({ player_id: v === ALL ? undefined : v })
}

function setOutcome(v: string): void {
  patchFilters({ outcome: v === ALL ? undefined : v })
}

function setModel(v: string): void {
  patchFilters({ model: v === ALL ? undefined : v })
}

function setParserOk(v: string): void {
  patchFilters({ parser_ok: v === ALL ? undefined : v })
}

function setPhase(v: string): void {
  patchFilters({ game_phase: v === ALL ? undefined : v })
}

function setMinQuality(v: string): void {
  patchFilters({ min_quality: v === ALL ? undefined : v })
}

const parserOkOptions = computed((): SelectOption[] => [
  { label: t('filter.allParser'), value: ALL },
  { label: t('filter.parseOk'), value: 'true' },
  { label: t('filter.ruleFallback'), value: 'false' },
])

const phaseOptions = computed((): SelectOption[] => [
  { label: t('filter.allPhases'), value: ALL },
  { label: t('game.phaseBidding'), value: 'bidding' },
  { label: t('game.phasePlaying'), value: 'playing' },
])

const minQualityOptions = computed((): SelectOption[] => [
  { label: t('filter.qualityAny'), value: ALL },
  { label: '≥ 0.5', value: '0.5' },
  { label: '≥ 0.7', value: '0.7' },
])

type ActiveChip = { key: string; label: string; clear: () => void }

const activeExtraChips = computed((): ActiveChip[] => {
  const chips: ActiveChip[] = []
  if (props.mode === 'decision') {
    if (outcome.value) {
      chips.push({
        key: 'outcome',
        label: `${t('filter.outcome')}: ${outcome.value === 'win' ? t('filter.win') : t('filter.lose')}`,
        clear: () => setOutcome(ALL),
      })
    }
    if (gamePhase.value) {
      const phaseLabel =
        gamePhase.value === 'bidding'
          ? t('game.phaseBidding')
          : gamePhase.value === 'playing'
            ? t('game.phasePlaying')
            : gamePhase.value
      chips.push({
        key: 'phase',
        label: `${t('filter.phase')}: ${phaseLabel}`,
        clear: () => setPhase(ALL),
      })
    }
    if (minQuality.value) {
      chips.push({
        key: 'quality',
        label: `${t('filter.quality')} ≥ ${minQuality.value}`,
        clear: () => setMinQuality(ALL),
      })
    }
  } else if (model.value) {
    chips.push({
      key: 'model',
      label: `${t('filter.model')}: ${model.value}`,
      clear: () => setModel(ALL),
    })
  }
  return chips
})

const hasExtraFilters = computed(() => activeExtraChips.value.length > 0)

async function loadConfigs(): Promise<void> {
  try {
    const res = await experimentConfigApi.list()
    configs.value = res.data ?? []
  } catch {
    configs.value = []
  }
}

async function loadExperimentPlayers(id: string | undefined): Promise<void> {
  if (!id) {
    experimentPlayerIds.value = []
    experimentName.value = ''
    return
  }
  try {
    const res = await experimentApi.get(id)
    experimentPlayerIds.value = res.data?.player_ids ?? []
    experimentName.value = res.data?.name ?? ''
  } catch {
    experimentPlayerIds.value = []
    experimentName.value = ''
  }
}

watch(experimentId, (id) => {
  void loadExperimentPlayers(id)
})

onMounted(() => {
  void loadConfigs()
  void loadExperimentPlayers(experimentId.value)
  if (props.mode === 'decision' && !localMode.value && route.query.train_usable === undefined) {
    patchQuery({ train_usable: 'true' })
  }
  if (
    props.mode === 'decision' &&
    localMode.value &&
    props.filters?.train_usable === undefined
  ) {
    patchLocal({ train_usable: 'true' })
  }
})
</script>

<template>
  <div class="space-y-2">
    <div
      class="flex flex-wrap items-center gap-2 rounded-ink-md border border-ink-border bg-ink-surface px-3 py-2.5"
    >
      <div class="flex min-w-0 flex-wrap items-center gap-2">
        <span class="text-xs text-ink-text-muted">{{ t('filter.scope') }}</span>
        <UiBadge
          :variant="hasScope ? 'accent' : 'muted'"
          class="max-w-[18rem] truncate"
          :title="scopeTitle"
        >
          {{ scopeLabel }}
        </UiBadge>
        <UiButton v-if="canClearScope" variant="ghost" size="sm" @click="clearScope">
          {{ t('filter.clearScope') }}
        </UiButton>
      </div>

      <div class="mx-1 hidden h-5 w-px bg-ink-border sm:block" />

      <UiSelect
        :model-value="playerId || ALL"
        :options="playerOptions"
        :placeholder="t('filter.player')"
        @update:model-value="setPlayer"
      />

      <template v-if="mode === 'decision'">
        <UiSelect
          v-model="trainUsableModel"
          :options="trainUsableOptions"
          :placeholder="t('filter.trainable')"
        />
      </template>
      <template v-else>
        <UiSelect
          :model-value="parserOk || ALL"
          :options="parserOkOptions"
          :placeholder="t('filter.parser')"
          @update:model-value="setParserOk"
        />
      </template>

      <UiButton variant="ghost" size="sm" @click="moreOpen = !moreOpen">
        <Icon
          :icon="moreOpen ? 'lucide:chevron-up' : 'lucide:sliders-horizontal'"
          class="mr-1 h-3.5 w-3.5"
        />
        {{ t('filter.more') }}
        <span
          v-if="hasExtraFilters"
          class="ml-1 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-ink-primary-muted px-1 text-[10px] tabular-nums text-ink-primary"
        >
          {{ activeExtraChips.length }}
        </span>
      </UiButton>
    </div>

    <div
      v-if="moreOpen"
      class="flex flex-wrap items-center gap-2 rounded-ink-md border border-dashed border-ink-border bg-ink-paper-elevated/60 px-3 py-2"
    >
      <template v-if="mode === 'decision'">
        <UiSelect
          :model-value="outcome || ALL"
          :options="outcomeOptions"
          :placeholder="t('filter.outcome')"
          @update:model-value="setOutcome"
        />
        <UiSelect
          :model-value="gamePhase || ALL"
          :options="phaseOptions"
          :placeholder="t('filter.phase')"
          @update:model-value="setPhase"
        />
        <UiSelect
          :model-value="minQuality || ALL"
          :options="minQualityOptions"
          :placeholder="t('filter.quality')"
          @update:model-value="setMinQuality"
        />
      </template>
      <template v-else>
        <UiSelect
          :model-value="model || ALL"
          :options="modelOptions"
          :placeholder="t('filter.model')"
          @update:model-value="setModel"
        />
      </template>
    </div>

    <div v-if="activeExtraChips.length" class="flex flex-wrap gap-1.5">
      <button
        v-for="chip in activeExtraChips"
        :key="chip.key"
        type="button"
        class="inline-flex items-center gap-1 rounded-[6px] bg-ink-surface-muted px-2 py-0.5 text-xs text-ink-text-secondary hover:bg-ink-primary-muted hover:text-ink-primary"
        @click="chip.clear()"
      >
        {{ chip.label }}
        <Icon icon="lucide:x" class="h-3 w-3" />
      </button>
    </div>
  </div>
</template>
