<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { showApiError } from '@/utils/error'
import { gameApi } from '@/api/gameApi'
import type { GameItem, ReplayData } from '@/api/gameApi'
import { useGameWebSocket } from '@/composables/useGameWebSocket'
import type { HistoryEntry } from '@/composables/useGameWebSocket'
import { displayCard, isRedCard } from '@/utils/card'
import GameHeaderBar from '@/components/game/GameHeaderBar.vue'
import GameTable from '@/components/game/GameTable.vue'
import GameReplayControls from '@/components/game/GameReplayControls.vue'
import GameResultDialog from '@/components/game/GameResultDialog.vue'
import ThinkingPanel from '@/components/game/ThinkingPanel.vue'

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
const isAnimatingAction = ref(false)
let animTimer: ReturnType<typeof setTimeout> | null = null

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
  playerHands,
  players,
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
  lastResponseTimeMs,
  playerTokenTotals,
  playerLastRoundTokens,
  actionHistory,
  thinkingHistory,
  landlordCards,
  playerLastActions,
  isPaused,
  isStarted,
  isFinished,
  lastError,
  winner,
  historyPanel,
} = useGameWebSocket(gameId.value)

watch(winner, (newWinner) => {
  if (newWinner) {
    showResultDialog.value = true
  }
})

watch(lastError, (msg) => {
  if (msg) {
    ElMessage.error(msg)
  }
})

watch(lastAction, (newVal, oldVal) => {
  if (newVal && newVal.playerId !== oldVal?.playerId) {
    if (animTimer) clearTimeout(animTimer)
    isAnimatingAction.value = true
    animTimer = setTimeout(() => { isAnimatingAction.value = false }, 400)
  }
})

function getLastAction(playerId: string): { actionType: string; cards: string[] } | undefined {
  return playerLastActions.value[playerId]
}

const playerPositions = computed(() => {
  const ids = game.value?.player_ids || []
  return [
    { id: ids[0] || '', position: 'left' },
    { id: ids[1] || '', position: 'bottom' },
    { id: ids[2] || '', position: 'right' },
  ]
})

const leftLastAction = computed(() => playerPositions.value[0]?.id ? getLastAction(playerPositions.value[0].id) : undefined)
const rightLastAction = computed(() => playerPositions.value[2]?.id ? getLastAction(playerPositions.value[2].id) : undefined)
const bottomLastAction = computed(() => playerPositions.value[1]?.id ? getLastAction(playerPositions.value[1].id) : undefined)

const totalTokens = computed(() =>
  Object.values(playerTokenTotals.value).reduce((sum, value) => sum + value, 0),
)

const latestModelName = computed(() => {
  const latest = [...thinkingHistory.value].reverse().find((entry) => entry.modelName)
  return latest?.modelName || undefined
})

async function fetchGame() {
  loading.value = true
  try {
    const res = await gameApi.get(gameId.value)
    game.value = res.data
    isStarted.value = ['running', 'paused', 'finished'].includes(res.data.status)
    isPaused.value = res.data.status === 'paused'
    isFinished.value = res.data.status === 'finished'
  } catch (e: unknown) {
    showApiError(e, '加载对局失败')
  } finally {
    loading.value = false
  }
}

async function handleStart() {
  try {
    await gameApi.start(gameId.value)
    ElMessage.success('对局已启动')
  } catch (e: unknown) {
    showApiError(e, '启动失败')
  }
}

async function handlePause() {
  try {
    await gameApi.pause(gameId.value)
  } catch (e: unknown) {
    showApiError(e, '暂停失败')
  }
}

async function handleResume() {
  try {
    await gameApi.resume(gameId.value)
  } catch (e: unknown) {
    showApiError(e, '恢复失败')
  }
}

function goBack() {
  router.push('/game')
}

// ── Replay functions ──────────────────────────────
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
  } catch (e: unknown) {
    showApiError(e, '加载回放数据失败')
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
        promptPreview: r.prompt?.map((message) => `[${message.role}]\n${message.content}`).join('\n\n') || '',
        rawResponsePreview: r.raw_response || '',
      })
      if (typeof r.total_tokens === 'number') {
        playerLastRoundTokens.value[r.player_id] = r.total_tokens
        playerTokenTotals.value[r.player_id] = (playerTokenTotals.value[r.player_id] || 0) + r.total_tokens
      }
    }
    if (r.all_hands && Object.keys(r.all_hands).length > 0) {
      for (const [pid, hand] of Object.entries(r.all_hands)) {
        playerHands.value[pid] = hand as string[]
      }
    } else if (r.hand_snapshot) {
      playerHands.value[r.player_id] = r.hand_snapshot
    }
    lastAction.value = {
      playerId: r.player_id,
      actionType: r.action_type,
      cards: r.cards || [],
    }
    currentPlayer.value = r.player_id
  }
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
  if (isFinished.value) {
    await loadReplay()
  } else {
    connectWs()
  }
})

