<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Icon } from '@iconify/vue'
import {
  experimentApi,
  experimentStatusLabel,
  experimentNextStepLabel,
  isBenchmarkExperiment,
  EXPERIMENT_STATUS_VARIANT,
  type Experiment,
  type ExperimentStatus,
} from '@/api/experimentApi'
import { experimentConfigApi, type ExperimentConfig } from '@/api/experimentConfigApi'
import { systemApi, type StartupCheck } from '@/api/systemApi'
import { dataApi } from '@/api/dataApi'
import { trainingApi, type TrainingTask } from '@/api/trainingApi'
import { toast } from '@/components/ui/toast'
import { showApiError } from '@/utils/error'
import {
  formatWinRate,
  formatWinRateCi,
  initialControlPlayerIds,
  remainingCollectCount,
  sanitizeNamePart,
  uniqueFilledIds,
} from '@/utils/experimentWorkbench'
import ExperimentControlDialog from '@/components/experiment/ExperimentControlDialog.vue'
import ExperimentNotebookPanel from '@/components/experiment/ExperimentNotebookPanel.vue'
import ExperimentGamesTab from '@/components/experiment/ExperimentGamesTab.vue'
import ExperimentPlayersTab from '@/components/experiment/ExperimentPlayersTab.vue'
import ExperimentTrainingTab from '@/components/experiment/ExperimentTrainingTab.vue'
import DecisionWorkbenchPanel from '@/components/decision/DecisionWorkbenchPanel.vue'
import TraceWorkbenchPanel from '@/components/trace/TraceWorkbenchPanel.vue'
import KpiStrip from '@/components/common/KpiStrip.vue'
import type { KpiItem } from '@/components/common/KpiStrip.vue'
import NameChips from '@/components/common/NameChips.vue'
import type { GameItem } from '@/api/gameApi'
import { gameApi } from '@/api/gameApi'
import UiBadge from '@/components/ui/Badge.vue'
import UiButton from '@/components/ui/Button.vue'
import UiDialog from '@/components/ui/Dialog.vue'
import UiDropdownMenu from '@/components/ui/DropdownMenu.vue'
import type { DropdownMenuItemDef } from '@/components/ui/DropdownMenu.vue'
import UiInput from '@/components/ui/Input.vue'
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
type ContentTab = 'games' | 'players' | 'training' | 'decisions' | 'traces'
const CONTENT_TABS: ContentTab[] = ['games', 'players', 'training', 'decisions', 'traces']
const contentTab = ref<ContentTab>('games')

function parseContentTab(raw: unknown): ContentTab {
  return typeof raw === 'string' && CONTENT_TABS.includes(raw as ContentTab)
    ? (raw as ContentTab)
    : 'games'
}

function setContentTab(tab: ContentTab): void {
  contentTab.value = tab
  const q: Record<string, string> = {}
  for (const [k, v] of Object.entries(route.query)) {
    if (typeof v === 'string' && v && k !== 'tab') q[k] = v
  }
  if (tab !== 'games') q.tab = tab
  void router.replace({ query: q })
}
const controlOpen = ref(false)
const cloneOpen = ref(false)
const cloneName = ref('')
const cloning = ref(false)
const registerOpen = ref(false)
const registerEvalRatio = ref(0.1)
const creatingControl = ref(false)
const actionGameId = ref<string | null>(null)
const pausingAll = ref(false)
const controlName = ref('')
const controlPlayerIds = ref<string[]>([])
const controlTarget = ref(5)
const controlPairDeals = ref(true)
const experiment = ref<Experiment | null>(null)
const configs = ref<ExperimentConfig[]>([])
const startup = ref<StartupCheck | null>(null)
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
const validation = computed(() => experiment.value?.validation ?? null)
const nextStep = computed(() => experiment.value?.next_step ?? null)
const protocol = computed(() => experiment.value?.protocol ?? null)
const protocolPlayers = computed(() => protocol.value?.players ?? [])
const protocolDrift = computed(() => {
  for (const frozen of protocolPlayers.value) {
    const live = configMap.value.get(frozen.id)
    if (!live) continue
    const lm = live.model_config
    const fm = frozen.model_config
    if (
      lm.provider !== fm.provider ||
      lm.model_name !== fm.model_name ||
      lm.temperature !== fm.temperature ||
      lm.top_p !== fm.top_p ||
      lm.max_tokens !== fm.max_tokens
    ) {
      return true
    }
  }
  return false
})
const pairedGamesCount = computed(() => summary.value?.paired_games ?? 0)
const dealSeedCount = computed(() => protocol.value?.deal_seeds?.length ?? 0)
const finishedCount = computed(() => summary.value?.finished_games ?? 0)
const targetCount = computed(() => summary.value?.target_games ?? 0)
const usableCount = computed(() => summary.value?.train_usable_decisions ?? 0)
const progressPct = computed(() => {
  if (targetCount.value <= 0) return 0
  return Math.min(100, (finishedCount.value / targetCount.value) * 100)
})
const usableDisplay = useTweenNumber(usableCount)

