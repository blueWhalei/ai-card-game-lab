<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { isBenchmarkExperiment, type Experiment } from '@/api/experimentApi'
import { remainingBenchmarkSeeds } from '@/utils/experimentBenchmark'
import {
  remainingGames,
  resolveStageId,
  verdictKeyOf,
  type ExperimentStageAction,
} from '@/utils/experimentStage'
import StageAction from '@/components/experiment/StageAction.vue'
import StageVerdict from '@/components/experiment/StageVerdict.vue'
import UiButton from '@/components/ui/Button.vue'

const props = withDefaults(
  defineProps<{
    experiment: Experiment
    /** A blocking preflight check replaces the phase's own action. */
    blockedMessage?: string
    busy?: boolean
    cancellingCollect?: boolean
  }>(),
  {
    busy: false,
    cancellingCollect: false,
  },
)

const emit = defineEmits<{
  action: [action: ExperimentStageAction]
  compare: []
  openExperiment: [id: string]
}>()

const { t } = useI18n()

const stage = computed(() => resolveStageId(props.experiment))
const summary = computed(() => props.experiment.summary)
const isBenchmark = computed(() => isBenchmarkExperiment(props.experiment))
const remaining = computed(() =>
  isBenchmark.value && props.experiment.benchmark
    ? remainingBenchmarkSeeds(props.experiment)
    : remainingGames(props.experiment),
)
const blocked = computed(() => Boolean(props.blockedMessage))

const emptyAct = computed(() => {
  if (blocked.value) {
    return {
      claim: t('stage.empty.blockedClaim'),
      detail: props.blockedMessage ?? '',
      actionLabel: t('stage.empty.blockedAction'),
      action: 'settings' as ExperimentStageAction,
    }
  }
  return {
    claim: t('stage.empty.claim'),
    detail: t('focus.readyHint', {
      target: summary.value.target_games,
      players: props.experiment.player_ids.length,
    }),
    actionLabel: t('stage.empty.action'),
    action: 'collect' as ExperimentStageAction,
  }
})

const harvestAct = computed(() => ({
  claim: t('focus.finished'),
  detail: t('focus.finishedHint'),
  actionLabel: t('stage.harvest.reviewAction'),
  action: 'review-decisions' as ExperimentStageAction,
}))

const verdictAct = computed(() => {
  const delta = props.experiment.delta
  if (!delta || delta.can_conclude) return { actionLabel: undefined, action: undefined }
  if (delta.inconclusive_reason === 'protocol_mismatch')
    return { actionLabel: undefined, action: undefined }
  const isThisRunShort = delta.relation === 'vs_source'
  if (isThisRunShort && remaining.value <= 0) return { actionLabel: undefined, action: undefined }
  if (blocked.value && isThisRunShort) {
    return {
      actionLabel: t('stage.empty.blockedAction'),
      action: 'settings' as ExperimentStageAction,
    }
  }
  return {
    actionLabel: isThisRunShort
      ? t('stage.verdictAction.collectHere')
      : t('stage.verdictAction.collectControl'),
    action: (isThisRunShort ? 'collect' : 'collect-control') as ExperimentStageAction,
  }
})

/** Secondary “run more” on harvest — never a disabled collect when blocked. */
const harvestCollectMore = computed(() => {
  if (remaining.value <= 0) return null
  if (blocked.value) {
    return {
      label: t('stage.empty.blockedAction'),
      action: 'settings' as ExperimentStageAction,
      disabled: false,
    }
  }
  return {
    label: t(isBenchmark.value ? 'stage.collectMoreSeeds' : 'stage.collectMore', {
      n: remaining.value,
    }),
    action: 'collect' as ExperimentStageAction,
    disabled: false,
  }
})
</script>

<template>
  <StageAction
    v-if="stage === 'empty'"
    :claim="emptyAct.claim"
    :detail="emptyAct.detail"
    :action-label="emptyAct.actionLabel"
    :action-loading="busy"
    :action-disabled="emptyAct.action === 'collect' && blocked"
    weak
    @action="emit('action', emptyAct.action)"
  />

  <StageAction
    v-else-if="stage === 'collecting'"
    :metric-value="summary.finished_games"
    :metric-total="summary.target_games"
    :metric-label="t('stage.collecting.metricLabel')"
    :claim="t('stage.collecting.claim')"
    :detail="t('stage.collecting.detail', { active: summary.active_games })"
    :action-label="t('stage.collecting.action')"
    :action-disabled="!summary.latest_game_id"
    @action="emit('action', 'watch')"
  >
    <template #secondary>
      <UiButton
        variant="ghost"
        :loading="cancellingCollect"
        :disabled="summary.active_games <= 0"
        @click="emit('action', 'cancel-collect')"
      >
        {{ t('experiment.cancelCollect') }}
      </UiButton>
    </template>
  </StageAction>

  <StageAction
    v-else-if="stage === 'harvest'"
    :metric-value="summary.finished_games"
    :metric-label="t('stage.collecting.metricLabel')"
    :claim="harvestAct.claim"
    :detail="harvestAct.detail"
    :action-label="harvestAct.actionLabel"
    :action-loading="busy"
    @action="emit('action', harvestAct.action)"
  >
    <template v-if="harvestCollectMore" #secondary>
      <UiButton
        variant="secondary"
        :loading="busy"
        @click="emit('action', harvestCollectMore.action)"
      >
        {{ harvestCollectMore.label }}
      </UiButton>
    </template>
  </StageAction>

  <StageVerdict
    v-else-if="experiment.delta"
    :delta="experiment.delta"
    :players="experiment.protocol?.solver.players"
    :verdict-key="verdictKeyOf(experiment)"
    :run-name="experiment.name"
    :action-label="verdictAct.actionLabel"
    @action="verdictAct.action && emit('action', verdictAct.action)"
    @compare="emit('compare')"
    @open-peer="emit('openExperiment', experiment.delta.peer_id)"
  />
</template>