onUnmounted(() => {
  disconnectWs()
  replayPause()
})
</script>

<template>
  <div v-loading="loading" class="flex h-[calc(100vh-48px)] flex-col overflow-hidden bg-[#f5f5f7]">
    <!-- Header bar -->
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

    <!-- Main area -->
    <div class="flex min-h-0 flex-1">
      <!-- Game Table -->
      <GameTable
        :replay-loading="replayLoading"
        :is-connected="isConnected"
        :is-started="isStarted"
        :is-finished="isFinished"
        :loading="loading"
        :landlord-cards="landlordCards"
        :action-history-length="actionHistory.length"
        :player-positions="playerPositions"
        :player-hands="playerHands"
        :players="players"
        :current-player="currentPlayer"
        :thinking-player="thinkingPlayer"
        :last-response-time-ms="lastResponseTimeMs"
        :player-last-round-tokens="playerLastRoundTokens"
        :player-token-totals="playerTokenTotals"
        :latest-model-name="latestModelName"
        :left-last-action="leftLastAction"
        :right-last-action="rightLastAction"
        :bottom-last-action="bottomLastAction"
        :is-animating-action="isAnimatingAction"
        :last-action="lastAction"
      />

      <!-- Right Panel - collapsible -->
      <Transition name="slide">
        <div v-if="!rightPanelCollapsed" class="flex w-96 shrink-0 flex-col border-l border-black/[0.06] bg-white">
          <div class="flex shrink-0 items-center justify-between border-b border-black/[0.06] px-4 py-3">
            <div class="apple-segmented flex-1">
              <button :class="rightPanelTab === 'history' ? 'apple-segmented-item-active' : 'apple-segmented-item'" style="flex:1" @click="rightPanelTab = 'history'">出牌记录</button>
              <button :class="rightPanelTab === 'thinking' ? 'apple-segmented-item-active' : 'apple-segmented-item'" style="flex:1" @click="rightPanelTab = 'thinking'">AI 思考</button>
            </div>
            <button class="ml-2 rounded-lg p-1.5 text-[#86868b] hover:bg-[#f5f5f7]" title="收起面板" @click="rightPanelCollapsed = true">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" /></svg>
            </button>
          </div>

          <div v-show="rightPanelTab === 'history'" ref="historyPanel" class="flex-1 overflow-y-auto p-4">
            <div v-if="actionHistory.length === 0" class="py-12 text-center text-sm text-[#86868b]">暂无记录</div>
            <div v-for="(entry, i) in actionHistory" :key="i" class="mb-2 rounded-xl bg-[#f5f5f7] px-3 py-2.5">
              <div class="mb-1 flex items-center gap-2 text-xs text-[#86868b]">
                <span class="font-mono">R{{ entry.round }}</span>
                <span class="font-medium text-[#1d1d1f]">{{ entry.playerId }}</span>
                <span v-if="entry.responseTimeMs" class="rounded-full bg-white px-2 py-0.5 text-[#aeaeb2]">
                  {{ entry.responseTimeMs >= 1000 ? `${(entry.responseTimeMs/1000).toFixed(1)}s` : `${entry.responseTimeMs}ms` }}
                </span>
              </div>
              <div v-if="entry.actionType === 'PASS'" class="text-sm text-[#aeaeb2]">不出</div>
              <div v-else class="flex flex-wrap gap-1">
                <span
                  v-for="(card, j) in entry.cards" :key="j"
                  class="inline-block text-sm font-bold"
                  :class="isRedCard(card) ? 'text-[#ff3b30]' : 'text-[#1d1d1f]'"
                >{{ displayCard(card) }}</span>
                <span v-if="entry.cards.length === 0" class="text-xs text-[#86868b]">{{ entry.actionType }}</span>
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

      <!-- Collapsed panel - expand button -->
      <div v-if="rightPanelCollapsed" class="flex shrink-0 items-center border-l border-black/[0.06] bg-white px-2">
        <button class="rounded-lg p-1.5 text-[#86868b] hover:bg-[#f5f5f7]" title="展开面板" @click="rightPanelCollapsed = false">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" /></svg>
        </button>
      </div>
    </div>

    <!-- Result Dialog -->
    <GameResultDialog
      v-model="showResultDialog"
      :winner="winner"
      @back="goBack"
    />
  </div>
</template>

<style scoped>
/* Slide transition for right panel */
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
