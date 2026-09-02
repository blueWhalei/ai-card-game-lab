<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
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
import { systemApi, type PreflightResult } from '@/api/systemApi'
import { dataApi } from '@/api/dataApi'
import { trainingApi } from '@/api/trainingApi'
import { toast } from '@/components/ui/toast'
import { showApiError } from '@/utils/error'
import {
  initialControlPlayerIds,
  remainingCollectCount,
  sanitizeNamePart,
  uniqueFilledIds,
} from '@/utils/experimentWorkbench'
import ExperimentControlDialog from '@/components/experiment/ExperimentControlDialog.vue'
import ExperimentDetailContextBar from '@/components/experiment/ExperimentDetailContextBar.vue'
import ExperimentMetaPanel from '@/components/experiment/ExperimentMetaPanel.vue'
import ExperimentResultsStrip from '@/components/experiment/ExperimentResultsStrip.vue'
import ExperimentValidationStrip from '@/components/experiment/ExperimentValidationStrip.vue'
import ExperimentGamesTab from '@/components/experiment/ExperimentGamesTab.vue'
import ExperimentPlayersTab from '@/components/experiment/ExperimentPlayersTab.vue'
import PreflightBanner from '@/components/common/PreflightBanner.vue'
import type { GameItem } from '@/api/gameApi'
import { gameApi } from '@/api/gameApi'
import UiButton from '@/components/ui/Button.vue'
import UiDialog from '@/components/ui/Dialog.vue'
import type { DropdownMenuItemDef } from '@/components/ui/DropdownMenu.vue'
import UiInput from '@/components/ui/Input.vue'
import UiInputNumber from '@/components/ui/InputNumber.vue'
import UiSkeletonList from '@/components/ui/SkeletonList.vue'

const { t } = useI18n()

type ContentTab = 'games' | 'players'
const LEGACY_TABS = new Set(['decisions', 'traces', 'training'])

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
const contentTab = ref<ContentTab>('games')

function stripTabQuery(query: Record<string, unknown>): Record<string, string> {
  const q: Record<string, string> = {}
  for (const [k, v] of Object.entries(query)) {
    if (typeof v === 'string' && v && k !== 'tab') q[k] = v
  }
  return q
}

function parseContentTab(raw: unknown): ContentTab {
  return raw === 'players' ? 'players' : 'games'
}

function setContentTab(tab: ContentTab): void {
  contentTab.value = tab
  const q = stripTabQuery(route.query as Record<string, unknown>)
  if (tab === 'players') q.tab = 'players'
  void router.replace({ query: q })
}

const archiveOpen = ref(false)
const controlOpen = ref(false)
const cloneOpen = ref(false)
const cloneName = ref('')
const cloning = ref(false)
const registerOpen = ref(false)
const registerEvalRatio = ref(0.1)
const creatingControl = ref(false)
const actionGameId = ref<string | null>(null)
const pausingAll = ref(false)
const resumingAll = ref(false)
const controlName = ref('')
const controlPlayerIds = ref<string[]>([])
const controlTarget = ref(5)
const controlPairDeals = ref(true)
const controlOpenCollectAfter = ref(true)
const experiment = ref<Experiment | null>(null)
const configs = ref<ExperimentConfig[]>([])
const preflight = ref<PreflightResult | null>(null)
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
const isControlExperiment = computed(() => !!protocol.value?.source_experiment_id)
const showValidationStrip = computed(
  () =>
    !isControlExperiment.value &&
    ((summary.value?.train_usable_decisions ?? 0) > 0 ||
      (validation.value?.control_experiment_ids?.length ?? 0) > 0),
)
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
  if (protocol.value?.engine_version) {
    bits.push(t('experiment.protocolEngineShort', { v: protocol.value.engine_version }))
  }
  if (protocol.value?.phases?.length) {
    bits.push(t('experiment.protocolPhasesShort', { v: protocol.value.phases.join('/') }))
  }
  return bits
})

function shortExperimentId(id: string): string {
  if (id.length <= 18) return id
  return `${id.slice(0, 8)}…${id.slice(-4)}`
}

const collectBlocked = computed(() => {
  const checks = preflight.value?.checks ?? []
  return checks.some((c) => c.severity === 'block' && !c.ok)
})

const noticeText = computed(() => {
  const checks = preflight.value?.checks ?? []
  const block = checks.find((c) => c.severity === 'block' && !c.ok)
  if (block) return block.message
  const warn = checks.find((c) => c.severity === 'warn' && !c.ok)
  return warn?.message ?? ''
})

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

const nextStepHint = computed(() => {
  if (experiment.value?.hypothesis?.trim()) return ''
  return nextStep.value ? experimentNextStepLabel(nextStep.value.id) : ''
})

