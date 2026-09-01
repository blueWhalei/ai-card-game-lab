<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Icon } from '@iconify/vue'
import {
  experimentApi,
  experimentStatusLabel,
  EXPERIMENT_STATUS_VARIANT,
  type Experiment,
  type ExperimentStatus,
} from '@/api/experimentApi'
import { experimentConfigApi, type ExperimentConfig } from '@/api/experimentConfigApi'
import { systemApi, type StartupCheck } from '@/api/systemApi'
import { dataApi, type DataStats } from '@/api/dataApi'
import { trainingApi, type TrainingTask } from '@/api/trainingApi'
import { toast } from '@/components/ui/toast'
import { showApiError } from '@/utils/error'
import {
  initialControlPlayerIds,
  remainingCollectCount,
  sanitizeNamePart,
  uniqueFilledIds,
} from '@/utils/experimentWorkbench'
import ExperimentControlDialog from '@/components/experiment/ExperimentControlDialog.vue'
import ExperimentGamesTab from '@/components/experiment/ExperimentGamesTab.vue'
import ExperimentPlayersTab from '@/components/experiment/ExperimentPlayersTab.vue'
import ExperimentTrainingTab from '@/components/experiment/ExperimentTrainingTab.vue'
import type { GameItem } from '@/api/gameApi'
import { gameApi } from '@/api/gameApi'
import UiBadge from '@/components/ui/Badge.vue'
import UiButton from '@/components/ui/Button.vue'
import UiDialog from '@/components/ui/Dialog.vue'
import UiInputNumber from '@/components/ui/InputNumber.vue'
import UiProgress from '@/components/ui/Progress.vue'
import UiSkeletonList from '@/components/ui/SkeletonList.vue'
import { useTweenNumber } from '@/composables/useTweenNumber'
import { cn } from '@/lib/cn'

const { t } = useI18n()

type StageStatus = 'idle' | 'ready' | 'done'

type Stage = {
  id: string
  title: string
  status: StageStatus
  meta: string
}

const route = useRoute()
const router = useRouter()
const loading = ref(true)
const collecting = ref(false)
const collectOpen = ref(false)
const collectCount = ref(1)
const registeringTrain = ref(false)
const trainStartedLocal = ref(false)
const controlCreatedLocal = ref(false)
const trainingDepsAvailable = ref(false)
const completedModelCount = ref(0)
const trainingTasks = ref<TrainingTask[]>([])
const contentTab = ref<'games' | 'players' | 'training'>('games')
const controlOpen = ref(false)
const creatingControl = ref(false)
const actionGameId = ref<string | null>(null)
const pausingAll = ref(false)
const controlName = ref('')
const controlPlayerIds = ref<string[]>([])
const controlTarget = ref(5)
const experiment = ref<Experiment | null>(null)
const configs = ref<ExperimentConfig[]>([])
const startup = ref<StartupCheck | null>(null)
const scopedStats = ref<DataStats | null>(null)
let pollTimer: ReturnType<typeof setInterval> | null = null

const experimentId = computed(() => String(route.params.id ?? ''))

const configMap = computed(() => {
  const map = new Map<string, ExperimentConfig>()
  for (const c of configs.value) map.set(c.id, c)
  return map
})

function configLabel(id: string): string {
  return configMap.value.get(id)?.name ?? id
}

const summary = computed(() => experiment.value?.summary)
const finishedCount = computed(() => summary.value?.finished_games ?? 0)
const targetCount = computed(() => summary.value?.target_games ?? 0)
const usableCount = computed(() => summary.value?.train_usable_decisions ?? 0)
const winnerCount = computed(() => summary.value?.games_with_winner ?? 0)
const progressPct = computed(() => {
  if (targetCount.value <= 0) return 0
  return Math.min(100, (finishedCount.value / targetCount.value) * 100)
})
const finishedDisplay = useTweenNumber(finishedCount)
const usableDisplay = useTweenNumber(usableCount)
const winnerDisplay = useTweenNumber(winnerCount)

const canRegisterTrain = computed(
  () => (summary.value?.train_usable_decisions ?? 0) > 0 && !registeringTrain.value,
)

const collectCta = computed(() => {
  const status = summary.value?.status
  if (status === 'pending_collect') return t('experiment.startGames')
  if (status === 'ready_more' || status === 'ready_review') return t('experiment.runMore')
  return t('experiment.runMore')
})

