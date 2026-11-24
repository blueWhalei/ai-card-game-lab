<script setup lang="ts">
import { promptDesignApi } from '@/api/promptDesignApi'
import { showApiError } from '@/utils/error'
import { metricLabel, seatLabel } from '@/utils/researchOutcome'
import { computed, ref } from 'vue'
import { useRoute, type LocationQueryRaw } from 'vue-router'
import { SCENARIO_QUERY_KEYS } from '@/utils/scenarioNavigation'
import { operationReturn } from '@/utils/studyOperations'
import ExperimentNotebookPanel from '@/components/experiment/ExperimentNotebookPanel.vue'
import { experimentOutcomeText } from '@/utils/experimentOutcomes'
import { Icon } from '@iconify/vue'
import { isBenchmarkExperiment } from '@/api/experimentApi'
import { useExperimentDetail } from '@/composables/useExperimentDetail'
import HeaderToggles from '@/components/common/HeaderToggles.vue'
import ExperimentBenchmarkReport from '@/components/experiment/ExperimentBenchmarkReport.vue'
import ExperimentControlDialog from '@/components/experiment/ExperimentControlDialog.vue'
import ExperimentMetaPanel from '@/components/experiment/ExperimentMetaPanel.vue'
import ExperimentStage from '@/components/experiment/ExperimentStage.vue'
import ExperimentTimeline from '@/components/experiment/ExperimentTimeline.vue'
import ExperimentGamesTab from '@/components/experiment/ExperimentGamesTab.vue'
import ExperimentPlayersTab from '@/components/experiment/ExperimentPlayersTab.vue'
import ExperimentScenarios from '@/components/experiment/ExperimentScenarios.vue'
import { resolveStageId } from '@/utils/experimentStage'
import UiBadge from '@/components/ui/Badge.vue'
import UiButton from '@/components/ui/Button.vue'
import UiDialog from '@/components/ui/Dialog.vue'
import UiDropdownMenu from '@/components/ui/DropdownMenu.vue'
import UiInput from '@/components/ui/Input.vue'
import UiInputNumber from '@/components/ui/InputNumber.vue'
import UiSkeletonList from '@/components/ui/SkeletonList.vue'

const {
  router,
  t,
  loading,
  experiment,
  summary,
  validation,
  experimentId,
  blockedMessage,
  noticeText,
  stageBusy,
  cancellingCollect,
  collectCount,
  remaining,
  collecting,
  collectOpen,
  collectCta,
  submitCollect,
  onStageAction,
  goCompareWithSuggested,
  openExperiment,
  openMenuItems,
  onOpenMenuSelect,
  statusOf,
  showBenchmarkReport,
  configLabel,
  protocol,
  protocolPlayers,
  protocolDrift,
  protocolSummaryBits,
  dealSeedCount,
  shortExperimentId,
  finishedCount,
  activeGames,
  runningGames,
  pausedGames,
  finishedGames,
  pausingAll,
  resumingAll,
  actionGameId,
  gameStatusLabel,
  openGame,
  pauseGame,
  resumeGame,
  pauseAllRunning,
  resumeAllPaused,
  controlOpen,
  controlName,
  controlTarget,
  controlPlayerIds,
  controlPairDeals,
  controlOpenCollectAfter,
  challengerOptions,
  configSelectOptions,
  canSubmitControl,
  creatingControl,
  submitControl,
  cloneOpen,
  cloneName,
  cloning,
  submitClone,
  registerOpen,
  registerEvalRatio,
  registerPreview,
  registeringTrain,
  submitRegister,
  archiveOpen,
  onNotebookSaved,
  downloadManifest,
  openCloneDialog,
} = useExperimentDetail()
const route = useRoute()
const panels = ['conditions', 'games', 'players', 'timeline', 'benchmark', 'scenarios'] as const
const inspector = computed<(typeof panels)[number] | null>({
  get: () => panels.find((panel) => panel === route.query.panel) ?? null,
  set: (panel) => {
    const query: LocationQueryRaw = { ...route.query, panel: panel ?? undefined }
    if (panel !== 'scenarios') for (const key of SCENARIO_QUERY_KEYS) delete query[key]
    void router.replace({ query })
  },
})
const inspectorTitle = computed(() =>
  t(
    {
      conditions: 'focus.conditions',
      games: 'focus.runDetails',
      players: 'focus.players',
      timeline: 'focus.timeline',
      benchmark: 'experiment.modeBenchmark',
      scenarios: 'scenarioRecords.title',
    }[inspector.value ?? 'conditions'],
  ),
)
const researchQuestion = computed(
  () =>
    experiment.value?.delta?.design_hypothesis ||
    experiment.value?.protocol?.design?.hypothesis ||
    experiment.value?.hypothesis?.trim(),
)
const reservingHoldout = ref(false)
async function openHoldout() {
  if (reservingHoldout.value || !experiment.value) return
  reservingHoldout.value = true
  const id = experiment.value.id
  try {
    const { data } = await promptDesignApi.holdout(id)
    if (experiment.value?.id === id) {
      inspector.value = null
      await router.push(`/experiments/${data.variant_id}`)
    }
  } catch (error) {
    showApiError(error, t('promptDesign.holdoutFailed'))
  } finally {
    reservingHoldout.value = false
  }
}