const protocolSummaryBits = computed(() => {
  const bits: string[] = []
  if (dealSeedCount.value > 0) {
    bits.push(t('experiment.protocolSeedsShort', { n: dealSeedCount.value }))
  }
  if (protocol.value?.pair_deals) {
    bits.push(
      t('experiment.protocolPairedShort', {
        paired: pairedGamesCount.value,
        total: summary.value?.total_games ?? 0,
      }),
    )
  }
  if (protocol.value?.prompt_version) {
    bits.push(t('experiment.protocolPromptShort', { v: protocol.value.prompt_version }))
  }
  return bits
})

function formatLatencyMs(ms: number): string {
  if (ms >= 1000) {
    const sec = ms / 1000
    return sec >= 10 ? `${Math.round(sec)}s` : `${sec.toFixed(1)}s`
  }
  return `${Math.round(ms)}ms`
}

function shortExperimentId(id: string): string {
  if (id.length <= 18) return id
  return `${id.slice(0, 8)}…${id.slice(-4)}`
}

const canRegisterTrain = computed(
  () => (summary.value?.train_usable_decisions ?? 0) > 0 && !registeringTrain.value,
)

const registerPreview = computed(() => {
  const usable = summary.value?.train_usable_decisions ?? 0
  const notUsable = summary.value?.not_usable_decisions ?? 0
  const gameEstimate = Math.max(1, Math.ceil((summary.value?.finished_games ?? 1) * registerEvalRatio.value))
  const evalCount = Math.max(0, Math.min(usable, gameEstimate))
  return { usable, notUsable, train: Math.max(0, usable - evalCount), eval: evalCount }
})

const collectCta = computed(() => {
  const status = summary.value?.status
  if (status === 'pending_collect') return t('experiment.startGames')
  if (status === 'ready_more' || status === 'ready_review') return t('experiment.runMore')
  return t('experiment.runMore')
})

const playerChipNames = computed(() =>
  (experiment.value?.player_ids ?? []).map((id) => {
    const wins = summary.value?.wins_by_config[id]
    const name = configLabel(id)
    return wins ? `${name} ·${wins}` : name
  }),
)

const openMenuItems = computed((): DropdownMenuItemDef[] => [
  {
    id: 'train',
    label: t('experiment.saveAndTrain'),
    disabled: !canRegisterTrain.value || registeringTrain.value,
  },
  { id: 'decisions', label: t('nav.decisions') },
  { id: 'traces', label: t('nav.traces') },
  { id: 'data', label: t('nav.data') },
  { id: 'compare', label: t('experiment.compare') },
  { id: 'control', label: t('experiment.newRound') },
])

function onOpenMenuSelect(id: string): void {
  switch (id) {
    case 'train':
      openRegisterDialog()
      break
    case 'decisions':
      goDecisions()
      break
    case 'traces':
      goTraces()
      break
    case 'data':
      goData()
      break
    case 'compare':
      goCompare()
      break
    case 'control':
      openControlDialog()
      break
    default:
      break
  }
}

