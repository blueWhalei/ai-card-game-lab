<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { experimentApi } from '@/api/experimentApi'
import { experimentConfigApi, type ExperimentConfig } from '@/api/experimentConfigApi'
import type { SelectOption } from '@/components/ui/Select.vue'
import UiBadge from '@/components/ui/Badge.vue'
import UiButton from '@/components/ui/Button.vue'
import UiSelect from '@/components/ui/Select.vue'
import { mergeUniqueIds } from '@/utils/filterFacets'

const props = withDefaults(
  defineProps<{
    mode: 'decision' | 'trace'
    /** Fallback player ids when not in an experiment (e.g. from loaded list). */
    playerCandidates?: string[]
    /** Fallback model ids from loaded traces. */
    modelCandidates?: string[]
  }>(),
  {
    playerCandidates: () => [],
    modelCandidates: () => [],
  },
)

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const configs = ref<ExperimentConfig[]>([])
const experimentPlayerIds = ref<string[]>([])
const experimentName = ref('')

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
  return typeof v === 'string' ? v : ''
})
const outcome = computed(() => {
  const v = route.query.outcome
  return typeof v === 'string' ? v : ''
})
const model = computed(() => {
  const v = route.query.model
  return typeof v === 'string' ? v : ''
})
const trainUsable = computed(() => {
  const v = route.query.train_usable
  if (v === 'true' || v === 'false') return v
  return props.mode === 'decision' ? 'true' : ''
})

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
    patchQuery({ train_usable: v === ALL ? undefined : v })
  },
})

const modelOptions = computed((): SelectOption[] => {
  const ids = seenModels.value
  return [
    { label: t('filter.allModels'), value: ALL },
    ...ids.map((id) => ({ label: id, value: id })),
  ]
})

function patchQuery(patch: Record<string, string | undefined>): void {
  const next: Record<string, string> = {}
  for (const [k, v] of Object.entries(route.query)) {
    if (typeof v === 'string' && v) next[k] = v
  }
  for (const [k, v] of Object.entries(patch)) {
    if (v === undefined || v === '') delete next[k]
    else next[k] = v
  }
  // Filter changes reset to page 1
  if (!('page' in patch)) delete next.page
  void router.replace({ query: next })
}

function clearScope(): void {
  patchQuery({ experiment_id: undefined, game_id: undefined })
}

function setPlayer(v: string): void {
  patchQuery({ player_id: v === ALL ? undefined : v })
}

function setOutcome(v: string): void {
  patchQuery({ outcome: v === ALL ? undefined : v })
}

function setModel(v: string): void {
  patchQuery({ model: v === ALL ? undefined : v })
}

function setParserOk(v: string): void {
  patchQuery({ parser_ok: v === ALL ? undefined : v })
}

const parserOk = computed(() => {
  const v = route.query.parser_ok
  return typeof v === 'string' ? v : ''
})

const parserOkOptions = computed((): SelectOption[] => [
  { label: t('filter.allParser'), value: ALL },
  { label: t('filter.parseOk'), value: 'true' },
  { label: t('filter.ruleFallback'), value: 'false' },
])

function setPhase(v: string): void {
  patchQuery({ game_phase: v === ALL ? undefined : v })
}

function setMinQuality(v: string): void {
  patchQuery({ min_quality: v === ALL ? undefined : v })
}

const gamePhase = computed(() => {
  const v = route.query.game_phase
  return typeof v === 'string' ? v : ''
})
const minQuality = computed(() => {
  const v = route.query.min_quality
  return typeof v === 'string' ? v : ''
})

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
  // Decision default: ensure train_usable=true in URL when absent (matches prior default)
  if (props.mode === 'decision' && route.query.train_usable === undefined) {
    patchQuery({ train_usable: 'true' })
  }
})
</script>

<template>
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
      <UiButton v-if="hasScope" variant="ghost" size="sm" @click="clearScope">
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
      <UiSelect
        :model-value="parserOk || ALL"
        :options="parserOkOptions"
        :placeholder="t('filter.parser')"
        @update:model-value="setParserOk"
      />
    </template>
  </div>
</template>
