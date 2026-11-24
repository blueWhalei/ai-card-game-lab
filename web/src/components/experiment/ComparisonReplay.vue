<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import {
  researchApi,
  type DecisionPair,
  type DecisionPairList,
  type PairedDecision,
} from '@/api/researchApi'
import { getErrorMessage } from '@/utils/error'
import DecisionPreview from '@/components/experiment/DecisionPreview.vue'
import ComparisonBoard from './ComparisonBoard.vue'
import EvidenceCiteButton from './EvidenceCiteButton.vue'
import UiButton from '@/components/ui/Button.vue'
import { EXPERIMENT_SCENARIO_IDS, type ExperimentScenarioId } from '@/utils/experimentWorkbench'
import { formatDateTime } from '@/utils/format'

const props = defineProps<{
  comparisonId: string
  playerNames: Record<string, string>
  citationDisabled: boolean
  included?: string[]
}>()
const emit = defineEmits<{ cite: [ids: string[]] }>()
const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const list = ref<DecisionPairList | null>(null)
const pair = ref<DecisionPair | null>(null)
const selectedSeed = ref<number | null>(null)
const step = ref(0)
const busy = ref(false)
const error = ref('')
const showAll = ref(false)
class PositionError extends Error {}
let request = 0
const scenario = computed(() => EXPERIMENT_SCENARIO_IDS.find((id) => id === route.query.scenario))
const selectedCounts = computed(() =>
  list.value?.groups.find((g) => g.scenario === (scenario.value ?? null)),
)
const selectedDeal = computed(() =>
  list.value?.items.find((item) => item.seed === selectedSeed.value),
)
const frame = computed(() => pair.value?.frames[step.value])
const previousMatch = computed(() =>
  pair.value?.matching_turns.filter((turn) => turn < (frame.value?.turn ?? 0)).at(-1),
)
const nextMatch = computed(() =>
  pair.value?.matching_turns.find((turn) => turn > (frame.value?.turn ?? 0)),
)
const sides = computed(() =>
  pair.value && frame.value
    ? [
        {
          label: 'A',
          run: pair.value.left,
          point: frame.value.left,
          ended: frame.value.left_ended,
          scenario: frame.value.left_scenario,
          boards: pair.value.boards?.left,
        },
        {
          label: 'B',
          run: pair.value.right,
          point: frame.value.right,
          ended: frame.value.right_ended,
          scenario: frame.value.right_scenario,
          boards: pair.value.boards?.right,
        },
      ]
    : [],
)
const citationIds = computed(() =>
  sides.value.flatMap((side) => (side.point ? [side.point.id] : [])),
)
function savePosition() {
  if (pair.value && frame.value)
    void router.replace({
      query: { ...route.query, seed: String(pair.value.seed), turn: String(frame.value.turn) },
    })
}
function selectStep(index: number) {
  if (!pair.value || index < 0 || index >= pair.value.frames.length) return
  step.value = index
  savePosition()
}
function selectTurn(turn: number | undefined) {
  if (turn !== undefined)
    selectStep(pair.value?.frames.findIndex((item) => item.turn === turn) ?? -1)
}
async function selectScenario(value?: ExperimentScenarioId) {
  await router.replace({
    query: { ...route.query, scenario: value, seed: undefined, turn: undefined },
  })
}
async function resetSelection() {
  const invalidScenario = route.query.scenario !== undefined && !scenario.value
  await router.replace({
    query: { ...route.query, scenario: scenario.value, seed: undefined, turn: undefined },
  })
  if (!invalidScenario) await loadList()
}
function readInteger(value: unknown): number | null {
  return typeof value === 'string' && /^-?\d+$/.test(value) && Number.isSafeInteger(Number(value))
    ? Number(value)
    : null
}
async function loadPair(seed: number, restore = false) {
  const version = ++request
  selectedSeed.value = seed
  pair.value = null
  showAll.value = false
  error.value = ''
  busy.value = true
  try {
    const { data } = await researchApi.pair(props.comparisonId, seed, scenario.value)
    if (version !== request) return
    if (data.seed !== seed || data.scenario !== (scenario.value ?? null))
      throw new PositionError(t('paired.positionMissing'))
    const requested = restore && route.query.turn !== undefined
    const turn = requested ? readInteger(route.query.turn) : (data.matching_turns[0] ?? 0)
    const index = data.frames.findIndex((item) => item.turn === turn)
    if (requested && index < 0) throw new PositionError(t('paired.positionMissing'))
    step.value = Math.max(0, index)
    pair.value = data
    savePosition()
  } catch (cause) {
    if (version === request)
      error.value = cause instanceof PositionError ? cause.message : getErrorMessage(cause)
  } finally {
    if (version === request) busy.value = false
  }
}
async function loadList() {
  const version = ++request
  busy.value = true
  error.value = ''
  pair.value = null
  list.value = null
  selectedSeed.value = null
  try {
    if (route.query.scenario !== undefined && !scenario.value)
      throw new PositionError(t('paired.positionMissing'))
    if (route.query.turn !== undefined && route.query.seed === undefined)
      throw new PositionError(t('paired.positionMissing'))
    const { data } = await researchApi.pairs(props.comparisonId, scenario.value)
    if (version !== request) return
    if (data.comparison_id !== props.comparisonId || data.scenario !== (scenario.value ?? null))
      throw new PositionError(t('paired.positionMissing'))
    list.value = data
    const requested = route.query.seed !== undefined
    const seed = requested ? readInteger(route.query.seed) : data.items[0]?.seed
    if (requested && !data.items.some((item) => item.seed === seed))
      throw new PositionError(t('paired.positionMissing'))
    if (seed !== undefined && seed !== null) await loadPair(seed, true)
  } catch (cause) {
    if (version === request)
      error.value = cause instanceof PositionError ? cause.message : getErrorMessage(cause)
  } finally {
    if (version === request) busy.value = false
  }
}
function decisionLink(point: PairedDecision) {
  return {
    path: '/pipeline/decisions',
    query: {
      game_id: point.game_id,
      experiment_id:
        pair.value?.left.game_id === point.game_id
          ? pair.value.left.experiment_id
          : pair.value?.right.experiment_id,
      decision_id: point.id,
      comparison_id: props.comparisonId,
      report_id: route.query.report_id,
      evidence: route.query.evidence,
      compare_seed: String(selectedSeed.value),
      compare_turn: String(frame.value?.turn),
      compare_scenario: scenario.value,
    },
  }
}
watch([() => props.comparisonId, () => route.query.scenario], loadList, { immediate: true })
watch([() => route.query.seed, () => route.query.turn], ([seed, turn]) => {
  if (busy.value || !list.value) return
  const parsedSeed = readInteger(seed)
  const parsedTurn = readInteger(turn)
  if (parsedSeed !== selectedSeed.value) {
    void loadList()
  } else if (pair.value && parsedTurn !== frame.value?.turn) {
    const index = pair.value.frames.findIndex((f) => f.turn === parsedTurn)
    if (index >= 0) step.value = index
    else {
      pair.value = null
      error.value = t('paired.positionMissing')
    }
  }
})
onBeforeUnmount(() => {
  request++
})
</script>