const kpiItems = computed((): KpiItem[] => {
  const s = summary.value
  if (!s) return []
  const dash = t('common.dash')
  const failed = s.status_counts?.failed ?? 0
  return [
    {
      id: 'finished',
      label: t('experiment.kpiFinished'),
      value: `${s.finished_games}/${s.target_games}`,
    },
    {
      id: 'usable',
      label: t('experiment.kpiUsable'),
      value: String(Math.round(usableDisplay.value)),
      tone: 'primary',
      onClick: goDecisions,
    },
    {
      id: 'landlord',
      label: t('experiment.kpiLandlord'),
      value: (s.decisive_games ?? 0) > 0 ? formatWinRate(s.landlord_win_rate ?? 0) : dash,
      title: formatWinRateCi(s.landlord_win_rate_ci),
    },
    {
      id: 'parser',
      label: t('experiment.kpiParser'),
      value: (s.parser_n ?? 0) > 0 ? formatWinRate(s.parser_success_rate ?? 0) : dash,
    },
    {
      id: 'latency',
      label: t('experiment.kpiLatency'),
      value:
        (s.p50_response_ms ?? 0) > 0 || (s.p95_response_ms ?? 0) > 0
          ? `${formatLatencyMs(s.p50_response_ms ?? 0)} / ${formatLatencyMs(s.p95_response_ms ?? 0)}`
          : dash,
      title: t('experiment.latencyPercentiles', {
        p50: Math.round(s.p50_response_ms ?? 0),
        p95: Math.round(s.p95_response_ms ?? 0),
      }),
    },
    {
      id: 'tokens',
      label: t('experiment.kpiTokens'),
      value: (s.tokens_per_game ?? 0) > 0 ? String(Math.round(s.tokens_per_game ?? 0)) : dash,
      tone: failed > 0 ? 'danger' : 'default',
      title: failed > 0 ? t('experiment.failedCount', { n: failed }) : undefined,
    },
  ]
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
    await loadTrainingTasks()
  } catch (e: unknown) {
    showApiError(e, t('experiment.loadDetailFailed'))
    experiment.value = null
  } finally {
    loading.value = false
  }
}