const noticeText = computed(() => {
  if (!startup.value) return ''
  if (!startup.value.can_collect) {
    return t('experiment.apiKeyWarning')
  }
  if (startup.value.warnings.length > 0) {
    return startup.value.warnings[0] ?? ''
  }
  return ''
})

function stampSuffix(): string {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}`
}

const stages = computed((): Stage[] => {
  const s = summary.value
  const finished = s?.finished_games ?? 0
  const active = s?.active_games ?? 0
  const usable = s?.train_usable_decisions ?? 0
  const hasGames = (s?.total_games ?? 0) > 0

  const configStatus: StageStatus = 'done'
  let collectStatus: StageStatus = 'idle'
  if (active > 0) collectStatus = 'ready'
  else if (finished > 0) collectStatus = 'done'
  else if (hasGames) collectStatus = 'ready'

  let decisionStatus: StageStatus = 'idle'
  if (usable > 0) decisionStatus = 'done'
  else if (finished > 0) decisionStatus = 'ready'

  let trainStatus: StageStatus = 'idle'
  let trainMeta = t('experiment.waitUsable')
  if (trainStartedLocal.value) {
    trainStatus = 'done'
    trainMeta = t('experiment.trainStarted')
  } else if (usable > 0) {
    trainStatus = 'ready'
    trainMeta = trainingDepsAvailable.value
      ? t('experiment.canSaveTrain')
      : t('experiment.canSaveNoDeps')
  }

  const loraConfigs = configs.value.filter((c) => c.id.startsWith('lora_'))
  let deployStatus: StageStatus = 'idle'
  let deployMeta = t('experiment.deployAfterAdd')
  if (controlCreatedLocal.value) {
    deployStatus = 'done'
    deployMeta = t('experiment.controlOpened')
  } else if (loraConfigs.length > 0 || completedModelCount.value > 0) {
    deployStatus = 'ready'
    deployMeta =
      loraConfigs.length > 0
        ? t('experiment.loraPlayers', { n: loraConfigs.length })
        : t('experiment.trainedModels', { n: completedModelCount.value })
  }

  return [
    {
      id: 'config',
      title: t('experiment.stageConfig'),
      status: configStatus,
      meta: t('experiment.metaPlayers', { n: experiment.value?.player_ids.length ?? 0 }),
    },
    {
      id: 'collect',
      title: t('experiment.stageGames'),
      status: collectStatus,
      meta: t('experiment.metaGames', {
        finished,
        target: s?.target_games ?? 0,
      }),
    },
    {
      id: 'decisions',
      title: t('experiment.stageDecisions'),
      status: decisionStatus,
      meta: usable > 0 ? t('experiment.metaUsable', { n: usable }) : t('experiment.waitGameEnd'),
    },
    {
      id: 'train',
      title: t('experiment.stageTrain'),
      status: trainStatus,
      meta: trainMeta,
    },
    {
      id: 'deploy',
      title: t('experiment.stageDeploy'),
      status: deployStatus,
      meta: deployMeta,
    },
  ]
})

const configSelectOptions = computed(() =>
  configs.value.map((c) => ({
    label: `${c.name} (${c.model_config.provider}/${c.model_config.model_name})`,
    value: c.id,
  })),
)

const challengerOptions = computed(() => {
  const loras = configs.value.filter((c) => c.id.startsWith('lora_'))
  const pool = loras.length > 0 ? loras : configs.value
  return pool.map((c) => ({
    label: `${c.name} (${c.model_config.provider}/${c.model_config.model_name})`,
    value: c.id,
  }))
})

const canSubmitControl = computed(() => {
  return (
    controlName.value.trim().length > 0 &&
    uniqueFilledIds(controlPlayerIds.value) &&
    (controlTarget.value ?? 0) >= 1
  )
})

const activeGames = computed(() =>
  (experiment.value?.games ?? []).filter((g) =>
    ['created', 'running', 'paused', 'pending'].includes(g.status),
  ),
)

const finishedGames = computed(() =>
  (experiment.value?.games ?? []).filter(
    (g) => !['created', 'running', 'paused', 'pending'].includes(g.status),
  ),
)

const remaining = computed(() => {
  const s = summary.value
  if (!s) return 1
  return remainingCollectCount(s.target_games, s.finished_games)
})

const runningGames = computed(() =>
  activeGames.value.filter((g) => g.status === 'running'),
)

function patchLocalGameStatus(gameId: string, status: string): void {
  if (!experiment.value?.games) return
  experiment.value = {
    ...experiment.value,
    games: experiment.value.games.map((g) =>
      g.id === gameId ? { ...g, status } : g,
    ),
  }
}

async function pauseGame(gameId: string): Promise<void> {
  actionGameId.value = gameId
  try {
    await gameApi.pause(gameId)
    patchLocalGameStatus(gameId, 'paused')
    toast.success(t('experiment.paused'))
  } catch (e: unknown) {
    showApiError(e, t('experiment.pauseFailed'))
    await refreshQuiet()
  } finally {
    actionGameId.value = null
  }
}

async function resumeGame(gameId: string): Promise<void> {
  actionGameId.value = gameId
  try {
    await gameApi.resume(gameId)
    patchLocalGameStatus(gameId, 'running')
    toast.success(t('experiment.resumed'))
  } catch (e: unknown) {
    showApiError(e, t('experiment.resumeFailed'))
    await refreshQuiet()
  } finally {
    actionGameId.value = null
  }
}

async function pauseAllRunning(): Promise<void> {
  const ids = runningGames.value.map((g) => g.id)
  if (ids.length === 0) return
  pausingAll.value = true
  try {
    for (const id of ids) {
      await gameApi.pause(id)
      patchLocalGameStatus(id, 'paused')
    }
    toast.success(t('experiment.pausedN', { n: ids.length }))
  } catch (e: unknown) {
    showApiError(e, t('experiment.pauseAllFailed'))
    await refreshQuiet()
  } finally {
    pausingAll.value = false
  }
}

async function loadTrainingTasks(): Promise<void> {
  if (!experimentId.value) {
    trainingTasks.value = []
    return
  }
  try {
    const res = await trainingApi.listTasks({
      experiment_id: experimentId.value,
      page: 1,
      page_size: 20,
    })
    trainingTasks.value = res.data.items
    if (trainingTasks.value.some((task) => task.status === 'completed')) {
      trainStartedLocal.value = true
    }
  } catch {
    trainingTasks.value = []
  }
}

async function load(): Promise<void> {
  if (!experimentId.value) return
  loading.value = true
  try {
    const [expRes, cfgRes, startupRes, configRes, modelsRes] = await Promise.all([
      experimentApi.get(experimentId.value),
      experimentConfigApi.list(),
      systemApi.getStartupCheck().catch(() => null),
      systemApi.getConfig().catch(() => null),
      trainingApi.listModels().catch(() => null),
    ])
    experiment.value = expRes.data
    configs.value = cfgRes.data ?? []
    startup.value = startupRes?.data ?? null
    trainingDepsAvailable.value = configRes?.data.training_deps_available ?? false
    completedModelCount.value = (modelsRes?.data ?? []).filter(
      (m) => m.model_path && !m.model_path.endsWith('model.bin'),
    ).length
    collectCount.value = Math.min(remaining.value, 5)
    await Promise.all([loadTrainingTasks(), loadScopedStats()])
  } catch (e: unknown) {
    showApiError(e, t('experiment.loadDetailFailed'))
    experiment.value = null
  } finally {
    loading.value = false
  }
}

async function loadScopedStats(): Promise<void> {
  if (!experimentId.value) {
    scopedStats.value = null
    return
  }
  try {
    const res = await dataApi.stats({ experiment_id: experimentId.value })
    scopedStats.value = res.data
  } catch {
    scopedStats.value = null
  }
}

async function refreshQuiet(): Promise<void> {
  if (!experimentId.value) return
  try {
    const res = await experimentApi.get(experimentId.value)
    experiment.value = res.data
    await loadTrainingTasks()
    await loadScopedStats()
  } catch {
    /* ignore poll errors */
  }
}

function openCollect(): void {
  collectCount.value = Math.min(remaining.value, 5)
  collectOpen.value = true
}

async function submitCollect(): Promise<void> {
  if (!experiment.value) return
  const n = collectCount.value ?? 1
  if (n < 1 || n > 50) return
  collecting.value = true
  try {
    const res = await experimentApi.collect(experiment.value.id, { count: n })
    collectOpen.value = false
    toast.success(t('experiment.startedN', { n: res.data.count }))
    await refreshQuiet()
  } catch (e: unknown) {
    showApiError(e, t('experiment.collectFailed'))
  } finally {
    collecting.value = false
  }
}

function openLatest(): void {
  const id = summary.value?.latest_game_id
  if (!id) {
    toast.info(t('experiment.noGamesYet'))
    return
  }
  void router.push(`/game/${id}`)
}

function openGame(game: GameItem): void {
  void router.push(`/game/${game.id}`)
}

function goDecisions(): void {
  void router.push({
    path: '/decisions',
    query: { experiment_id: experimentId.value },
  })
}

function goTraces(): void {
  void router.push({
    path: '/traces',
    query: { experiment_id: experimentId.value },
  })
}

function goData(): void {
  void router.push({
    path: '/data',
    query: { experiment_id: experimentId.value },
  })
}

function goCompare(): void {
  void router.push({
    path: '/experiments/compare',
    query: { ids: experimentId.value },
  })
}

async function registerAndTrain(): Promise<void> {
  if (!experiment.value || !canRegisterTrain.value) return
  registeringTrain.value = true
  try {
    const stamp = stampSuffix()
    const base = sanitizeNamePart(experiment.value.name)
    const dsName = `${base}-chatml-${stamp}`
    const dsRes = await dataApi.createDatasetFromDecisions({
      name: dsName,
      game_type: experiment.value.game_type || 'doudizhu',
      experiment_id: experiment.value.id,
      train_usable_only: true,
      include_thinking: false,
    })
    const dataset = dsRes.data

    if (!trainingDepsAvailable.value) {
      toast.warning(
        t('experiment.savedNoDeps', { name: dataset.name, count: dataset.sample_count }),
      )
      return
    }

    try {
      const taskRes = await trainingApi.createTask({
        name: `${base}-sft-${stamp}`,
        dataset_id: dataset.id,
        training_type: 'sft',
        experiment_id: experiment.value.id,
      })
      trainStartedLocal.value = true
      await loadTrainingTasks()
      toast.success(t('experiment.trainStartedNamed', { name: taskRes.data.name }))
    } catch (e: unknown) {
      toast.success(t('experiment.savedNamed', { name: dataset.name, count: dataset.sample_count }))
      showApiError(e, t('experiment.trainStartFailed'))
    }
  } catch (e: unknown) {
    showApiError(e, t('experiment.saveDatasetFailed'))
  } finally {
    registeringTrain.value = false
  }
}

function openControlDialog(): void {
  if (!experiment.value) return
  const loras = configs.value.filter((c) => c.id.startsWith('lora_'))
  const challenger = loras[0]?.id ?? ''
  controlName.value = `${sanitizeNamePart(experiment.value.name)}${t('experiment.controlNameSuffix')}`
  controlPlayerIds.value = initialControlPlayerIds(
    experiment.value.player_ids.length,
    challenger,
    experiment.value.player_ids,
  )
  controlTarget.value = experiment.value.target_games || 5
  controlOpen.value = true
}

async function submitControl(): Promise<void> {
  if (!canSubmitControl.value) return
  creatingControl.value = true
  try {
    const res = await experimentApi.create({
      name: controlName.value.trim(),
      notes: t('experiment.controlNotes', {
        id: experimentId.value,
        challenger: controlPlayerIds.value[0] ?? '',
      }),
      game_type: experiment.value?.game_type || 'doudizhu',
      player_ids: controlPlayerIds.value,
      target_games: Number(controlTarget.value) || 5,
    })
    controlOpen.value = false
    controlCreatedLocal.value = true
    toast.success(t('experiment.controlCreated'))
    await router.push(`/experiments/${res.data.id}`)
  } catch (e: unknown) {
    showApiError(e, t('experiment.controlFailed'))
  } finally {
    creatingControl.value = false
  }
}

function statusOf(status: ExperimentStatus | undefined) {
  if (!status) return { label: t('common.dash'), variant: 'muted' as const }
  return {
    label: experimentStatusLabel(status),
    variant: EXPERIMENT_STATUS_VARIANT[status],
  }
}

function gameStatusLabel(status: string): string {
  switch (status) {
    case 'created':
      return t('experiment.gameStatus.created')
    case 'running':
      return t('experiment.gameStatus.running')
    case 'paused':
      return t('experiment.gameStatus.paused')
    case 'finished':
      return t('experiment.gameStatus.finished')
    case 'interrupted':
      return t('experiment.gameStatus.interrupted')
    case 'failed':
      return t('experiment.gameStatus.failed')
    default:
      return status
  }
}

watch(experimentId, () => {
  trainStartedLocal.value = false
  controlCreatedLocal.value = false
  void load()
})

watch(
  () => summary.value?.status,
  (status) => {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
    if (status === 'collecting') {
      pollTimer = setInterval(() => {
        void refreshQuiet()
      }, 4000)
    }
  },
  { immediate: true },
)

onMounted(() => {
  void load()
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<template>
  <div class="page-container space-y-6">
    <div v-if="loading">
      <UiSkeletonList :rows="6" />
    </div>

    <template v-else-if="experiment && summary">
      <div class="space-y-3">
        <button
          type="button"
          class="inline-flex items-center gap-1 text-sm text-ink-text-muted hover:text-ink-text"
          @click="router.push('/')"
        >
          <Icon icon="lucide:arrow-left" class="h-4 w-4" />
          {{ t('experiment.backToList') }}
        </button>

        <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div class="min-w-0 space-y-2">
            <div class="flex flex-wrap items-center gap-2">
              <h1 class="text-xl font-semibold text-ink-text">{{ experiment.name }}</h1>
              <UiBadge :variant="statusOf(summary.status).variant">
                {{ statusOf(summary.status).label }}
              </UiBadge>
              <span class="text-sm text-ink-text-secondary">
                {{
                  t('experiment.progressLabel', {
                    finished: summary.finished_games,
                    target: summary.target_games,
                  })
                }}
              </span>
            </div>
            <p v-if="experiment.notes" class="text-sm text-ink-text-muted">
              {{ experiment.notes }}
            </p>
            <div class="flex flex-wrap gap-1.5">
              <UiBadge
                v-for="pid in experiment.player_ids"
                :key="pid"
                variant="muted"
              >
                {{ configLabel(pid) }}
                <span v-if="summary.wins_by_config[pid]" class="ml-1 opacity-70">
                  ·{{ t('experiment.winsSuffix', { n: summary.wins_by_config[pid] }) }}
                </span>
              </UiBadge>
            </div>
          </div>

          <div class="flex flex-wrap gap-2">
            <UiButton variant="secondary" :disabled="!summary.latest_game_id" @click="openLatest">
              {{ t('experiment.openLatest') }}
            </UiButton>
            <UiButton
              variant="secondary"
              :disabled="!canRegisterTrain"
              :loading="registeringTrain"
              @click="registerAndTrain"
            >
              <Icon icon="lucide:brain" class="mr-1.5 h-4 w-4" />
              {{ t('experiment.saveAndTrain') }}
            </UiButton>
            <UiButton @click="openCollect">
              <Icon icon="lucide:play" class="mr-1.5 h-4 w-4" />
              {{ collectCta }}
            </UiButton>
          </div>
        </div>

        <button
          v-if="noticeText"
          type="button"
          class="w-full rounded-ink border border-ink-warning/40 bg-ink-warning/10 px-3 py-2 text-left text-sm text-ink-text-secondary hover:bg-ink-warning/15"
          @click="router.push('/settings')"
        >
          {{ noticeText }}
        </button>

        <!-- Compact pipeline + key stats -->
        <div
          class="flex flex-col gap-2 border-t border-ink-border pt-3 text-sm text-ink-text-secondary sm:flex-row sm:flex-wrap sm:items-center sm:justify-between"
        >
          <p class="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs sm:text-sm">
            <template v-for="(stage, idx) in stages" :key="stage.id">
              <span v-if="idx > 0" class="text-ink-text-muted">→</span>
              <span
                :class="
                  cn(
                    stage.status === 'done'
                      ? 'font-medium text-ink-success'
                      : stage.status === 'ready'
                        ? 'font-medium text-ink-primary'
                        : 'text-ink-text-muted',
                  )
                "
                :title="stage.meta"
              >
                {{ stage.title }}
              </span>
            </template>
          </p>
          <p class="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs tabular-nums sm:text-sm">
            <span>
              {{
                t('experiment.completed', {
                  finished: Math.round(finishedDisplay),
                  target: targetCount,
                })
              }}
            </span>
            <span class="text-ink-text-muted">
              {{ t('experiment.winnersCount', { n: Math.round(winnerDisplay) }) }}
            </span>
            <button
              type="button"
              class="text-ink-primary hover:underline"
              @click="goDecisions"
            >
              {{ t('experiment.trainUsableCount', { n: Math.round(usableDisplay) }) }}
            </button>
            <span class="text-ink-text-muted">
              {{ t('experiment.avgRounds', { n: summary.avg_rounds }) }}
            </span>
            <span v-if="scopedStats" class="text-ink-text-muted">
              Token {{ scopedStats.total_tokens }}
            </span>
            <span v-if="scopedStats" class="text-ink-text-muted">
              {{ t('experiment.avgResponse', { ms: Math.round(scopedStats.avg_response_time_ms || 0) }) }}
            </span>
          </p>
        </div>

        <UiProgress :value="progressPct" class="h-1.5" />

        <div class="flex flex-wrap gap-2">
          <UiButton variant="secondary" size="sm" @click="goDecisions">{{ t('nav.decisions') }}</UiButton>
          <UiButton variant="secondary" size="sm" @click="goTraces">{{ t('nav.traces') }}</UiButton>
          <UiButton variant="secondary" size="sm" @click="goData">{{ t('nav.data') }}</UiButton>
          <UiButton variant="secondary" size="sm" @click="goCompare">{{ t('experiment.compare') }}</UiButton>
          <UiButton variant="secondary" size="sm" @click="openControlDialog">
            {{ t('experiment.newRound') }}
          </UiButton>
        </div>
      </div>

      <div class="mb-1 flex gap-1 rounded-ink border border-ink-border bg-ink-surface-muted p-1 w-fit">
        <button
          type="button"
          class="rounded-[6px] px-3 py-1.5 text-sm font-medium transition-colors"
          :class="
            contentTab === 'games'
              ? 'bg-ink-surface text-ink-text shadow-[var(--ink-shadow)]'
              : 'text-ink-text-muted hover:text-ink-text'
          "
          @click="contentTab = 'games'"
        >
          {{ t('experiment.tabGames') }}
        </button>
        <button
          type="button"
          class="rounded-[6px] px-3 py-1.5 text-sm font-medium transition-colors"
          :class="
            contentTab === 'players'
              ? 'bg-ink-surface text-ink-text shadow-[var(--ink-shadow)]'
              : 'text-ink-text-muted hover:text-ink-text'
          "
          @click="contentTab = 'players'"
        >
          {{ t('experiment.tabPlayers') }}
        </button>
        <button
          type="button"
          class="rounded-[6px] px-3 py-1.5 text-sm font-medium transition-colors"
          :class="
            contentTab === 'training'
              ? 'bg-ink-surface text-ink-text shadow-[var(--ink-shadow)]'
              : 'text-ink-text-muted hover:text-ink-text'
          "
          @click="contentTab = 'training'"
        >
          {{ t('experiment.tabTraining') }}
          <span v-if="trainingTasks.length" class="ml-1 tabular-nums opacity-70">
            {{ trainingTasks.length }}
          </span>
        </button>
      </div>

      <ExperimentPlayersTab
        v-if="contentTab === 'players'"
        :summary="summary"
        :config-label="configLabel"
      />

      <ExperimentTrainingTab
        v-else-if="contentTab === 'training'"
        :tasks="trainingTasks"
        :experiment-id="experimentId"
      />

      <ExperimentGamesTab
        v-else
        :active-games="activeGames"
        :running-games="runningGames"
        :finished-games="finishedGames"
        :collect-cta="collectCta"
        :pausing-all="pausingAll"
        :action-game-id="actionGameId"
        :config-label="configLabel"
        :game-status-label="gameStatusLabel"
        @open-game="openGame"
        @pause="pauseGame"
        @resume="resumeGame"
        @pause-all="pauseAllRunning"
      />

    </template>

    <div v-else class="py-16 text-center text-ink-text-muted">{{ t('experiment.missing') }}</div>

    <UiDialog
      v-model:open="collectOpen"
      :title="t('experiment.collectTitle')"
      :description="t('experiment.collectDesc')"
    >
      <label class="block space-y-1.5">
        <span class="text-sm font-medium text-ink-text">{{ t('experiment.batchCount') }}</span>
        <UiInputNumber v-model="collectCount" :min="1" :max="50" />
      </label>
      <template #footer>
        <UiButton variant="secondary" @click="collectOpen = false">{{ t('common.cancel') }}</UiButton>
        <UiButton :loading="collecting" @click="submitCollect">{{ t('experiment.confirmStart') }}</UiButton>
      </template>
    </UiDialog>

    <ExperimentControlDialog
      v-model:open="controlOpen"
      v-model:name="controlName"
      v-model:target="controlTarget"
      v-model:playerIds="controlPlayerIds"
      :challenger-options="challengerOptions"
      :baseline-options="configSelectOptions"
      :can-submit="canSubmitControl"
      :loading="creatingControl"
      @submit="submitControl"
    />
  </div>
</template>
