<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { isBenchmarkExperiment, flattenProtocol, type Experiment } from '@/api/experimentApi'
import { remainingBenchmarkSeeds } from '@/utils/experimentBenchmark'
import { formatWinRate } from '@/utils/experimentWorkbench'
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
import UiInputNumber from '@/components/ui/InputNumber.vue'

const props = withDefaults(
  defineProps<{
    experiment: Experiment
    /** A blocking preflight check replaces the phase's own action. */
    blockedMessage?: string
    /** A trained model has already been registered as a player config. */
    hasChallenger?: boolean
    busy?: boolean
    collectCount?: number
    remainingCollect?: number
    cancellingCollect?: boolean
  }>(),
  {
    hasChallenger: false,
    busy: false,
    collectCount: 1,
    remainingCollect: 0,
    cancellingCollect: false,
  },
)

const emit = defineEmits<{
  action: [action: ExperimentStageAction]
  compare: []
  openExperiment: [id: string]
  conclusionSaved: []
  'update:collectCount': [value: number]
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
const usable = computed(() => summary.value.train_usable_decisions)
const notUsable = computed(() => summary.value.not_usable_decisions ?? 0)
const blocked = computed(() => Boolean(props.blockedMessage))
const collectMax = computed(() => Math.min(50, Math.max(props.remainingCollect, 1)))

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
    detail: t(isBenchmark.value ? 'stage.empty.detailBenchmark' : 'stage.empty.detail', {
      target: summary.value.target_games,
      players: props.experiment.player_ids.length,
    }),
    actionLabel: t('experiment.confirmStart'),
    action: 'collect' as ExperimentStageAction,
  }
})

const harvestAct = computed(() => {
  if (usable.value === 0) {
    if (blocked.value) {
      return {
        claim: t('stage.empty.blockedClaim'),
        detail: props.blockedMessage ?? '',
        actionLabel: t('stage.empty.blockedAction'),
        action: 'settings' as ExperimentStageAction,
        disabled: false,
        showCount: false,
      }
    }
    return {
      claim: t('stage.harvest.noneClaim'),
      detail: t('stage.harvest.noneDetail'),
      actionLabel: t('experiment.confirmStart'),
      action: 'collect' as ExperimentStageAction,
      disabled: false,
      showCount: true,
    }
  }
  if (props.experiment.next_step?.id === 'review_decisions') {
    return {
      claim: t('stage.harvest.reviewClaim', { n: usable.value }),
      detail: t('stage.harvest.reviewDetail', { n: notUsable.value }),
      actionLabel: t('stage.harvest.reviewAction'),
      action: 'review-decisions' as ExperimentStageAction,
      disabled: false,
      showCount: false,
    }
  }
  return {
    claim: t('stage.harvest.readyClaim'),
    detail:
      notUsable.value > 0
        ? t('stage.harvest.detail', { n: notUsable.value })
        : t('stage.harvest.detailClean'),
    actionLabel: t('stage.harvest.action'),
    action: 'train' as ExperimentStageAction,
    disabled: false,
    showCount: false,
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
      seeds:
        flattenProtocol(props.experiment.protocol)?.deal_seeds?.length ??
        summary.value.finished_games,
      rate: formatWinRate(summary.value.landlord_win_rate ?? 0),
    }),
    actionLabel: t('stage.control.action'),
    action: 'open-control' as ExperimentStageAction,
  }
})

const verdictAct = computed(() => {
  const delta = props.experiment.delta
  if (!delta || delta.can_conclude) return { actionLabel: undefined, action: undefined }
  const isThisRunShort = delta.relation === 'vs_source'
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
  if (remaining.value <= 0 || harvestAct.value.action === 'collect') return null
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

function onCollectCount(value: number | null): void {
  if (value == null) return
  emit('update:collectCount', value)
}
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
  >
    <template v-if="emptyAct.action === 'collect'" #before-action>
      <label class="flex items-center gap-ink-2 text-caption text-ink-text-muted">
        <span>{{ t('experiment.batchCount') }}</span>
        <UiInputNumber
          :model-value="collectCount"
          :min="1"
          :max="collectMax"
          @update:model-value="onCollectCount"
        />
      </label>
    </template>
  </StageAction>

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
    :metric-value="usable"
    :metric-label="t('stage.harvest.metricLabel')"
    :claim="harvestAct.claim"
    :detail="harvestAct.detail"
    :action-label="harvestAct.actionLabel"
    :action-disabled="harvestAct.disabled"
    :action-loading="busy"
    @action="emit('action', harvestAct.action)"
  >
    <template v-if="harvestAct.showCount" #before-action>
      <label class="flex items-center gap-ink-2 text-caption text-ink-text-muted">
        <span>{{ t('experiment.batchCount') }}</span>
        <UiInputNumber
          :model-value="collectCount"
          :min="1"
          :max="collectMax"
          @update:model-value="onCollectCount"
        />
      </label>
    </template>
    <template v-if="harvestCollectMore" #secondary>
      <label
        v-if="harvestCollectMore.action === 'collect'"
        class="flex items-center gap-ink-2 text-caption text-ink-text-muted"
      >
        <span>{{ t('experiment.batchCount') }}</span>
        <UiInputNumber
          :model-value="collectCount"
          :min="1"
          :max="collectMax"
          @update:model-value="onCollectCount"
        />
      </label>
      <UiButton
        variant="secondary"
        :loading="busy"
        @click="emit('action', harvestCollectMore.action)"
      >
        {{ harvestCollectMore.label }}
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
    :experiment-id="experiment.id"
    :existing-conclusion="experiment.conclusion"
    :delta="experiment.delta"
    :verdict-key="verdictKeyOf(experiment)"
    :games-needed="gamesNeededForPower(experiment)"
    :action-label="verdictAct.actionLabel"
    @action="verdictAct.action && emit('action', verdictAct.action)"
    @compare="emit('compare')"
    @open-peer="emit('openExperiment', experiment.delta.peer_id)"
    @conclusion-saved="emit('conclusionSaved')"
  />
</template>