async function refreshQuiet(): Promise<void> {
  if (!experimentId.value) return
  try {
    const res = await experimentApi.get(experimentId.value)
    experiment.value = res.data
    await loadTrainingTasks()
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
  setContentTab('decisions')
}

function goTraces(): void {
  setContentTab('traces')
}

function goData(): void {
  void router.push({
    path: '/data',
    query: { experiment_id: experimentId.value },
  })
}

function goCompareWithSuggested(): void {
  const ids = validation.value?.suggested_compare_ids ?? [experimentId.value]
  void router.push({
    path: '/experiments/compare',
    query: { ids: ids.join(',') },
  })
}

function handleNextStep(): void {
  const step = nextStep.value
  if (!step) return
  switch (step.action) {
    case 'collect':
      collectOpen.value = true
      break
    case 'games':
      setContentTab('games')
      break
    case 'decisions':
      setContentTab('decisions')
      break
    case 'train':
      openRegisterDialog()
      break
    case 'control':
      openControlDialog()
      break
    case 'compare':
      goCompareWithSuggested()
      break
    default:
      setContentTab('games')
      break
  }
}

function downloadManifest(): void {
  if (!experiment.value) return
  const payload = {
    experiment: {
      id: experiment.value.id,
      name: experiment.value.name,
      hypothesis: experiment.value.hypothesis,
      notes: experiment.value.notes,
      conclusion: experiment.value.conclusion,
      tags: experiment.value.tags,
      game_type: experiment.value.game_type,
      player_ids: experiment.value.player_ids,
      target_games: experiment.value.target_games,
      created_at: experiment.value.created_at,
    },
    protocol: experiment.value.protocol,
    summary: experiment.value.summary,
    timeline: experiment.value.timeline,
    validation: experiment.value.validation,
  }
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${experiment.value.id}-manifest.json`
  a.click()
  URL.revokeObjectURL(url)
}

function openCloneDialog(): void {
  if (!experiment.value) return
  cloneName.value = `${experiment.value.name} (copy)`
  cloneOpen.value = true
}

async function submitClone(): Promise<void> {
  if (!experiment.value || !cloneName.value.trim()) return
  cloning.value = true
  try {
    const res = await experimentApi.clone(experiment.value.id, {
      name: cloneName.value.trim(),
      copy_deal_seeds: true,
      copy_hypothesis: true,
    })
    cloneOpen.value = false
    toast.success(t('experiment.cloned'))
    void router.push(`/experiments/${res.data.id}`)
  } catch (e: unknown) {
    showApiError(e, t('experiment.cloneFailed'))
  } finally {
    cloning.value = false
  }
}

function onNotebookSaved(updated: Experiment): void {
  experiment.value = { ...experiment.value!, ...updated }
}

function openRegisterDialog(): void {
  registerEvalRatio.value = 0.1
  registerOpen.value = true
}

async function submitRegister(): Promise<void> {
  registerOpen.value = false
  await registerAndTrain(registerEvalRatio.value)
}

function goCompare(): void {
  void router.push({
    path: '/experiments/compare',
    query: { ids: experimentId.value },
  })
}

async function registerAndTrain(evalRatio = 0): Promise<void> {
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
      eval_ratio: evalRatio,
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
  controlPairDeals.value = true
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
      source_experiment_id: experimentId.value,
      pair_deals: controlPairDeals.value,
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

watch(
  () => route.query.tab,
  (tab) => {
    const next = parseContentTab(tab)
    if (contentTab.value !== next) contentTab.value = next
  },
  { immediate: true },
)

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
          class="inline-flex items-center gap-1 text-sm text-ink-text-secondary hover:text-ink-text"
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
              <UiBadge v-if="isBenchmarkExperiment(experiment)" variant="accent">
                {{ t('experiment.modeBenchmark') }}
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
            <p v-if="experiment.notes" class="text-sm text-ink-text-secondary">
              {{ experiment.notes }}
            </p>
            <NameChips :names="playerChipNames" :max="4" />
          </div>

          <div class="flex flex-wrap gap-2">
            <UiButton
              variant="secondary"
              :disabled="!summary.latest_game_id"
              @click="openLatest"
            >
              {{ t('experiment.openLatest') }}
            </UiButton>
            <UiDropdownMenu :items="openMenuItems" @select="onOpenMenuSelect">
              <UiButton variant="secondary" type="button">
                {{ t('common.open') }}
                <Icon icon="lucide:chevron-down" class="ml-1.5 h-3.5 w-3.5" />
              </UiButton>
            </UiDropdownMenu>
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

        <ExperimentNotebookPanel :experiment="experiment" @saved="onNotebookSaved" />

        <div
          v-if="nextStep"
          class="flex flex-wrap items-center justify-between gap-2 rounded-ink border border-ink-primary/30 bg-ink-primary-muted/40 px-3 py-2"
        >
          <p class="text-sm text-ink-text">{{ experimentNextStepLabel(nextStep.id) }}</p>
          <UiButton size="sm" @click="handleNextStep">
            {{ t('experiment.nextStepAction') }}
          </UiButton>
        </div>

        <div
          v-if="validation"
          class="flex flex-wrap items-center gap-2 rounded-ink border border-ink-border bg-ink-surface-muted px-3 py-2 text-xs text-ink-text-secondary sm:text-sm"
        >
          <span class="font-medium text-ink-text">{{ t('experiment.validationTitle') }}</span>
          <UiBadge :variant="validation.validation_ready ? 'success' : 'warning'">
            {{
              validation.validation_ready
                ? t('experiment.validationReady')
                : t('experiment.validationPending')
            }}
          </UiBadge>
          <span>{{ t('experiment.validationPaired', { n: validation.paired_n }) }}</span>
          <span>
            {{
              t('experiment.validationControls', {
                n: validation.control_experiment_ids.length,
              })
            }}
          </span>
          <button
            v-for="cid in validation.control_experiment_ids"
            :key="cid"
            type="button"
            class="text-ink-primary hover:underline"
            @click="router.push(`/experiments/${cid}`)"
          >
            {{ shortExperimentId(cid) }}
          </button>
        </div>

        <details
          v-if="protocol"
          class="group rounded-ink-md border border-ink-border bg-ink-surface-muted/40 open:bg-ink-surface-muted/60"
        >
          <summary
            class="flex cursor-pointer list-none items-center gap-2 px-3 py-2 text-sm marker:content-none [&::-webkit-details-marker]:hidden"
            :title="t('experiment.protocolFrozen')"
          >
            <Icon
              icon="lucide:chevron-right"
              class="h-3.5 w-3.5 shrink-0 text-ink-text-secondary transition-transform group-open:rotate-90"
            />
            <span class="font-medium text-ink-text">{{ t('experiment.protocolTitle') }}</span>
            <span
              v-if="protocolSummaryBits.length"
              class="min-w-0 truncate text-sm text-ink-text-secondary"
            >
              {{ protocolSummaryBits.join(' · ') }}
            </span>
            <span v-if="protocolDrift" class="ml-auto shrink-0 text-xs text-ink-warning">
              {{ t('experiment.protocolDriftShort') }}
            </span>
          </summary>
          <div class="space-y-2 border-t border-ink-border px-3 py-2.5 text-sm text-ink-text-secondary">
            <ul class="flex flex-wrap gap-1.5">
              <li
                v-for="p in protocolPlayers"
                :key="p.id"
                class="rounded-ink border border-ink-border bg-ink-surface px-2 py-0.5 tabular-nums"
              >
                <span class="font-medium text-ink-text">{{ p.name }}</span>
                <span class="text-ink-text-secondary">
                  · {{ p.model_config.model_name }} · T={{
                    p.model_config.temperature ?? t('common.dash')
                  }}
                </span>
              </li>
            </ul>
            <p
              v-if="protocol.pair_deals && protocol.source_experiment_id"
              class="text-ink-text-secondary"
              :title="protocol.source_experiment_id"
            >
              {{
                t('experiment.protocolSource', {
                  id: shortExperimentId(protocol.source_experiment_id),
                })
              }}
            </p>
            <div class="flex flex-wrap gap-2 pt-1">
              <UiButton size="sm" variant="secondary" @click="downloadManifest">
                {{ t('experiment.downloadManifest') }}
              </UiButton>
              <UiButton size="sm" variant="secondary" @click="openCloneDialog">
                {{ t('experiment.cloneExperiment') }}
              </UiButton>
            </div>
          </div>
        </details>

        <!-- Compact pipeline + KPI -->
        <div class="space-y-3 border-t border-ink-border pt-3">
          <p class="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-text-secondary sm:text-sm">
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
          <KpiStrip :items="kpiItems" />
        </div>

        <UiProgress :value="progressPct" class="h-1.5" />
      </div>

      <div class="mb-1 flex flex-wrap gap-1 rounded-ink border border-ink-border bg-ink-surface-muted p-1 w-fit">
        <button
          type="button"
          class="rounded-[6px] px-3 py-1.5 text-sm font-medium transition-colors"
          :class="
            contentTab === 'games'
              ? 'bg-ink-surface text-ink-text shadow-[var(--ink-shadow)]'
              : 'text-ink-text-secondary hover:text-ink-text'
          "
          @click="setContentTab('games')"
        >
          {{ t('experiment.tabGames') }}
        </button>
        <button
          type="button"
          class="rounded-[6px] px-3 py-1.5 text-sm font-medium transition-colors"
          :class="
            contentTab === 'players'
              ? 'bg-ink-surface text-ink-text shadow-[var(--ink-shadow)]'
              : 'text-ink-text-secondary hover:text-ink-text'
          "
          @click="setContentTab('players')"
        >
          {{ t('experiment.tabPlayers') }}
        </button>
        <button
          type="button"
          class="rounded-[6px] px-3 py-1.5 text-sm font-medium transition-colors"
          :class="
            contentTab === 'decisions'
              ? 'bg-ink-surface text-ink-text shadow-[var(--ink-shadow)]'
              : 'text-ink-text-secondary hover:text-ink-text'
          "
          @click="setContentTab('decisions')"
        >
          {{ t('experiment.tabDecisions') }}
          <span v-if="usableCount" class="ml-1 tabular-nums opacity-70">
            {{ usableCount }}
          </span>
        </button>
        <button
          type="button"
          class="rounded-[6px] px-3 py-1.5 text-sm font-medium transition-colors"
          :class="
            contentTab === 'traces'
              ? 'bg-ink-surface text-ink-text shadow-[var(--ink-shadow)]'
              : 'text-ink-text-secondary hover:text-ink-text'
          "
          @click="setContentTab('traces')"
        >
          {{ t('experiment.tabTraces') }}
        </button>
        <button
          type="button"
          class="rounded-[6px] px-3 py-1.5 text-sm font-medium transition-colors"
          :class="
            contentTab === 'training'
              ? 'bg-ink-surface text-ink-text shadow-[var(--ink-shadow)]'
              : 'text-ink-text-secondary hover:text-ink-text'
          "
          @click="setContentTab('training')"
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
        :validation="validation"
        @open-control="openControlDialog"
        @compare="goCompareWithSuggested"
      />

      <DecisionWorkbenchPanel
        v-else-if="contentTab === 'decisions'"
        :experiment-id="experimentId"
        embedded
      />

      <TraceWorkbenchPanel
        v-else-if="contentTab === 'traces'"
        :experiment-id="experimentId"
        embedded
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
      <div>
        <label class="mb-1.5 block text-sm font-medium text-ink-text">
          {{ t('experiment.batchCount') }}
        </label>
        <UiInputNumber v-model="collectCount" :min="1" :max="50" />
      </div>
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
      v-model:pairDeals="controlPairDeals"
      :challenger-options="challengerOptions"
      :baseline-options="configSelectOptions"
      :can-submit="canSubmitControl"
      :loading="creatingControl"
      @submit="submitControl"
    />

    <UiDialog v-model:open="cloneOpen" :title="t('experiment.cloneTitle')" :description="t('experiment.cloneDesc')">
      <label class="mb-1.5 block text-sm font-medium text-ink-text">{{ t('experiment.cloneName') }}</label>
      <UiInput v-model="cloneName" />
      <template #footer>
        <UiButton variant="secondary" @click="cloneOpen = false">{{ t('common.cancel') }}</UiButton>
        <UiButton :loading="cloning" @click="submitClone">{{ t('experiment.cloneConfirm') }}</UiButton>
      </template>
    </UiDialog>

    <UiDialog
      v-model:open="registerOpen"
      :title="t('experiment.registerTitle')"
      :description="t('experiment.registerDesc')"
    >
      <div class="space-y-3">
        <p class="text-sm text-ink-text-secondary">
          {{ t('experiment.registerUsable', { n: registerPreview.usable }) }} ·
          {{ t('experiment.registerNotUsable', { n: registerPreview.notUsable }) }}
        </p>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-text">
            {{ t('experiment.registerEvalRatio') }}
          </label>
          <UiInputNumber v-model="registerEvalRatio" :min="0" :max="0.5" :step="0.05" />
        </div>
        <p class="text-sm text-ink-text-secondary">
          {{ t('experiment.registerTrainCount', { n: registerPreview.train }) }} ·
          {{ t('experiment.registerEvalCount', { n: registerPreview.eval }) }}
        </p>
      </div>
      <template #footer>
        <UiButton variant="secondary" @click="registerOpen = false">{{ t('common.cancel') }}</UiButton>
        <UiButton :loading="registeringTrain" @click="submitRegister">
          {{ t('experiment.registerConfirm') }}
        </UiButton>
      </template>
    </UiDialog>
  </div>
</template>
