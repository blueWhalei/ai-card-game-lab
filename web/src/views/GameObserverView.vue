<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { toast } from '@/components/ui/toast'
import { showApiError } from '@/utils/error'
import { gameApi } from '@/api/gameApi'
import { experimentConfigApi } from '@/api/experimentConfigApi'
import type { GameItem, ReplayData } from '@/api/gameApi'
import { useGameWebSocket } from '@/composables/useGameWebSocket'
import type { HistoryEntry } from '@/composables/useGameWebSocket'
import { coerceObserverSnapshot } from '@/types/observer'
import { displayCard, isRedCard } from '@/utils/card'
import GameHeaderBar from '@/components/game/GameHeaderBar.vue'
import GenericBoard from '@/components/game/GenericBoard.vue'
import GameReplayControls from '@/components/game/GameReplayControls.vue'
import GameResultDialog from '@/components/game/GameResultDialog.vue'
import ThinkingPanel from '@/components/game/ThinkingPanel.vue'
import UiSpinner from '@/components/ui/Spinner.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const gameId = computed(() => route.params.id as string)

const game = ref<GameItem | null>(null)
const loading = ref(true)
const replayLoading = ref(false)
const showResultDialog = ref(false)
const rightPanelTab = ref<'history' | 'thinking'>('thinking')
const rightPanelCollapsed = ref(false)
const thinkingExpandedSet = ref(new Set<number>())

const isReplayMode = ref(false)
const replayData = ref<ReplayData | null>(null)
const replayIndex = ref(0)
const replayPlaying = ref(false)
const replaySpeed = ref(1000)
let replayTimer: ReturnType<typeof setInterval> | null = null

const {
  isConnected,
  connect: connectWs,
  disconnect: disconnectWs,
  snapshot,
  applySnapshot,
  playerHands,
  currentPlayer,
  lastAction,
  thinkingPlayer,
  thinkingContent,
  currentThinkingRound,
  currentThinkingActionType,
  currentThinkingCards,
  currentPromptPreview,
  currentRawResponsePreview,
  currentPromptMessages,
  currentRawResponseFull,
  reasoningContent,
  answerContent,
  playerTokenTotals,
  playerLastRoundTokens,
  actionHistory,
  thinkingHistory,
  isPaused,
  isStarted,
  isFinished,
  lastError,
  winner,
  historyPanel,
} = useGameWebSocket(gameId)

const configNameMap = ref<Record<string, string>>({})

const playerNames = computed<Record<string, string>>(() => {
  const names: Record<string, string> = {}
  for (const id of game.value?.player_ids || []) {
    names[id] = configNameMap.value[id] || id
  }
  return names
})

async function fetchConfigNames(ids: string[]) {
  if (ids.length === 0) return
  try {
    const res = await experimentConfigApi.list()
    const map: Record<string, string> = {}
    for (const config of res.data) {
      if (ids.includes(config.id)) {
        map[config.id] = config.name
      }
    }
    configNameMap.value = map
  } catch {
    // Non-blocking: fall back to config id
  }
}

const totalTokens = computed(() =>
  Object.values(playerTokenTotals.value).reduce((sum, value) => sum + value, 0),
)

const latestModelName = computed(() => {
  const latest = [...thinkingHistory.value].reverse().find((entry) => entry.modelName)
  return latest?.modelName || undefined
})

watch(winner, (newWinner) => {
  if (newWinner) showResultDialog.value = true
})

watch(lastError, (msg) => {
  if (msg) toast.error(msg)
})

async function fetchGame() {
  loading.value = true
  try {
    const res = await gameApi.get(gameId.value)
    game.value = res.data
    await fetchConfigNames(res.data.player_ids)
    isStarted.value = ['running', 'paused', 'finished'].includes(res.data.status)
    isPaused.value = res.data.status === 'paused'
    isFinished.value = res.data.status === 'finished'
  } catch (e: unknown) {
    showApiError(e, t('game.loadGameFailed'))
  } finally {
    loading.value = false
  }
}

async function handleStart() {
  try {
    await gameApi.start(gameId.value)
    toast.success(t('game.started'))
  } catch (e: unknown) {
    showApiError(e, t('game.startFailed'))
  }
}