<template>
  <section
    id="comparison-evidence"
    class="space-y-ink-4"
    :aria-label="t('paired.title')"
    :aria-busy="busy"
  >
    <p class="max-w-3xl text-caption text-ink-text-secondary">{{ t('paired.scenarioScope') }}</p>
    <label class="flex flex-wrap items-center gap-ink-3 text-body">
      {{ t('paired.scenarioFilter') }}
      <select
        class="ink-input"
        :value="scenario ?? ''"
        @change="
          selectScenario(
            (($event.target as HTMLSelectElement).value as ExperimentScenarioId) || undefined,
          )
        "
      >
        <option value="">{{ t('scenarioRecords.names.all') }}</option>
        <option v-for="id in EXPERIMENT_SCENARIO_IDS" :key="id" :value="id">
          {{ t(`scenarioRecords.names.${id}`) }}
        </option>
      </select>
    </label>
    <template v-if="list">
      <p class="text-caption text-ink-text-muted">
        {{
          t('paired.scopeTime', {
            cutoff: formatDateTime(list.cutoff),
            time: formatDateTime(list.read_at),
            n: list.cohort_n,
          })
        }}
      </p>
      <p v-if="selectedCounts" class="text-body">
        {{ t('paired.scenarioCounts', selectedCounts) }}
      </p>
      <details class="text-caption text-ink-text-secondary">
        <summary class="cursor-pointer text-ink-primary">
          {{ t('scenarioRecords.definitions') }}
        </summary>
        <p>{{ t('scenarioRecords.rules', { n: list.endgame_max_hand }) }}</p>
        <p>{{ t('scenarioRecords.limits') }}</p>
        <p>{{ t('paired.scenarioLimits') }}</p>
      </details>
    </template>
    <div class="flex flex-wrap items-center justify-between gap-ink-3">
      <label v-if="list?.items.length" class="flex min-w-0 items-center gap-ink-2 text-caption">
        <span class="shrink-0">{{ t('paired.deal') }}</span>
        <select
          class="ink-input max-w-full"
          :value="selectedSeed"
          @change="loadPair(Number(($event.target as HTMLSelectElement).value))"
        >
          <option v-for="(item, index) in list.items" :key="item.seed" :value="item.seed">
            {{ t('paired.dealN', { n: index + 1, total: list.items.length }) }}
          </option>
        </select>
      </label>
      <UiButton
        v-if="pair?.first_divergence != null"
        variant="ghost"
        size="sm"
        @click="selectStep(pair.frames.findIndex((item) => item.turn === pair!.first_divergence))"
        >{{ t('paired.firstDifference') }}</UiButton
      >
    </div>
    <p v-if="selectedDeal" class="text-caption text-ink-text-secondary">
      {{ t('paired.dealCounts', selectedDeal) }}
    </p>
    <p v-if="busy" role="status" class="py-ink-6 text-body text-ink-text-secondary">
      {{ t('common.loading') }}
    </p>
    <div v-else-if="error" class="space-y-ink-3">
      <p role="alert" class="text-body text-ink-danger">{{ error }}</p>
      <UiButton
        variant="secondary"
        @click="list && selectedSeed !== null ? loadPair(selectedSeed, true) : loadList()"
        >{{ t('common.retry') }}</UiButton
      >
      <UiButton variant="ghost" @click="resetSelection">{{ t('paired.resetSelection') }}</UiButton>
    </div>
    <p v-else-if="!frame" class="py-ink-6 text-body text-ink-text-secondary">
      {{ t(scenario ? 'paired.emptyScenario' : 'paired.empty') }}
    </p>
    <template v-else-if="pair">
      <div v-if="scenario" class="flex flex-wrap items-center gap-ink-3">
        <UiButton
          variant="secondary"
          size="sm"
          :disabled="previousMatch === undefined"
          @click="selectTurn(previousMatch)"
          >{{ t('paired.previousMatch') }}</UiButton
        >
        <UiButton
          variant="secondary"
          size="sm"
          :disabled="nextMatch === undefined"
          @click="selectTurn(nextMatch)"
          >{{ t('paired.nextMatch') }}</UiButton
        >
        <span class="text-caption">{{
          t('paired.matches', { n: pair.matching_turns.length })
        }}</span>
      </div>
      <div class="flex flex-wrap items-center justify-between gap-ink-3">
        <p role="status" class="text-body font-medium text-ink-text">
          {{ t(`paired.status.${frame.status}`) }}
        </p>
        <div class="flex items-center gap-ink-2">
          <UiButton
            variant="secondary"
            size="sm"
            :disabled="step === 0"
            @click="selectStep(step - 1)"
            >{{ t('paired.previous') }}</UiButton
          >
          <span class="text-caption tabular-nums">{{
            t('paired.step', { n: step + 1, total: pair.frames.length })
          }}</span>
          <UiButton
            variant="secondary"
            size="sm"
            :disabled="step === pair.frames.length - 1"
            @click="selectStep(step + 1)"
            >{{ t('paired.next') }}</UiButton
          >
        </div>
      </div>
      <input
        type="range"
        class="w-full accent-ink-primary"
        min="0"
        :max="pair.frames.length - 1"
        :value="step"
        :aria-label="t('paired.timeline')"
        :aria-valuetext="t('paired.step', { n: step + 1, total: pair.frames.length })"
        @input="selectStep(Number(($event.target as HTMLInputElement).value))"
      />
      <div class="space-y-ink-2 text-caption text-ink-text-secondary">
        <p v-if="pair.boards">
          {{
            t('pairedBoard.basis', {
              version: pair.boards.engine_version,
              cutoff: formatDateTime(pair.boards.cutoff),
              read: formatDateTime(pair.boards.read_at),
            })
          }}
        </p>
        <label class="flex items-center gap-ink-2"
          ><input v-model="showAll" type="checkbox" />{{ t('pairedBoard.showAll') }}</label
        >
        <p>{{ t(showAll ? 'pairedBoard.allScope' : 'pairedBoard.actorScope') }}</p>
        <p>{{ t('pairedBoard.limits') }}</p>
      </div>
      <div class="grid gap-ink-4 lg:grid-cols-2">
        <article
          v-for="side in sides"
          :key="side.label"
          class="min-w-0 space-y-ink-4 rounded-ink-md border border-ink-border bg-ink-surface p-ink-6"
        >
          <h3 class="break-words text-body font-semibold">
            {{ side.label }} · {{ side.run.name }}
          </h3>
          <template v-if="side.point">
            <p v-if="side.scenario" class="text-caption text-ink-text-secondary">
              {{ t(`scenarioRecords.names.${side.scenario}`)
              }}<span v-if="scenario">
                ·
                {{
                  t(side.scenario === scenario ? 'paired.matchesFilter' : 'paired.contextOnly')
                }}</span
              >
            </p>
            <p class="text-caption text-ink-text-secondary">
              {{ playerNames[side.point.player_id] ?? side.point.player_id }}
            </p>
            <ComparisonBoard
              :boards="side.boards"
              :point="side.point"
              :show-all="showAll"
              :player-names="playerNames"
            />
            <DecisionPreview :point="side.point" :action-id="side.point.action_id" />
            <div class="flex flex-wrap items-center gap-ink-3">
              <RouterLink
                :to="decisionLink(side.point)"
                class="inline-block text-body text-ink-primary hover:underline"
                >{{ t('focus.inspectDecision') }}</RouterLink
              >
              <EvidenceCiteButton
                :ids="[side.point.id]"
                :included="included ?? []"
                :disabled="citationDisabled"
                @cite="emit('cite', $event)"
              />
            </div>
          </template>
          <p v-else class="py-ink-6 text-body text-ink-text-secondary">
            {{ t(side.ended ? 'paired.ended' : 'paired.missing') }}
          </p>
        </article>
      </div>
      <div class="flex flex-wrap items-center justify-between gap-ink-3">
        <p class="max-w-2xl text-caption text-ink-text-secondary">{{ t('paired.scope') }}</p>
        <EvidenceCiteButton
          :ids="citationIds"
          :included="included ?? []"
          :disabled="citationDisabled"
          pair
          @cite="emit('cite', $event)"
        />
      </div>
      <details class="space-y-ink-2 text-caption text-ink-text-muted">
        <summary class="cursor-pointer">{{ t('paired.basis') }}</summary>
        <p>{{ t('paired.method') }}</p>
        <p>{{ t('paired.seed', { seed: pair.seed }) }}</p>
        <p v-for="reason in frame.reasons" :key="reason">{{ t(`paired.reason.${reason}`) }}</p>
        <p v-for="side in sides" :key="side.label" class="break-all">
          {{ side.label }} · {{ side.run.game_id }} · {{ side.point?.id ?? t('common.dash') }}
        </p>
      </details>
    </template>
  </section>
</template>
