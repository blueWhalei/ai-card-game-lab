/** Experiment detail page state, load/poll lifecycle, and action handlers. */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  experimentApi,
  experimentStatusLabel,
  flattenProtocol,
  EXPERIMENT_STATUS_VARIANT,
  type Experiment,
  type ExperimentStatus,
} from '@/api/experimentApi'
import { experimentConfigApi, type ExperimentConfig } from '@/api/experimentConfigApi'
import { systemApi, type PreflightResult } from '@/api/systemApi'
import { trainingApi } from '@/api/trainingApi'
import { toast } from '@/components/ui/toast'
import { showApiError } from '@/utils/error'
import { preflightCheckMessage } from '@/utils/systemLabels'
import { downloadJson } from '@/utils/jsonFile'
import { shouldShowBenchmarkReport } from '@/utils/experimentBenchmark'
import {
  initialControlPlayerIds,
  sanitizeNamePart,
  uniqueFilledIds,
} from '@/utils/experimentWorkbench'
import type { ExperimentStageAction } from '@/utils/experimentStage'
import { pipelinePath } from '@/utils/pipeline'
import { useExperimentCollect } from '@/composables/useExperimentCollect'
import { useRegisterAndTrain } from '@/composables/useRegisterAndTrain'
import type { GameItem } from '@/api/gameApi'
import { gameApi } from '@/api/gameApi'
import type { DropdownMenuItemDef } from '@/components/ui/DropdownMenu.vue'

