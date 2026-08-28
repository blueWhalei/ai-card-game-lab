<script setup lang="ts">
import { formatMs } from '@/utils/card'
import CardDisplay from '@/components/game/CardDisplay.vue'

const props = defineProps<{
  playerId: string
  name?: string
  info?: { cardsLeft: number; role: string }
  handCards?: string[]
  isCurrent: boolean
  isThinking: boolean
  responseTimeMs?: number
  roundTokens?: number
  totalTokens?: number
  modelName?: string
  lastAction?: 'play' | 'pass' | 'grab'
  mini?: boolean
}>()

</script>

<template>
  <div
    v-if="playerId"
    class="player-card text-center transition-all relative"
    :class="[
      mini
        ? 'min-w-[100px] rounded-lg px-2.5 py-2'
        : 'min-w-[150px] rounded-xl px-4 py-3',
      isCurrent
        ? 'bg-yellow-400/90 shadow-lg ring-2 ring-yellow-300 scale-105'
        : 'bg-white/90 shadow',
      info?.role === 'landlord' ? 'landlord-card' : ''
    ]"
  >
    <!-- Landlord Crown -->
    <div
      v-if="info?.role === 'landlord'"
      class="absolute -top-3 left-1/2 -translate-x-1/2 crown-shadow"
      :class="mini ? 'text-xl' : 'text-2xl'"
    >
      👑
    </div>

    <div :class="mini ? 'text-xs font-semibold text-gray-800 truncate' : 'text-sm font-semibold text-gray-800'">{{ props.name || playerId }}</div>
    <div v-if="!mini" class="mt-1 flex flex-wrap items-center justify-center gap-1 text-[11px] text-gray-500">
      <template v-if="info?.role === 'landlord'">地主</template>
      <template v-else-if="info?.role === 'peasant'">农民</template>
      <span v-if="modelName" class="rounded-full bg-black/5 px-2 py-0.5 text-[10px] text-gray-600">{{ modelName }}</span>
    </div>
    <div :class="mini ? 'mt-0.5 text-base font-bold text-gray-700' : 'mt-1 text-lg font-bold text-gray-700'">
      🃏 {{ info?.cardsLeft ?? '?' }}
    </div>
    <div v-if="!mini && (roundTokens || totalTokens)" class="mt-2 flex flex-wrap justify-center gap-1 text-[11px]">
      <span v-if="roundTokens" class="rounded-full bg-amber-50 px-2 py-0.5 font-medium text-amber-700">本回 {{ roundTokens }}</span>
      <span v-if="totalTokens" class="rounded-full bg-emerald-50 px-2 py-0.5 font-medium text-emerald-700">累计 {{ totalTokens }}</span>
    </div>
    <!-- Mini mode: show total tokens inline -->
    <div v-if="mini && totalTokens" class="mt-0.5 text-[10px] text-amber-600">
      {{ totalTokens }}t
    </div>
    <div v-if="props.handCards?.length" class="mt-2 flex justify-center overflow-hidden rounded bg-gray-50 px-2 py-2" :class="mini ? 'max-w-[160px]' : 'max-w-[300px]'">
      <CardDisplay
        :cards="props.handCards"
        :compact="true"
        size="table"
        :show-count="false"
      />
    </div>

    <!-- Thinking Indicator with Bouncing Dots -->
    <div
      v-if="isThinking"
      class="mt-2 flex items-center justify-center gap-1 rounded bg-blue-50 px-2 py-1 text-xs text-blue-600"
    >
      <span>💭 思考中</span>
      <span class="thinking-dots">
        <span class="dot"></span>
        <span class="dot"></span>
        <span class="dot"></span>
      </span>
    </div>

    <!-- Response Time Badge -->
    <div
      v-if="responseTimeMs && !mini"
      class="absolute bottom-2 right-2 text-xs text-gray-400"
    >
      ⏱ {{ formatMs(responseTimeMs) }}
    </div>

    <!-- Action Bubble -->
    <div
      v-if="lastAction"
      class="action-bubble"
      :class="`action-${lastAction}`"
    >
      <template v-if="lastAction === 'play'">出牌</template>
      <template v-else-if="lastAction === 'pass'">不出</template>
      <template v-else-if="lastAction === 'grab'">抢地主</template>
    </div>
  </div>
</template>

<style scoped>
.player-card {
  position: relative;
}

/* Landlord gold border and shadow */
.landlord-card {
  border: 2px solid #fbbf24;
  box-shadow: 0 0 0 2px rgba(251, 191, 36, 0.3);
}

/* Crown drop shadow */
.crown-shadow {
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.3));
}

/* Thinking dots animation */
.thinking-dots {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  margin-left: 2px;
}

.thinking-dots .dot {
  display: inline-block;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background-color: #3b82f6;
  animation: bounce 1.4s infinite ease-in-out both;
}

.thinking-dots .dot:nth-child(1) {
  animation-delay: -0.32s;
}

.thinking-dots .dot:nth-child(2) {
  animation-delay: -0.16s;
}

.thinking-dots .dot:nth-child(3) {
  animation-delay: 0s;
}

@keyframes bounce {
  0%, 80%, 100% {
    transform: translateY(0);
  }
  40% {
    transform: translateY(-4px);
  }
}

/* Action bubble styles */
.action-bubble {
  position: absolute;
  bottom: -28px;
  left: 50%;
  transform: translateX(-50%);
  padding: 4px 12px;
  border-radius: 9999px;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
  animation: fadeIn 0.2s ease-out;
}

.action-play {
  background-color: #dcfce7;
  color: #16a34a;
}

.action-pass {
  background-color: #f3f4f6;
  color: #6b7280;
}

.action-grab {
  background-color: #fef3c7;
  color: #d97706;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(-4px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
}
</style>
