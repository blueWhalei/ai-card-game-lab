<script setup lang="ts">
import CardDisplay from '@/components/game/CardDisplay.vue'
import PlayerCard from '@/components/game/PlayerCard.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'

defineProps<{
  replayLoading: boolean
  isConnected: boolean
  isStarted: boolean
  isFinished: boolean
  loading: boolean
  landlordCards: string[]
  actionHistoryLength: number
  playerPositions: Array<{ id: string; position: string }>
  playerHands: Record<string, string[]>
  players: Record<string, { cardsLeft: number; role: string } | undefined>
  currentPlayer: string | null
  thinkingPlayer: string | null
  lastResponseTimeMs: Record<string, number>
  playerLastRoundTokens: Record<string, number>
  playerTokenTotals: Record<string, number>
  latestModelName: string | undefined
  leftLastAction: { actionType: string; cards: string[] } | undefined
  rightLastAction: { actionType: string; cards: string[] } | undefined
  bottomLastAction: { actionType: string; cards: string[] } | undefined
  isAnimatingAction: boolean
  lastAction: { playerId: string; actionType: string; cards: string[] } | null
}>()
</script>

<template>
  <div class="flex-1 p-3">
    <div class="game-table relative mx-auto flex h-full flex-col" style="max-width: 1200px; min-height: 520px;">
      <!-- Replay loading overlay -->
      <div v-if="replayLoading" class="absolute inset-0 z-50 flex items-center justify-center rounded-3xl bg-black/30 backdrop-blur-sm">
        <LoadingSpinner text="加载回放数据..." />
      </div>
      <!-- Reconnecting banner -->
      <div v-if="!isConnected && isStarted && !isFinished" class="mx-4 mt-4 rounded-lg bg-red-500/20 px-4 py-2 text-center text-sm text-red-200">
        连接断开，正在尝试重新连接...
      </div>
      <!-- Top bar: 底牌 + 轮次 -->
      <div class="flex shrink-0 items-center justify-center gap-4 pt-4 pb-2">
        <div v-if="landlordCards.length > 0" class="flex items-center gap-2">
          <span class="text-xs font-medium text-amber-200/80">底牌</span>
          <CardDisplay :cards="landlordCards" compact size="mini" :show-count="false" />
        </div>
        <span v-if="actionHistoryLength > 0" class="rounded-full bg-white/10 px-3 py-1 text-xs text-white/60">
          第 {{ actionHistoryLength }} 轮
        </span>
      </div>

      <!-- Main table body: 3 player zones -->
      <div class="relative flex-1">

        <!-- LEFT player (top-left) -->
        <div v-if="playerPositions[0]" class="absolute left-6 top-6 flex flex-col items-center gap-2">
          <PlayerCard
            :player-id="playerPositions[0].id" :info="players[playerPositions[0].id]"
            :hand-cards="playerHands[playerPositions[0].id]"
            :is-current="currentPlayer === playerPositions[0].id"
            :is-thinking="thinkingPlayer === playerPositions[0].id"
            :response-time-ms="lastResponseTimeMs[playerPositions[0].id]"
            :round-tokens="playerLastRoundTokens[playerPositions[0].id]"
            :total-tokens="playerTokenTotals[playerPositions[0].id]"
            :model-name="latestModelName"
          />
        </div>

        <!-- CENTER: action zones (triangle layout) -->
        <div class="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div class="flex flex-col items-center gap-3">
            <!-- Top row: left + right action cards side by side -->
            <div class="flex items-start gap-16">
              <!-- Left player action -->
              <Transition name="card-action" mode="out-in">
                <div v-if="leftLastAction" :key="leftLastAction.actionType + (leftLastAction.cards ?? []).join(',')" class="flex flex-col items-center gap-1">
                  <span class="text-xs text-white/50">{{ playerPositions[0]?.id }}</span>
                  <template v-if="leftLastAction.actionType === 'PASS'">
                    <span class="rounded-lg bg-white/20 px-3 py-1 text-xs text-white/70">不出</span>
                  </template>
                  <template v-else-if="leftLastAction.cards.length > 0">
                    <CardDisplay :cards="leftLastAction.cards" compact size="table" :show-count="false" :playing="isAnimatingAction && lastAction?.playerId === playerPositions[0]?.id" />
                  </template>
                </div>
              </Transition>

              <!-- Right player action -->
              <Transition name="card-action" mode="out-in">
                <div v-if="rightLastAction" :key="rightLastAction.actionType + (rightLastAction.cards ?? []).join(',')" class="flex flex-col items-center gap-1">
                  <span class="text-xs text-white/50">{{ playerPositions[2]?.id }}</span>
                  <template v-if="rightLastAction.actionType === 'PASS'">
                    <span class="rounded-lg bg-white/20 px-3 py-1 text-xs text-white/70">不出</span>
                  </template>
                  <template v-else-if="rightLastAction.cards.length > 0">
                    <CardDisplay :cards="rightLastAction.cards" compact size="table" :show-count="false" :playing="isAnimatingAction && lastAction?.playerId === playerPositions[2]?.id" />
                  </template>
                </div>
              </Transition>
            </div>

            <!-- Waiting state (no actions yet) -->
            <div v-if="!isStarted && !loading" class="flex flex-col items-center gap-3">
              <div class="text-4xl opacity-40">🃏</div>
              <div class="text-base text-white/60">等待启动...</div>
              <div class="flex gap-3">
                <div v-for="i in 3" :key="i" class="h-10 w-10 animate-pulse rounded-full bg-white/10" />
              </div>
              <p class="text-xs text-white/40">3 位 AI 玩家准备就绪</p>
            </div>
            <div v-else-if="currentPlayer && !leftLastAction && !rightLastAction && !bottomLastAction" class="text-sm text-white/40">
              <span class="text-white/70 font-medium">{{ currentPlayer }}</span> 的回合
            </div>

            <!-- Bottom player action (below center) -->
            <Transition name="card-action" mode="out-in">
              <div v-if="bottomLastAction" :key="bottomLastAction.actionType + (bottomLastAction.cards ?? []).join(',')" class="flex flex-col items-center gap-1">
                <span class="text-xs text-white/50">{{ playerPositions[1]?.id }}</span>
                <template v-if="bottomLastAction.actionType === 'PASS'">
                  <span class="rounded-lg bg-white/20 px-4 py-1.5 text-sm text-white/70">不出</span>
                </template>
                <template v-else-if="bottomLastAction.cards.length > 0">
                  <CardDisplay :cards="bottomLastAction.cards" compact size="table" :show-count="false" :playing="isAnimatingAction && lastAction?.playerId === playerPositions[1]?.id" />
                </template>
              </div>
            </Transition>
          </div>
        </div>

        <!-- RIGHT player (top-right) -->
        <div v-if="playerPositions[2]" class="absolute right-6 top-6 flex flex-col items-center gap-2">
          <PlayerCard
            :player-id="playerPositions[2].id" :info="players[playerPositions[2].id]"
            :hand-cards="playerHands[playerPositions[2].id]"
            :is-current="currentPlayer === playerPositions[2].id"
            :is-thinking="thinkingPlayer === playerPositions[2].id"
            :response-time-ms="lastResponseTimeMs[playerPositions[2].id]"
            :round-tokens="playerLastRoundTokens[playerPositions[2].id]"
            :total-tokens="playerTokenTotals[playerPositions[2].id]"
            :model-name="latestModelName"
          />
        </div>

        <!-- BOTTOM player -->
        <div v-if="playerPositions[1]" class="absolute bottom-6 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2">
          <PlayerCard
            :player-id="playerPositions[1].id" :info="players[playerPositions[1].id]"
            :hand-cards="playerHands[playerPositions[1].id]"
            :is-current="currentPlayer === playerPositions[1].id"
            :is-thinking="thinkingPlayer === playerPositions[1].id"
            :response-time-ms="lastResponseTimeMs[playerPositions[1].id]"
            :round-tokens="playerLastRoundTokens[playerPositions[1].id]"
            :total-tokens="playerTokenTotals[playerPositions[1].id]"
            :model-name="latestModelName"
          />
        </div>

      </div>
    </div>
  </div>
</template>

<style scoped>
/* 欢乐斗地主风格牌桌 */
.game-table {
  background: linear-gradient(135deg, #1a472a 0%, #2d5a3f 50%, #1a472a 100%);
  border-radius: 24px;
  box-shadow:
    inset 0 2px 4px rgba(255, 255, 255, 0.1),
    0 8px 32px rgba(0, 0, 0, 0.3),
    0 2px 8px rgba(0, 0, 0, 0.2);
  border: 3px solid #8b6914;
  position: relative;
  overflow: hidden;
}

.game-table::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse at center, rgba(255, 215, 0, 0.05) 0%, transparent 70%);
  pointer-events: none;
}

/* Card action transition */
.card-action-enter-active {
  transition: all 0.3s ease-out;
}
.card-action-leave-active {
  transition: all 0.15s ease-in;
}
.card-action-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.card-action-leave-to {
  opacity: 0;
  transform: scale(0.9);
}
</style>
