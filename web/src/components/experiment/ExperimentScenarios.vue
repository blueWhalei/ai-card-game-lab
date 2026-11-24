<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { experimentApi, type ScenarioRecords, type ScenarioQuery } from '@/api/experimentApi'
import { scenarioPosition, scenarioQuery } from '@/utils/scenarioNavigation'
import { formatRolloutScope } from '@/utils/gameHighlights'
import { actionTypeLabel } from '@/utils/traceOutput'
import { formatDateTime } from '@/utils/format'
import DecisionPreview from './DecisionPreview.vue'
import UiButton from '@/components/ui/Button.vue'
import UiPagination from '@/components/ui/Pagination.vue'

const props = defineProps<{ experimentId: string; configLabel: (id: string) => string }>()
const { t, te } = useI18n()
const route = useRoute()
const router = useRouter()
const position = computed(() => scenarioPosition(route.query))
const data = ref<ScenarioRecords | null>(null)
const loading = ref(false)
const failed = ref(false)
let request = 0
onBeforeUnmount(() => request++)

async function load() {
  const token = ++request
  const id = props.experimentId
  const selection = position.value
  data.value = null
  failed.value = false
  loading.value = false
  if (!selection) {
    failed.value = true
    return
  }
  loading.value = true
  try {
    const response = await experimentApi.scenarios(id, selection)
    if (token !== request) return
    if (
      response.data.experiment_id !== id ||
      response.data.scenario !== (selection.scenario ?? null) ||
      (response.data.selected_game?.id ?? undefined) !== selection.game_id
    )
      throw new Error('Scenario scope mismatch')
    data.value = response.data
  } catch {
    if (token === request) failed.value = true
  } finally {
    if (token === request) loading.value = false
  }
}
watch([() => props.experimentId, position], load, { immediate: true })

function update(next: Partial<ScenarioQuery>) {
  const selected = { ...(position.value ?? { game_page: 1, page: 1 }), ...next }
  void router.replace({ query: { ...route.query, ...scenarioQuery(selected) } })
}
function chooseScenario(scenario?: ScenarioQuery['scenario']) {
  update({ scenario, game_id: undefined, decision_id: undefined, page: 1, game_page: 1 })
}
const selectedPoint = computed(() => {
  const records = data.value?.decisions.items ?? []
  return position.value?.decision_id
    ? records.find((point) => point.id === position.value?.decision_id)
    : records[0]
})
const detailLink = computed(() =>
  selectedPoint.value && position.value
    ? {
        name: 'decisions',
        query: {
          experiment_id: props.experimentId,
          game_id: selectedPoint.value.game_id,
          decision_id: selectedPoint.value.id,
          scenario_run: props.experimentId,
          ...scenarioQuery({ ...position.value, decision_id: selectedPoint.value.id }),
        },
      }
    : null,
)
function status(value: string) {
  const key = `game.status.${value}`
  return te(key) ? t(key) : value
}
</script>