function cloneFromConditions() {
  inspector.value = null
  openCloneDialog()
}
</script>
<template>
  <div class="page-container research-page space-y-ink-6">
    <div v-if="loading">
      <UiSkeletonList :rows="6" />
    </div>

    <template v-else-if="experiment && summary">
      <header class="flex flex-wrap items-center justify-between gap-ink-3">
        <div class="flex min-w-0 items-center gap-ink-3">
          <UiButton
            variant="ghost"
            size="sm"
            @click="
              router.push(
                operationReturn(route.query, experiment.study_id) ??
                  (experiment.study_id ? `/research/${experiment.study_id}` : '/experiments'),
              )
            "
          >
            {{
              t(
                operationReturn(route.query, experiment.study_id)
                  ? 'operations.back'
                  : experiment.study_id
                    ? 'study.back'
                    : 'common.back',
              )
            }}
          </UiButton>
          <h1 class="min-w-0 truncate text-title font-semibold tracking-tight text-ink-text">
            {{ experiment.name }}
          </h1>
          <UiBadge :variant="statusOf(summary.status).variant" size="xs">
            {{ statusOf(summary.status).label }}
          </UiBadge>
          <UiBadge v-if="isBenchmarkExperiment(experiment)" variant="muted" size="xs">
            {{
              t(
                experiment.protocol?.dataset.holdout_for
                  ? 'focus.purpose.holdout'
                  : 'focus.purpose.development',
              )
            }}
          </UiBadge>
        </div>
        <div class="flex items-center gap-ink-1">
          <UiButton variant="ghost" size="sm" @click="inspector = 'conditions'">{{
            t('focus.conditions')
          }}</UiButton>
          <UiButton variant="ghost" size="sm" @click="archiveOpen = true">{{
            t('experiment.research.notes')
          }}</UiButton>
          <HeaderToggles class="hidden md:flex" />
          <UiDropdownMenu :items="openMenuItems" @select="onOpenMenuSelect">
            <UiButton variant="ghost" size="icon" :aria-label="t('common.more')">
              <Icon icon="lucide:ellipsis" class="h-4 w-4" />
            </UiButton>
          </UiDropdownMenu>
        </div>
      </header>

      <section v-if="researchQuestion" class="max-w-3xl space-y-ink-2">
        <p class="text-caption text-ink-text-muted">{{ t('focus.runQuestion') }}</p>
        <p class="whitespace-pre-wrap break-words text-lead text-ink-text">
          {{ researchQuestion }}
        </p>
      </section>
      <section class="py-ink-6">
        <ExperimentStage
          :experiment="experiment"
          :blocked-message="blockedMessage"
          :busy="stageBusy"
          :cancelling-collect="cancellingCollect"
          @action="onStageAction"
          @compare="goCompareWithSuggested"
          @open-experiment="openExperiment"
        />

        <div
          class="mt-ink-6 flex flex-wrap items-center justify-between gap-ink-3 border-t border-ink-border pt-ink-4"
        >
          <p v-if="summary.total_games > 0" class="text-caption text-ink-text-secondary">
            {{ experimentOutcomeText(summary) }}
          </p>
          <UiButton
            v-if="resolveStageId(experiment) !== 'verdict'"
            variant="ghost"
            size="sm"
            @click="goCompareWithSuggested"
          >
            {{ t('experiment.research.compare') }}
          </UiButton>
        </div>
      </section>

      <button
        v-if="noticeText && !blockedMessage"
        type="button"
        class="w-full rounded-ink border border-ink-border bg-ink-surface-muted/60 px-3 py-2 text-left text-caption text-ink-text-secondary hover:bg-ink-surface-muted"
        @click="router.push('/settings')"
      >
        {{ noticeText }}
      </button>

      <nav
        :aria-label="t('experiment.analysisLinks')"
        class="flex flex-wrap gap-ink-3 border-t border-ink-border pt-ink-4"
      >
        <UiButton
          v-if="finishedCount > 0 || activeGames.length > 0"
          variant="secondary"
          @click="inspector = 'games'"
        >
          {{ t('focus.runDetails') }} · {{ summary.total_games }}
        </UiButton>
        <UiButton v-if="finishedCount > 0" variant="ghost" @click="inspector = 'players'">{{
          t('focus.players')
        }}</UiButton>
        <UiButton
          v-if="experiment.game_type === 'doudizhu'"
          variant="ghost"
          @click="inspector = 'scenarios'"
          >{{ t('scenarioRecords.title') }}</UiButton
        >
        <UiButton variant="ghost" @click="inspector = 'timeline'">{{
          t('focus.timeline')
        }}</UiButton>
        <UiButton v-if="showBenchmarkReport" variant="ghost" @click="inspector = 'benchmark'">{{
          t('experiment.modeBenchmark')
        }}</UiButton>
      </nav>
      <UiDialog
        :open="inspector !== null"
        placement="side"
        :title="inspectorTitle"
        @update:open="!$event && (inspector = null)"
      >
        <template v-if="inspector === 'conditions'">
          <p v-if="experiment.protocol?.dataset.holdout_for" class="mb-ink-3 text-body">
            {{ t('focus.purpose.holdout') }} ·
            <RouterLink
              class="text-ink-primary hover:underline"
              :to="`/experiments/${experiment.protocol.dataset.holdout_for}`"
              >{{ t('promptDesign.origin') }}</RouterLink
            >
          </p>
          <section
            v-if="experiment.protocol?.design?.kind === 'prompt_ab'"
            class="mb-ink-6 space-y-ink-3"
          >
            <h3 class="text-body font-semibold">{{ t('promptDesign.savedDesign') }}</h3>
            <RouterLink
              v-if="experiment.protocol.design.source_revision_id"
              class="text-body text-ink-primary hover:underline"
              :to="{
                name: 'research-report',
                params: { id: experiment.protocol.design.source_revision_id },
              }"
            >
              {{ t('promptDesign.sourceConclusion') }}
            </RouterLink>
            <p class="break-words text-caption text-ink-text-secondary">
              {{ experiment.protocol.design.template_key }} ·
              {{
                t('promptDesign.affected', {
                  seats: experiment.protocol.design.affected_player_ids
                    .map((id) => seatLabel(id, protocolPlayers))
                    .join(', '),
                })
              }}
            </p>
            <p>{{ experiment.protocol.design.hypothesis }}</p>
            <p>
              {{ metricLabel(t, experiment.protocol.design.primary_metric, protocolPlayers) }} ·
              {{ t('promptDesign.contrast') }}
            </p>
            <UiButton
              variant="secondary"
              @click="router.push(`/experiments/${experiment.protocol.design.baseline_id}`)"
              >{{ t('promptDesign.openA') }}</UiButton
            >
            <div v-if="!experiment.protocol.dataset.holdout_for" class="space-y-ink-2">
              <p class="text-caption text-ink-text-secondary">
                {{ t('promptDesign.holdoutHint') }}
              </p>
              <UiButton variant="secondary" :loading="reservingHoldout" @click="openHoldout">{{
                t('promptDesign.openHoldout')
              }}</UiButton>
            </div>
          </section>
          <ExperimentMetaPanel
            :validation="validation"
            :protocol="protocol"
            :protocol-players="protocolPlayers"
            :protocol-drift="protocolDrift"
            :short-experiment-id="shortExperimentId"
            @download-manifest="downloadManifest"
            @clone="cloneFromConditions"
          />
        </template>
        <ExperimentGamesTab
          v-if="inspector === 'games'"
          :active-games="activeGames"
          :running-games="runningGames"
          :paused-games="pausedGames"
          :finished-games="finishedGames"
          :collect-cta="collectCta"
          :pausing-all="pausingAll"
          :resuming-all="resumingAll"
          :action-game-id="actionGameId"
          :config-label="configLabel"
          :game-status-label="gameStatusLabel"
          @open-game="openGame"
          @pause="pauseGame"
          @resume="resumeGame"
          @pause-all="pauseAllRunning"
          @resume-all="resumeAllPaused"
        />

        <div v-else-if="inspector === 'players'" class="space-y-ink-6">
          <ExperimentPlayersTab :summary="summary" :config-label="configLabel" />
        </div>
        <ExperimentScenarios
          v-else-if="inspector === 'scenarios'"
          :experiment-id="experimentId"
          :config-label="configLabel"
        />
        <ExperimentTimeline
          v-else-if="inspector === 'timeline'"
          :events="experiment.timeline"
          :control-progress="validation?.control_progress"
          @open-experiment="openExperiment"
        />
        <ExperimentBenchmarkReport
          v-else-if="inspector === 'benchmark'"
          :experiment="experiment"
          :config-label="configLabel"
        />
      </UiDialog>
    </template>

    <div v-else class="py-16 text-center text-ink-text-muted">{{ t('experiment.missing') }}</div>

    <UiDialog v-model:open="collectOpen" :title="collectCta">
      <p v-if="experiment && summary" class="mb-ink-4 text-body text-ink-text-secondary">
        {{
          t(
            isBenchmarkExperiment(experiment)
              ? 'stage.empty.detailBenchmark'
              : 'stage.empty.detail',
            { target: collectCount, players: experiment.player_ids.length },
          )
        }}
      </p>
      <div>
        <label class="mb-1.5 block text-body font-medium text-ink-text">
          {{ t('experiment.batchCount') }}
        </label>
        <UiInputNumber
          v-model="collectCount"
          :min="1"
          :max="Math.min(50, Math.max(remaining, 1))"
        />
      </div>
      <template #footer>
        <UiButton variant="secondary" @click="collectOpen = false">{{
          t('common.cancel')
        }}</UiButton>
        <UiButton :loading="collecting" @click="submitCollect">{{
          t('experiment.confirmStart')
        }}</UiButton>
      </template>
    </UiDialog>

    <ExperimentControlDialog
      v-model:open="controlOpen"
      v-model:name="controlName"
      v-model:target="controlTarget"
      v-model:playerIds="controlPlayerIds"
      v-model:pairDeals="controlPairDeals"
      v-model:openCollectAfter="controlOpenCollectAfter"
      :challenger-options="challengerOptions"
      :baseline-options="configSelectOptions"
      :can-submit="canSubmitControl"
      :loading="creatingControl"
      :protocol-summary-bits="protocolSummaryBits"
      :source-experiment-label="shortExperimentId(experimentId)"
      :seed-count="dealSeedCount"
      @submit="submitControl"
    />

    <UiDialog v-model:open="cloneOpen" :title="t('experiment.cloneTitle')">
      <label class="mb-1.5 block text-body font-medium text-ink-text">{{
        t('experiment.cloneName')
      }}</label>
      <UiInput v-model="cloneName" />
      <p v-if="experiment?.protocol?.dataset.holdout_for" class="text-caption">
        {{ t('promptDesign.cloneDeals') }}
      </p>
      <template #footer>
        <UiButton variant="secondary" @click="cloneOpen = false">{{ t('common.cancel') }}</UiButton>
        <UiButton :loading="cloning" @click="submitClone">{{
          t('experiment.cloneConfirm')
        }}</UiButton>
      </template>
    </UiDialog>

    <UiDialog v-model:open="registerOpen" :title="t('experiment.registerTitle')">
      <div class="space-y-3">
        <p class="text-body text-ink-text-secondary">
          {{ t('experiment.registerUsable', { n: registerPreview.usable }) }} ·
          {{ t('experiment.registerNotUsable', { n: registerPreview.notUsable }) }}
        </p>
        <div>
          <label class="mb-1.5 block text-body font-medium text-ink-text">
            {{ t('experiment.registerEvalRatio') }}
          </label>
          <UiInputNumber v-model="registerEvalRatio" :min="0" :max="0.5" :step="0.05" />
        </div>
        <p class="text-body text-ink-text-secondary">
          {{ t('experiment.registerSplitHint') }}
        </p>
      </div>
      <template #footer>
        <UiButton variant="secondary" @click="registerOpen = false">{{
          t('common.cancel')
        }}</UiButton>
        <UiButton :loading="registeringTrain" @click="submitRegister">
          {{ t('experiment.registerConfirm') }}
        </UiButton>
      </template>
    </UiDialog>

    <UiDialog v-model:open="archiveOpen" placement="side" :title="t('experiment.research.notes')">
      <ExperimentNotebookPanel
        v-if="experiment"
        :key="experiment.id"
        :experiment="experiment"
        flat
        @saved="onNotebookSaved"
      />
    </UiDialog>
  </div>
</template>
