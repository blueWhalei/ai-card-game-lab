<script setup lang="ts">
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
  load,
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
</script>
<template>
  <div class="page-container research-page space-y-ink-6">
    <div v-if="loading">
      <UiSkeletonList :rows="6" />
    </div>

    <template v-else-if="experiment && summary">
      <header class="flex flex-wrap items-center justify-between gap-ink-3">
        <div class="flex min-w-0 items-center gap-ink-3">
          <UiButton variant="ghost" size="sm" @click="router.push('/')">
            {{ t('common.back') }}
          </UiButton>
          <h1 class="min-w-0 truncate text-title font-semibold tracking-tight text-ink-text">
            {{ experiment.name }}
          </h1>
          <UiBadge :variant="statusOf(summary.status).variant" size="xs">
            {{ statusOf(summary.status).label }}
          </UiBadge>
          <UiBadge v-if="isBenchmarkExperiment(experiment)" variant="muted" size="xs">
            {{ t('experiment.modeBenchmark') }}
          </UiBadge>
        </div>
        <div class="flex items-center gap-ink-1">
          <HeaderToggles class="hidden md:flex" />
          <UiDropdownMenu :items="openMenuItems" @select="onOpenMenuSelect">
            <UiButton variant="ghost" size="icon" :aria-label="t('common.more')">
              <Icon icon="lucide:ellipsis" class="h-4 w-4" />
            </UiButton>
          </UiDropdownMenu>
        </div>
      </header>

      <section :aria-label="t('experiment.research.title')" class="space-y-ink-3">
        <div class="flex flex-wrap items-center justify-between gap-ink-3">
          <h2 class="text-body font-semibold text-ink-text">
            {{ t('experiment.research.title') }}
          </h2>
          <div class="flex flex-wrap gap-ink-2">
            <UiButton variant="secondary" size="sm" @click="archiveOpen = true">
              {{ t('experiment.research.notes') }}
            </UiButton>
            <UiButton variant="secondary" size="sm" @click="goCompareWithSuggested">
              {{ t('experiment.research.compare') }}
            </UiButton>
            <UiButton variant="secondary" size="sm" @click="onStageAction('open-control')">
              {{ t('control.submit') }}
            </UiButton>
          </div>
        </div>
        <p class="max-w-3xl whitespace-pre-wrap break-words text-body text-ink-text-secondary">
          {{ experiment.hypothesis?.trim() || t('experiment.research.emptyHypothesis') }}
        </p>
        <p
          v-if="experiment.conclusion?.trim()"
          class="max-w-3xl whitespace-pre-wrap break-words text-body text-ink-text-secondary"
        >
          <span class="font-medium text-ink-text">{{ t('experiment.research.conclusion') }}</span>
          {{ experiment.conclusion }}
        </p>
      </section>

      <section class="rounded-ink-md border border-ink-border bg-ink-surface p-ink-6 md:p-ink-8">
        <ExperimentStage
          :experiment="experiment"
          :blocked-message="blockedMessage"
          :busy="stageBusy"
          v-model:collect-count="collectCount"
          :remaining-collect="remaining"
          :cancelling-collect="cancellingCollect"
          @action="onStageAction"
          @compare="goCompareWithSuggested"
          @open-experiment="openExperiment"
          @conclusion-saved="load"
        />

        <div
          class="mt-ink-6 flex flex-wrap items-center justify-between gap-ink-3 border-t border-ink-border pt-ink-4"
        >
          <p v-if="summary.total_games > 0" class="text-caption text-ink-text-secondary">
            {{ experimentOutcomeText(summary) }}
          </p>
          <nav
            :aria-label="t('experiment.analysisLinks')"
            class="flex flex-wrap gap-ink-4 text-body"
          >
            <RouterLink
              v-for="tool in ['data', 'decisions', 'traces']"
              :key="tool"
              :to="{
                path: `/pipeline/${tool}`,
                query: {
                  experiment_id: experimentId,
                  ...(tool === 'decisions' ? { train_usable: 'all' } : {}),
                },
              }"
              class="text-ink-primary underline-offset-4 hover:underline focus-visible:underline"
            >
              {{ t(`nav.${tool}`) }}
            </RouterLink>
          </nav>
        </div>
      </section>

      <ExperimentBenchmarkReport
        v-if="showBenchmarkReport"
        :experiment="experiment"
        :config-label="configLabel"
      />

      <button
        v-if="noticeText && !blockedMessage"
        type="button"
        class="w-full rounded-ink border border-ink-border bg-ink-surface-muted/60 px-3 py-2 text-left text-caption text-ink-text-secondary hover:bg-ink-surface-muted"
        @click="router.push('/settings')"
      >
        {{ noticeText }}
      </button>

      <ExperimentGamesTab
        v-if="finishedCount > 0 || activeGames.length > 0"
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

      <section v-if="finishedCount > 0" class="ink-section">
        <h2 class="ink-section-title">{{ t('stage.sectionPlayers') }}</h2>
        <div class="mt-ink-3">
          <ExperimentPlayersTab :summary="summary" :config-label="configLabel" />
        </div>
      </section>
      <ExperimentTimeline
        :events="experiment.timeline"
        :control-progress="validation?.control_progress"
        @open-experiment="openExperiment"
      />
    </template>

    <div v-else class="py-16 text-center text-ink-text-muted">{{ t('experiment.missing') }}</div>

    <UiDialog v-model:open="collectOpen" :title="collectCta">
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
          {{ t('experiment.registerTrainCount', { n: registerPreview.train }) }} ·
          {{ t('experiment.registerEvalCount', { n: registerPreview.eval }) }}
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

    <UiDialog v-model:open="archiveOpen" size="wide" :title="t('experiment.metaPanelTitle')">
      <ExperimentMetaPanel
        v-if="experiment"
        dialog
        :experiment="experiment"
        :validation="validation"
        :protocol="protocol"
        :protocol-players="protocolPlayers"
        :protocol-drift="protocolDrift"
        :protocol-summary-bits="protocolSummaryBits"
        :short-experiment-id="shortExperimentId"
        @saved="onNotebookSaved"
        @download-manifest="downloadManifest"
        @clone="openCloneDialog"
      />
      <template #footer>
        <UiButton variant="secondary" @click="archiveOpen = false">{{
          t('common.close')
        }}</UiButton>
      </template>
    </UiDialog>
  </div>
</template>