async function handlePause() {
  try {
    await gameApi.pause(gameId.value)
  } catch (e: unknown) {
    showApiError(e, t('experiment.pauseFailed'))
  }
}

async function handleResume() {
  try {
    await gameApi.resume(gameId.value)
  } catch (e: unknown) {
    showApiError(e, t('game.restoreFailed'))
  }
}

function goBack() {
  const experimentId = game.value?.experiment_id
  if (experimentId) {
    void router.push(`/experiments/${experimentId}`)
    return
  }
  void router.push('/game')
}

async function loadReplay() {
  replayLoading.value = true
  try {
    const res = await gameApi.replay(gameId.value)
    replayData.value = res.data
    isReplayMode.value = true
    replayIndex.value = 0
    actionHistory.value = []
    thinkingHistory.value = []
    Object.keys(playerTokenTotals.value).forEach((key) => delete playerTokenTotals.value[key])
    Object.keys(playerLastRoundTokens.value).forEach((key) => delete playerLastRoundTokens.value[key])
    replayStepTo(0)
  } catch (e: unknown) {
    showApiError(e, t('game.replayFailed'))
  } finally {
    replayLoading.value = false
  }
}

function replayStepTo(index: number) {
  if (!replayData.value) return
  const rounds = replayData.value.rounds
  actionHistory.value = []
  thinkingHistory.value = []
  Object.keys(playerTokenTotals.value).forEach((key) => delete playerTokenTotals.value[key])
  Object.keys(playerLastRoundTokens.value).forEach((key) => delete playerLastRoundTokens.value[key])
  Object.keys(playerHands.value).forEach((key) => delete playerHands.value[key])
  lastAction.value = null

  const ids = game.value?.player_ids || []
  const roles: Record<string, string> = {}
  const hands: Record<string, string[]> = {}

  for (let i = 0; i <= index && i < rounds.length; i++) {
    const r = rounds[i]
    if (!r) continue
    const thinking = r.thinking || replayData.value.thinking[r.round_num] || ''
    const entry: HistoryEntry = {
      round: r.round_num,
      playerId: r.player_id,
      actionType: r.action_type,
      cards: r.cards || [],
      thinking,
      responseTimeMs: r.response_time_ms ?? undefined,
    }
    actionHistory.value.push(entry)
    if (thinking) {
      thinkingHistory.value.push({
        playerId: r.player_id,
        round: r.round_num,
        thinking,
        responseTimeMs: r.response_time_ms ?? 0,
        promptTokens: r.prompt_tokens,
        completionTokens: r.completion_tokens,
        totalTokens: r.total_tokens,
        modelProvider: r.model_provider ?? undefined,
        modelName: r.model_name ?? undefined,
        actionType: r.action_type,
        cards: r.cards || [],
        promptPreview:
          r.prompt?.map((message) => `[${message.role}]\n${message.content}`).join('\n\n') || '',
        rawResponsePreview: r.raw_response || '',
      })
      if (typeof r.total_tokens === 'number') {
        playerLastRoundTokens.value[r.player_id] = r.total_tokens
        playerTokenTotals.value[r.player_id] =
          (playerTokenTotals.value[r.player_id] || 0) + r.total_tokens
      }
    }
    if (r.all_hands && Object.keys(r.all_hands).length > 0) {
      for (const [pid, hand] of Object.entries(r.all_hands)) {
        hands[pid] = hand as string[]
        playerHands.value[pid] = hand as string[]
      }
    } else if (r.hand_snapshot) {
      hands[r.player_id] = r.hand_snapshot
      playerHands.value[r.player_id] = r.hand_snapshot
    }
    lastAction.value = {
      playerId: r.player_id,
      actionType: r.action_type,
      cards: r.cards || [],
    }
    currentPlayer.value = r.player_id
  }

  const playerList = (ids.length ? ids : Object.keys(hands)).map((id) => ({
    id,
    role: roles[id] || 'unknown',
    is_active: currentPlayer.value === id,
    hand_count: hands[id]?.length ?? 0,
    hand_cards: hands[id],
    badges: roles[id] ? [roles[id]] : [],
    last_action:
      lastAction.value?.playerId === id
        ? {
            type: lastAction.value.actionType,
            cards: lastAction.value.cards,
            label: lastAction.value.actionType === 'PASS' ? t('action.PASS') : undefined,
          }
        : undefined,
  }))

  applySnapshot(
    coerceObserverSnapshot(
      {
        game_type: game.value?.game_type ?? '',
        phase: 'playing',
        round: rounds[index]?.round_num ?? 0,
        current_player_id: currentPlayer.value,
        players: playerList,
        table: { slots: [] },
      },
      game.value?.game_type ?? '',
    ),
  )
  replayIndex.value = index
}