<template>
  <section class="space-y-ink-5">
    <p class="text-body text-ink-text-secondary">{{ t('scenarioRecords.scope') }}</p>
    <div class="flex flex-wrap gap-ink-3">
      <UiButton variant="secondary" :disabled="loading" @click="load">{{
        t('scenarioRecords.refresh')
      }}</UiButton>
      <UiButton variant="ghost" @click="chooseScenario()">{{
        t('scenarioRecords.reset')
      }}</UiButton>
    </div>
    <p v-if="loading" role="status">{{ t('common.loading') }}</p>
    <p v-if="failed" role="alert" class="text-body">{{ t('scenarioRecords.failed') }}</p>
    <template v-if="data">
      <p class="text-caption text-ink-text-muted">
        {{ t('scenarioRecords.readAt', { time: formatDateTime(data.read_at) }) }}
      </p>
      <details class="space-y-ink-3 text-body text-ink-text-secondary">
        <summary class="cursor-pointer text-ink-primary">
          {{ t('scenarioRecords.definitions') }}
        </summary>
        <p>{{ t('scenarioRecords.rules', { n: data.endgame_max_hand }) }}</p>
        <p>{{ t('scenarioRecords.limits') }}</p>
      </details>
      <p class="text-caption text-ink-text-secondary">{{ t('scenarioRecords.denominators') }}</p>
      <div class="overflow-x-auto">
        <table class="w-full text-left text-caption tabular-nums">
          <thead>
            <tr class="border-b border-ink-border">
              <th class="py-ink-2">{{ t('scenarioRecords.group') }}</th>
              <th>{{ t('scenarioRecords.decisions') }}</th>
              <th>{{ t('scenarioRecords.games') }}</th>
              <th>{{ t('scenarioRecords.evaluated') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="group in [{ ...data.totals, scenario: undefined }, ...data.groups]"
              :key="group.scenario ?? 'all'"
              class="border-b border-ink-border"
            >
              <th class="py-ink-2 pr-ink-3 font-normal">
                <button
                  type="button"
                  class="text-ink-primary underline underline-offset-4"
                  :aria-pressed="position?.scenario === group.scenario"
                  @click="chooseScenario(group.scenario)"
                >
                  {{ t(`scenarioRecords.names.${group.scenario ?? 'all'}`) }}
                </button>
              </th>
              <td>{{ group.decision_n }}</td>
              <td>{{ group.game_n }}</td>
              <td>{{ group.evaluated_n }} / {{ group.decision_n }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-if="data.totals.unrecorded_game_n" class="text-caption text-ink-text-secondary">
        {{ t('scenarioRecords.unrecorded', { n: data.totals.unrecorded_game_n }) }}
      </p>
      <h3 class="text-body font-semibold">
        {{
          t('scenarioRecords.selectedGroup', {
            name: t(`scenarioRecords.names.${position?.scenario ?? 'all'}`),
          })
        }}
      </h3>
      <p v-if="!data.games.total" role="status">{{ t('scenarioRecords.empty') }}</p>
      <ul class="max-h-64 space-y-ink-2 overflow-y-auto">
        <li v-for="game in data.games.items" :key="game.id">
          <button
            type="button"
            class="w-full border-l-2 py-ink-2 pl-ink-3 text-left text-body"
            :class="
              game.id === data.selected_game?.id
                ? 'border-ink-primary text-ink-primary'
                : 'border-transparent text-ink-text-secondary'
            "
            :aria-pressed="game.id === data.selected_game?.id"
            @click="update({ game_id: game.id, decision_id: undefined, page: 1 })"
          >
            <span class="block break-all">{{ game.id }}</span>
            <span class="text-caption"
              >{{ status(game.status) }} ·
              {{
                t('scenarioRecords.gameCounts', { n: game.decision_n, evaluated: game.evaluated_n })
              }}</span
            >
          </button>
        </li>
      </ul>
      <UiPagination
        v-if="data.games.total > 20"
        fixed-page-size
        :page="data.games.page"
        :page-size="20"
        :total="data.games.total"
        @update:page="
          update({ game_page: $event, game_id: undefined, decision_id: undefined, page: 1 })
        "
      />
      <section v-if="data.selected_game" class="space-y-ink-4 border-t border-ink-border pt-ink-4">
        <h3 class="break-all text-body font-semibold">
          {{ t('scenarioRecords.selectedGame') }} · {{ data.selected_game.id }}
        </h3>
        <p class="text-caption text-ink-text-secondary">{{ t('scenarioRecords.sequence') }}</p>
        <p v-if="!data.decisions.items.length" role="status">
          {{ t('scenarioRecords.emptyPage') }}
        </p>
        <ul
          class="flex max-h-40 flex-wrap gap-ink-2 overflow-y-auto"
          :aria-label="t('scenarioRecords.decisions')"
        >
          <li v-for="point in data.decisions.items" :key="point.id">
            <UiButton
              :variant="point.id === selectedPoint?.id ? 'primary' : 'secondary'"
              size="sm"
              @click="update({ decision_id: point.id })"
            >
              {{ t('scenarioRecords.turn', { n: point.round_number }) }} ·
              {{ props.configLabel(point.player_id) }} ·
              {{ actionTypeLabel(point.chosen_action.action_type) }}
            </UiButton>
          </li>
        </ul>
        <UiPagination
          v-if="data.decisions.total > 20"
          fixed-page-size
          :page="data.decisions.page"
          :page-size="20"
          :total="data.decisions.total"
          @update:page="update({ page: $event, decision_id: undefined })"
        />
        <div v-if="selectedPoint" class="space-y-ink-4">
          <DecisionPreview :point="selectedPoint" :action-id="selectedPoint.action_id" />
          <p v-if="selectedPoint.ev_loss == null" class="text-body">
            {{ t('scenarioRecords.unevaluated') }}
          </p>
          <template v-else>
            <p class="text-body">
              {{ t('decision.evLossLabel', { n: selectedPoint.ev_loss.toFixed(2) }) }}
            </p>
            <p class="text-caption text-ink-text-secondary">
              {{ formatRolloutScope(selectedPoint.evaluator_params, t) }}
            </p>
          </template>
          <RouterLink
            v-if="detailLink"
            :to="detailLink"
            class="inline-block text-body text-ink-primary underline underline-offset-4"
            >{{ t('scenarioRecords.openDecision') }}</RouterLink
          >
        </div>
      </section>
    </template>
  </section>
</template>