export function useExperimentDetail() {
  const { t } = useI18n()

  const PIPELINE_TABS = new Set(['decisions', 'traces', 'training'])

  const route = useRoute()
  const router = useRouter()
  const loading = ref(true)
  const registeringTrain = ref(false)
  const cancellingCollect = ref(false)
  const trainStartedLocal = ref(false)
  const controlCreatedLocal = ref(false)
  const trainingDepsAvailable = ref(false)
  const completedModelCount = ref(0)

  function stripTabQuery(query: Record<string, unknown>): Record<string, string> {
    const q: Record<string, string> = {}
    for (const [k, v] of Object.entries(query)) {
      if (typeof v === 'string' && v && k !== 'tab') q[k] = v
    }
    return q
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

  const { registerAndMaybeTrain, stampNow } = useRegisterAndTrain()

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
  const protocol = computed(() => flattenProtocol(experiment.value?.protocol ?? null))
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
    const hashes = protocol.value?.prompt_hashes
      ? Object.values(protocol.value.prompt_hashes).filter(Boolean)
      : []
    if (hashes.length > 0) {
      bits.push(t('experiment.protocolPromptHashShort', { h: hashes[0] }))
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

  /**
   * A blocking check takes over the phase's status line and action, so the user
   * is never offered a button that only produces a warning toast.
   */
  const blockedMessage = computed(() => {
    const block = (preflight.value?.checks ?? []).find((c) => c.severity === 'block' && !c.ok)
    return block ? preflightCheckMessage(block) : ''
  })

  const noticeText = computed(() => {
    const warn = (preflight.value?.checks ?? []).find((c) => c.severity === 'warn' && !c.ok)
    return warn ? preflightCheckMessage(warn) : ''
  })

  async function refreshQuiet(): Promise<void> {
    if (!experimentId.value) return
    try {
      const res = await experimentApi.get(experimentId.value)
      experiment.value = res.data
    } catch {
      /* ignore poll errors */
    }
  }

  const {
    collecting,
    collectOpen,
    collectCount,
    remaining,
    openCollect,
    openCollectDialog,
    submitCollect,
  } = useExperimentCollect({
    experiment,
    collectBlocked,
    noticeText,
    t,
    onCollected: refreshQuiet,
  })

  const hasChallenger = computed(() => configs.value.some((c) => c.id.startsWith('lora_')))

  const stageBusy = computed(() => collecting.value || registeringTrain.value)

  const canRegisterTrain = computed(
    () => (summary.value?.train_usable_decisions ?? 0) > 0 && !registeringTrain.value,
  )

  const registerPreview = computed(() => {
    const usable = summary.value?.train_usable_decisions ?? 0
    const notUsable = summary.value?.not_usable_decisions ?? 0
    const gameEstimate = Math.max(
      1,
      Math.ceil((summary.value?.finished_games ?? 1) * registerEvalRatio.value),
    )
    const evalCount = Math.max(0, Math.min(usable, gameEstimate))
    return { usable, notUsable, train: Math.max(0, usable - evalCount), eval: evalCount }
  })

  const collectCta = computed(() => {
    const status = summary.value?.status
    if (status === 'pending_collect') return t('experiment.startGames')
    if (status === 'ready_more' || status === 'ready_review') return t('experiment.runMore')
    return t('experiment.runMore')
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

  const showBenchmarkReport = computed(
    () => experiment.value != null && shouldShowBenchmarkReport(experiment.value),
  )

  const runningGames = computed(() => activeGames.value.filter((g) => g.status === 'running'))

  const pausedGames = computed(() => activeGames.value.filter((g) => g.status === 'paused'))

  const openMenuItems = computed((): DropdownMenuItemDef[] => {
    const items: DropdownMenuItemDef[] = [
      { id: 'archive', label: t('experiment.metaPanelTitle') },
      {
        id: 'collect',
        label: collectCta.value,
        disabled: remaining.value <= 0 || collectBlocked.value,
      },
    ]
    if (summary.value?.status === 'collecting') {
      items.push({
        id: 'cancel-collect',
        label: t('experiment.cancelCollect'),
        disabled: cancellingCollect.value || activeGames.value.length === 0,
      })
    }
    items.push(
      {
        id: 'train',
        label: t('experiment.saveAndTrain'),
        disabled: !canRegisterTrain.value || registeringTrain.value,
      },
      { id: 'decisions', label: t('nav.decisions') },
      { id: 'data', label: t('nav.data') },
      { id: 'training', label: t('nav.training') },
      { id: 'traces', label: t('nav.traces') },
      { id: 'puzzles', label: t('nav.puzzles') },
      { id: 'control', label: t('experiment.newRound') },
      { id: 'manifest', label: t('experiment.downloadManifest') },
      { id: 'clone', label: t('experiment.cloneExperiment') },
    )
    return items
  })

  function onOpenMenuSelect(id: string): void {
    switch (id) {
      case 'archive':
        archiveOpen.value = true
        break
      case 'collect':
        openCollectDialog()
        break
      case 'cancel-collect':
        void cancelCollect()
        break
      case 'train':
        openRegisterDialog()
        break
      case 'decisions':
        goDecisions()
        break
      case 'data':
        goData()
        break
      case 'training':
        goTraining()
        break
      case 'traces':
        goTraces()
        break
      case 'puzzles':
        goPuzzles()
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
      games: experiment.value.games.map((g) => (g.id === gameId ? { ...g, status } : g)),
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
      void submitCollect()
      void router.replace({ query: stripTabQuery(route.query as Record<string, unknown>) })
      return
    }
    if (q.open_control === '1') {
      const redirected = openControlDialog({ requireChallenger: true })
      if (!redirected) {
        void router.replace({ query: stripTabQuery(route.query as Record<string, unknown>) })
      }
    }
  }

  async function cancelCollect(): Promise<void> {
    if (!experiment.value) return
    cancellingCollect.value = true
    try {
      const res = await experimentApi.cancelCollect(experiment.value.id)
      if (res.data.count <= 0) {
        toast.info(t('experiment.cancelCollectNone'))
      } else {
        toast.success(t('experiment.cancelCollectDone', { n: res.data.count }))
      }
      await refreshQuiet()
    } catch (e: unknown) {
      showApiError(e, t('experiment.cancelCollectFailed'))
    } finally {
      cancellingCollect.value = false
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

  function goDecisions(gamePhase?: string): void {
    const query: Record<string, string> = { experiment_id: experimentId.value }
    if (gamePhase) query.game_phase = gamePhase
    void router.push({
      path: pipelinePath('decisions'),
      query,
    })
  }

  function goData(): void {
    void router.push({
      path: pipelinePath('data'),
      query: { experiment_id: experimentId.value },
    })
  }

  function goTraces(): void {
    void router.push({
      path: pipelinePath('traces'),
      query: { experiment_id: experimentId.value },
    })
  }

  function goPuzzles(): void {
    void router.push({
      path: pipelinePath('puzzles'),
      query: { experiment_id: experimentId.value },
    })
  }

  function goTraining(): void {
    void router.push({
      path: pipelinePath('training'),
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

  function goModelRepo(): void {
    void router.push({
      path: pipelinePath('training'),
      query: { experiment_id: experimentId.value, tab: 'models', return_control: '1' },
    })
  }

  function onStageAction(action: ExperimentStageAction): void {
    switch (action) {
      case 'collect':
        void submitCollect()
        break
      case 'watch':
        openLatest()
        break
      case 'review-decisions':
        goDecisions()
        break
      case 'train':
        openRegisterDialog()
        break
      case 'register-player':
        goModelRepo()
        break
      case 'open-control':
        openControlDialog({ requireChallenger: true })
        break
      case 'collect-control':
        goControlCollect(nextStep.value?.ref_id)
        break
      case 'compare':
        goCompareWithSuggested()
        break
      case 'settings':
        void router.push('/settings')
        break
      case 'cancel-collect':
        void cancelCollect()
        break
    }
  }

  function openExperiment(id: string): void {
    void router.push(`/experiments/${id}`)
  }

  async function downloadManifest(): Promise<void> {
    if (!experiment.value) return
    try {
      const res = await experimentApi.exportPack(experiment.value.id)
      downloadJson(`${experiment.value.id}-pack.json`, res.data)
      toast.success(t('experiment.exportedPack'))
    } catch (e: unknown) {
      showApiError(e, t('experiment.exportFailed'))
    }
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
    const stamp = stampNow()
    const base = sanitizeNamePart(experiment.value.name)
    await registerAndMaybeTrain(
      {
        name: `${base}-chatml-${stamp}`,
        game_type: experiment.value.game_type,
        experiment_id: experiment.value.id,
        train_usable_only: true,
        include_thinking: false,
        eval_ratio: evalRatio,
      },
      {
        startTraining: true,
        trainingDepsAvailable: trainingDepsAvailable.value,
        experimentId: experiment.value.id,
        nameBase: base,
        stamp,
        t,
        busy: registeringTrain,
        onTrainStarted: () => {
          trainStartedLocal.value = true
        },
      },
    )
  }

  function openControlDialog(opts?: { requireChallenger?: boolean }): boolean {
    if (!experiment.value) return false
    const loras = configs.value.filter((c) => c.id.startsWith('lora_'))
    if (opts?.requireChallenger && loras.length === 0) {
      toast.info(t('experiment.registerPlayerFirst'))
      void router.push({
        path: pipelinePath('training'),
        query: { experiment_id: experimentId.value, tab: 'models', return_control: '1' },
      })
      return true
    }
    const challenger = loras[0]?.id ?? ''
    controlName.value = `${sanitizeNamePart(experiment.value.name)}${t('experiment.controlNameSuffix')}`
    controlPlayerIds.value = initialControlPlayerIds(
      experiment.value.player_ids.length,
      challenger,
      experiment.value.player_ids,
    )
    controlTarget.value = experiment.value.target_games || 5
    controlPairDeals.value = true
    controlOpenCollectAfter.value = true
    controlOpen.value = true
    return false
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
      toast.success(
        controlOpenCollectAfter.value
          ? t('experiment.controlCreatedCollect')
          : t('experiment.controlCreated'),
      )
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

  function openPipelineTab(tab: unknown): boolean {
    if (typeof tab !== 'string' || !PIPELINE_TABS.has(tab) || !experimentId.value) return false
    void router.replace({
      path: route.path,
      query: stripTabQuery(route.query as Record<string, unknown>),
    })
    if (tab === 'decisions') goDecisions()
    else if (tab === 'traces') goTraces()
    else goTraining()
    return true
  }

  watch(
    () => route.query.tab,
    (tab) => {
      openPipelineTab(tab)
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

  return {
    // route / i18n
    router,
    t,
    // load state
    loading,
    experiment,
    summary,
    validation,
    experimentId,
    load,
    // stage
    blockedMessage,
    noticeText,
    hasChallenger,
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
    // header / menu
    openMenuItems,
    onOpenMenuSelect,
    statusOf,
    // benchmark / protocol
    showBenchmarkReport,
    configLabel,
    protocol,
    protocolPlayers,
    protocolDrift,
    protocolSummaryBits,
    dealSeedCount,
    shortExperimentId,
    // games
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
    // control dialog
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
    // clone
    cloneOpen,
    cloneName,
    cloning,
    submitClone,
    // register
    registerOpen,
    registerEvalRatio,
    registerPreview,
    registeringTrain,
    submitRegister,
    // archive
    archiveOpen,
    onNotebookSaved,
    downloadManifest,
    openCloneDialog,
  }
}