function replayNext() {
  if (!replayData.value) return
  if (replayIndex.value < replayData.value.rounds.length - 1) {
    replayStepTo(replayIndex.value + 1)
  } else {
    replayPause()
  }
}

function replayPrev() {
  if (replayIndex.value > 0) {
    replayStepTo(replayIndex.value - 1)
  }
}

function replayPlay() {
  replayPlaying.value = true
  replayTimer = setInterval(() => {
    replayNext()
    if (replayData.value && replayIndex.value >= replayData.value.rounds.length - 1) {
      replayPause()
    }
  }, replaySpeed.value)
}

function replayPause() {
  replayPlaying.value = false
  if (replayTimer) {
    clearInterval(replayTimer)
    replayTimer = null
  }
}

onMounted(async () => {
  await fetchGame()
  if (game.value?.status === 'created') {
    await handleStart()
    await fetchGame()
  }
  if (isFinished.value) {
    await loadReplay()
  } else {
    connectWs()
  }
})

watch(gameId, async (next, prev) => {
  if (!next || next === prev) return
  replayPause()
  isReplayMode.value = false
  replayData.value = null
  replayIndex.value = 0
  await fetchGame()
  if (isFinished.value) {
    disconnectWs()
    await loadReplay()
  }
})

onUnmounted(() => {
  disconnectWs()
  replayPause()
})
</script>

