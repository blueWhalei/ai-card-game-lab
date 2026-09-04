<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Experiment } from '@/api/experimentApi'
import {
  gamesNeededForPower,
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
    /** A blocking preflight check replaces the act's own action. */
    blockedMessage?: string
    /** A trained model has already been registered as a player config. */
    hasChallenger?: boolean
    busy?: boolean
  }>(),
  {
    hasChallenger: false,
    busy: false,
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
const remaining = computed(() => remainingGames(props.experiment))
const usable = computed(() => summary.value.train_usable_decisions)
const notUsable = computed(() => summary.value.not_usable_decisions ?? 0)
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
    detail: t('stage.empty.detail', {
      target: summary.value.target_games,
      players: props.experiment.player_ids.length,
    }),
    actionLabel: t('stage.empty.action'),
    action: 'collect' as ExperimentStageAction,
  }
})

const harvestAct = computed(() => {
  if (usable.value === 0) {
    return {
      claim: t('stage.harvest.noneClaim'),
      detail: t('stage.harvest.noneDetail'),
      actionLabel: t('stage.harvest.noneAction'),
      action: 'collect' as ExperimentStageAction,
      disabled: blocked.value,
    }
  }
  if (props.experiment.next_step?.id === 'review_decisions') {
    return {
      claim: t('stage.harvest.reviewClaim', { n: usable.value }),
      detail: t('stage.harvest.reviewDetail', { n: notUsable.value }),
      actionLabel: t('stage.harvest.reviewAction'),
      action: 'review-decisions' as ExperimentStageAction,
      disabled: false,
    }
  }
  return {
    claim: t('stage.harvest.claim', { n: usable.value }),
    detail:
      notUsable.value > 0
        ? t('stage.harvest.detail', { n: notUsable.value })
        : t('stage.harvest.detailClean'),
    actionLabel: t('stage.harvest.action'),
    action: 'train' as ExperimentStageAction,
    disabled: false,
  }
})

const controlAct = computed(() => {
  if (!props.hasChallenger) {
    return {
      claim: t('stage.control.needPlayerClaim'),
      detail: t('stage.control.needPlayerDetail'),
      actionLabel: t('stage.control.needPlayerAction'),
      action: 'register-player' as ExperimentStageAction,
    }
  }
  return {
    claim: t('stage.control.claim'),
    detail: t('stage.control.detail', {
      seeds: props.experiment.protocol?.deal_seeds?.length ?? summary.value.finished_games,
    }),
    actionLabel: t('stage.control.action'),
    action: 'open-control' as ExperimentStageAction,
  }
})

const verdictAct = computed(() => {
  const delta = props.experiment.delta
  if (!delta || delta.can_conclude) return { actionLabel: undefined, action: undefined }
  // Top up whichever side is short of decisive games: this run when it *is*
  // the control, otherwise the control that was opened from here.
  const isThisRunShort = delta.relation === 'vs_source'
  return {
    actionLabel: isThisRunShort
      ? t('stage.verdictAction.collectHere')
      : t('stage.verdictAction.collectControl'),
    action: (isThisRunShort ? 'collect' : 'collect-control') as ExperimentStageAction,
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
  />

  <StageAction
    v-else-if="stage === 'harvest'"
    :metric-value="usable"
    :metric-label="t('stage.harvest.metricLabel')"
    :claim="harvestAct.claim"
    :detail="harvestAct.detail"
    :action-label="harvestAct.actionLabel"
    :action-disabled="harvestAct.disabled"
    :action-loading="busy"
    @action="emit('action', harvestAct.action)"
  >
    <template v-if="remaining > 0 && harvestAct.action !== 'collect'" #secondary>
      <UiButton variant="secondary" :disabled="blocked" @click="emit('action', 'collect')">
        {{ t('stage.collectMore', { n: remaining }) }}
      </UiButton>
    </template>
  </StageAction>

  <StageAction
    v-else-if="stage === 'control'"
    :claim="controlAct.claim"
    :detail="controlAct.detail"
    :action-label="controlAct.actionLabel"
    :action-loading="busy"
    @action="emit('action', controlAct.action)"
  />

  <StageVerdict
    v-else-if="experiment.delta"
    :delta="experiment.delta"
    :verdict-key="verdictKeyOf(experiment)"
    :games-needed="gamesNeededForPower(experiment)"
    :action-label="verdictAct.actionLabel"
    @action="verdictAct.action && emit('action', verdictAct.action)"
    @compare="emit('compare')"
    @open-peer="emit('openExperiment', experiment.delta.peer_id)"
  />
</template>