const primaryActionLabel = computed(() => {
  const step = nextStep.value
  if (!step) return collectCta.value
  switch (step.action) {
    case 'collect':
      return collectCta.value
    case 'games':
      return t('experiment.openLatest')
    case 'decisions':
      return t('nav.decisions')
    case 'train':
      return t('experiment.saveAndTrain')
    case 'control':
      return t('experiment.newRound')
    case 'control_collect':
      return t('experiment.nextStep.collect_control')
    case 'compare':
      return t('experiment.compare')
    default:
      return t('experiment.nextStepAction')
  }
})

function stampSuffix(): string {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}`
}

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

const pausedGames = computed(() =>
  activeGames.value.filter((g) => g.status === 'paused'),
)

const primaryActionDisabled = computed(() => {
  const step = nextStep.value
  if (step?.action === 'games') return !summary.value?.latest_game_id
  if (!step || step.action === 'collect') {
    return remaining.value <= 0 || collectBlocked.value
  }
  if (step.action === 'train') return !canRegisterTrain.value || registeringTrain.value
  return false
})

const openMenuItems = computed((): DropdownMenuItemDef[] => [
  { id: 'archive', label: t('experiment.metaPanelTitle') },
  {
    id: 'collect',
    label: collectCta.value,
    disabled: remaining.value <= 0 || collectBlocked.value,
  },
  {
    id: 'train',
    label: t('experiment.saveAndTrain'),
    disabled: !canRegisterTrain.value || registeringTrain.value,
  },
  { id: 'traces', label: t('nav.traces') },
  { id: 'control', label: t('experiment.newRound') },
  { id: 'manifest', label: t('experiment.downloadManifest') },
  { id: 'clone', label: t('experiment.cloneExperiment') },
])

function onOpenMenuSelect(id: string): void {
  switch (id) {
    case 'archive':
      archiveOpen.value = true
      break
    case 'collect':
      openCollect()
      break
    case 'train':
      openRegisterDialog()
      break
    case 'traces':
      goTraces()
      break
    case 'control':
      openControlDialog()
      break
    case 'manifest':
      downloadManifest()
      break
    case 'clone':
      openCloneDialog()
      break
    default:
      break
  }
}

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

async function resumeAllPaused(): Promise<void> {
  const ids = pausedGames.value.map((g) => g.id)
  if (ids.length === 0) return
  resumingAll.value = true
  try {
    for (const id of ids) {
      await gameApi.resume(id)
      patchLocalGameStatus(id, 'running')
    }
    toast.success(t('experiment.resumedN', { n: ids.length }))
  } catch (e: unknown) {
    showApiError(e, t('experiment.resumeAllFailed'))
    await refreshQuiet()
  } finally {
    resumingAll.value = false
  }
}

async function load(): Promise<void> {
  if (!experimentId.value) return
  loading.value = true
  try {
    const [expRes, cfgRes, preflightRes, configRes, modelsRes] = await Promise.all([
      experimentApi.get(experimentId.value),
      experimentConfigApi.list(),
      systemApi
        .preflight({ scope: 'collect', experiment_id: experimentId.value })
        .catch(() => null),
      systemApi.getConfig().catch(() => null),
      trainingApi.listModels().catch(() => null),
    ])
    experiment.value = expRes.data
    configs.value = cfgRes.data ?? []
    preflight.value = preflightRes?.data ?? null
    trainingDepsAvailable.value = configRes?.data.training_deps_available ?? false
    completedModelCount.value = (modelsRes?.data ?? []).filter(
      (m) => m.model_path && !m.model_path.endsWith('model.bin'),
    ).length
    collectCount.value = Math.min(remaining.value, 5)
    handlePostLoadQuery()
  } catch (e: unknown) {
    showApiError(e, t('experiment.loadDetailFailed'))
    experiment.value = null
  } finally {
    loading.value = false
  }
}

function handlePostLoadQuery(): void {
  const q = route.query
  if (q.collect === '1') {
    openCollect()
  } else if (q.open_control === '1') {
    openControlDialog()
  }
  if (q.collect === '1' || q.open_control === '1') {
    void router.replace({ query: stripTabQuery(route.query as Record<string, unknown>) })
  }
}

async function refreshQuiet(): Promise<void> {
  if (!experimentId.value) return
  try {
    const res = await experimentApi.get(experimentId.value)
    experiment.value = res.data
  } catch {
    /* ignore poll errors */
  }
}

function openCollect(): void {
  if (collectBlocked.value) {
    toast.warning(noticeText.value || t('experiment.apiKeyWarning'))
    return
  }
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

function goTraining(): void {
  void router.push({
    path: '/training',
    query: { experiment_id: experimentId.value },
  })
}

function goData(): void {
  void router.push({
    path: '/data',
    query: { experiment_id: experimentId.value },
  })
}

function goControlCollect(controlId?: string): void {
  const id =
    controlId ??
    validation.value?.control_progress?.find((c) => !c.ready)?.id ??
    validation.value?.control_experiment_ids?.[0]
  if (!id) return
  void router.push({ path: `/experiments/${id}`, query: { collect: '1' } })
}

function goCompareWithSuggested(): void {
  const ids = validation.value?.suggested_compare_ids ?? [experimentId.value]
  void router.push({
    path: '/experiments/compare',
    query: { ids: ids.join(','), from: experimentId.value },
  })
}

function handleNextStep(): void {
  const step = nextStep.value
  if (!step) return
  switch (step.action) {
    case 'collect':
      openCollect()
      break
    case 'games':
      openLatest()
      break
    case 'decisions':
      goDecisions()
      break
    case 'train':
      openRegisterDialog()
      break
    case 'control':
      openControlDialog()
      break
    case 'control_collect':
      goControlCollect(step.ref_id)
      break
    case 'compare':
      goCompareWithSuggested()
      break
    default:
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

async function registerAndTrain(evalRatio = 0): Promise<void> {
  if (!experiment.value || !canRegisterTrain.value) return
  registeringTrain.value = true
  try {
    const stamp = stampSuffix()
    const base = sanitizeNamePart(experiment.value.name)
    const dsName = `${base}-chatml-${stamp}`
    const dsRes = await dataApi.createDatasetFromDecisions({
      name: dsName,
      game_type: experiment.value.game_type,
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
      game_type: experiment.value?.game_type ?? '',
      player_ids: controlPlayerIds.value,
      target_games: Number(controlTarget.value) || 5,
      source_experiment_id: experimentId.value,
      pair_deals: controlPairDeals.value,
    })
    controlOpen.value = false
    controlCreatedLocal.value = true
    toast.success(t('experiment.controlCreated'))
    const query = controlOpenCollectAfter.value ? { collect: '1' } : {}
    await router.push({ path: `/experiments/${res.data.id}`, query })
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

function redirectLegacyTab(tab: unknown): boolean {
  if (typeof tab !== 'string' || !LEGACY_TABS.has(tab) || !experimentId.value) return false
  void router.replace({ path: route.path, query: stripTabQuery(route.query as Record<string, unknown>) })
  if (tab === 'decisions') goDecisions()
  else if (tab === 'traces') goTraces()
  else goTraining()
  return true
}

watch(
  () => route.query.tab,
  (tab) => {
    if (redirectLegacyTab(tab)) return
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
        <ExperimentDetailContextBar
          :name="experiment.name"
          :status-label="statusOf(summary.status).label"
          :status-variant="statusOf(summary.status).variant"
          :benchmark="isBenchmarkExperiment(experiment)"
          :finished="summary.finished_games"
          :target="summary.target_games"
          :usable-decisions="usableCount"
          :subtitle="experiment.hypothesis ?? ''"
          :next-step="nextStep"
          :next-step-hint="nextStepHint"
          :primary-label="primaryActionLabel"
          :primary-disabled="primaryActionDisabled"
          :latest-game-id="summary.latest_game_id"
          :open-menu-items="openMenuItems"
          @back="router.push('/')"
          @primary="handleNextStep"
          @open-latest="openLatest"
          @menu-select="onOpenMenuSelect"
        />

        <PreflightBanner
          v-if="preflight?.checks?.length"
          :checks="preflight.checks"
        />
        <button
          v-else-if="noticeText"
          type="button"
          class="w-full rounded-ink border border-ink-warning/40 bg-ink-warning/10 px-3 py-2 text-left text-sm text-ink-text-secondary hover:bg-ink-warning/15"
          @click="router.push('/settings')"
        >
          {{ noticeText }}
        </button>

        <ExperimentValidationStrip
          v-if="showValidationStrip"
          :validation="validation"
          :short-experiment-id="shortExperimentId"
          @open-control="openControlDialog"
          @compare="goCompareWithSuggested"
        />

        <ExperimentResultsStrip
          v-if="finishedCount > 0"
          :summary="summary"
          @decisions="goDecisions"
          @training="goTraining"
          @data="goData"
          @compare="goCompareWithSuggested"
        />

        <div
          v-if="finishedCount > 0"
          class="flex w-fit gap-1 rounded-ink border border-ink-border bg-ink-surface-muted p-1"
        >
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
        </div>

        <ExperimentPlayersTab
          v-if="contentTab === 'players' && finishedCount > 0"
          :summary="summary"
          :config-label="configLabel"
        />

        <ExperimentGamesTab
          v-else
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
      </div>
    </template>

    <div v-else class="py-16 text-center text-ink-text-muted">{{ t('experiment.missing') }}</div>

    <UiDialog
      v-model:open="collectOpen"
      :title="t('experiment.collectTitle')"
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

    <UiDialog
      v-model:open="archiveOpen"
      size="wide"
      :title="t('experiment.metaPanelTitle')"
    >
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
        <UiButton variant="secondary" @click="archiveOpen = false">{{ t('common.close') }}</UiButton>
      </template>
    </UiDialog>
  </div>
</template>