<template>
  <div class="relative flex h-screen flex-col overflow-hidden bg-ink-obs-bg text-ink-obs-text">
    <div v-if="loading" class="absolute inset-0 z-20">
      <UiSpinner overlay :label="t('game.loadingGame')" />
    </div>

    <GameHeaderBar
      :game="game"
      :is-connected="isConnected"
      :is-started="isStarted"
      :is-paused="isPaused"
      :is-finished="isFinished"
      :is-replay-mode="isReplayMode"
      :total-tokens="totalTokens"
      :latest-model-name="latestModelName"
      @back="goBack"
      @start="handleStart"
      @pause="handlePause"
      @resume="handleResume"
    >
      <template #replay-controls>
        <GameReplayControls
          v-if="isReplayMode"
          :replay-data="replayData"
          :replay-index="replayIndex"
          :replay-playing="replayPlaying"
          :replay-speed="replaySpeed"
          @prev="replayPrev"
          @play="replayPlay"
          @pause="replayPause"
          @next="replayNext"
          @update:replay-speed="replaySpeed = $event"
        />
      </template>
    </GameHeaderBar>

    <div class="flex min-h-0 flex-1 flex-col lg:flex-row">
      <div class="relative min-h-0 min-w-0 flex-1">
        <GenericBoard
          :snapshot="snapshot"
          :thinking-player-id="thinkingPlayer"
          :player-names="playerNames"
          :loading="replayLoading"
          :empty-hint="t('game.waitPush')"
        />
      </div>

      <Transition name="slide">
        <div
          v-if="!rightPanelCollapsed"
          class="flex max-h-[42vh] w-full shrink-0 flex-col border-t border-ink-obs-border bg-ink-obs-surface lg:max-h-none lg:w-96 lg:border-t-0 lg:border-l"
        >
          <div class="flex shrink-0 items-center justify-between border-b border-ink-obs-border px-4 py-3">
            <div class="inline-flex flex-1 rounded-ink bg-ink-obs-bg p-0.5">
              <button
                type="button"
                class="flex-1 rounded-[6px] px-3 py-1.5 text-sm"
                :class="
                  rightPanelTab === 'history'
                    ? 'bg-ink-obs-surface text-ink-obs-text shadow-[var(--ink-shadow)]'
                    : 'text-ink-obs-muted'
                "
                @click="rightPanelTab = 'history'"
              >
                {{ t('game.actionLog') }}
              </button>
              <button
                type="button"
                class="flex-1 rounded-[6px] px-3 py-1.5 text-sm"
                :class="
                  rightPanelTab === 'thinking'
                    ? 'bg-ink-obs-surface text-ink-obs-text shadow-[var(--ink-shadow)]'
                    : 'text-ink-obs-muted'
                "
                @click="rightPanelTab = 'thinking'"
              >
                {{ t('game.aiThinking') }}
              </button>
            </div>
            <button
              type="button"
              class="ml-2 rounded-ink p-1.5 text-ink-obs-muted hover:bg-ink-obs-bg"
              :title="t('game.collapsePanel')"
              :aria-label="t('game.collapseSidebar')"
              @click="rightPanelCollapsed = true"
            >
              ›
            </button>
          </div>

          <div
            v-show="rightPanelTab === 'history'"
            ref="historyPanel"
            class="flex-1 overflow-y-auto p-4"
          >
            <div v-if="actionHistory.length === 0" class="py-12 text-center text-sm text-ink-obs-muted">
              {{ t('game.noRecords') }}
            </div>
            <div
              v-for="(entry, i) in actionHistory"
              :key="i"
              class="mb-2 rounded-ink bg-ink-obs-bg px-3 py-2.5"
            >
              <div class="mb-1 flex items-center gap-2 text-xs text-ink-obs-muted">
                <span class="font-mono">R{{ entry.round }}</span>
                <span class="font-medium text-ink-obs-text">{{ entry.playerId }}</span>
                <span v-if="entry.responseTimeMs" class="rounded px-2 py-0.5 text-ink-obs-muted">
                  {{
                    entry.responseTimeMs >= 1000
                      ? `${(entry.responseTimeMs / 1000).toFixed(1)}s`
                      : `${entry.responseTimeMs}ms`
                  }}
                </span>
              </div>
              <div v-if="entry.actionType === 'PASS'" class="text-sm text-ink-obs-muted">{{
                t('action.PASS')
              }}</div>
              <div v-else class="flex flex-wrap gap-1">
                <span
                  v-for="(card, j) in entry.cards"
                  :key="j"
                  class="inline-block text-sm font-bold"
                  :class="isRedCard(card) ? 'text-red-400' : 'text-ink-obs-text'"
                >
                  {{ displayCard(card) }}
                </span>
                <span v-if="entry.cards.length === 0" class="text-xs text-ink-obs-muted">
                  {{ entry.actionType }}
                </span>
              </div>
            </div>
          </div>

          <div v-show="rightPanelTab === 'thinking'" class="min-h-0 flex-1 overflow-hidden">
            <ThinkingPanel
              :current-player-id="thinkingPlayer"
              :current-thinking="thinkingContent"
              :current-round="currentThinkingRound"
              :current-action-type="currentThinkingActionType"
              :current-cards="currentThinkingCards"
              :current-prompt-preview="currentPromptPreview"
              :current-raw-response-preview="currentRawResponsePreview"
              :current-prompt-messages="currentPromptMessages"
              :current-raw-response-full="currentRawResponseFull"
              :current-reasoning="reasoningContent"
              :current-answer="answerContent"
              :history="thinkingHistory"
              v-model:expanded-set="thinkingExpandedSet"
            />
          </div>
        </div>
      </Transition>

      <div
        v-if="rightPanelCollapsed"
        class="flex shrink-0 items-center justify-center border-t border-ink-obs-border bg-ink-obs-surface px-2 py-2 lg:border-t-0 lg:border-l lg:py-0"
      >
        <button
          type="button"
          class="rounded-ink p-1.5 text-ink-obs-muted hover:bg-ink-obs-bg"
          :title="t('game.expandPanel')"
          :aria-label="t('game.expandSidebar')"
          @click="rightPanelCollapsed = false"
        >
          ‹
        </button>
      </div>
    </div>

    <GameResultDialog
      v-model="showResultDialog"
      :game-id="gameId"
      :winner="winner"
      @back="goBack"
    />
  </div>
</template>

<style scoped>
.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s ease;
}

.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
  opacity: 0;
}
</style>
