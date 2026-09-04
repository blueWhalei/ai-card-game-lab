<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { CardDisplayProps } from '@/types/game'
import { getCardInfo, isRedSuit, RANK_ORDER } from '@/utils/card'

const props = withDefaults(defineProps<CardDisplayProps>(), {
  cards: () => [],
  selected: () => [],
  showCount: true,
  interactive: false,
  compact: false,
  size: 'default',
  playing: false,
})

const emit = defineEmits<{
  toggle: [card: string]
}>()

const { t } = useI18n()

function isSelected(card: string): boolean {
  return props.selected.includes(card)
}

function toggleCard(card: string): void {
  if (props.interactive) {
    emit('toggle', card)
  }
}

const sortedCards = computed(() => {
  return [...props.cards].sort((a, b) => {
    const getRank = (card: string): number => {
      if (card === 'BJ') return 13
      if (card === 'RJ') return 14
      return RANK_ORDER.indexOf(card.slice(1))
    }
    return getRank(a) - getRank(b)
  })
})

const sizeConfig = {
  default: { width: 60, height: 84, overlap: 32, radius: 6 },
  table: { width: 52, height: 72, overlap: 30, radius: 6 },
  mini: { width: 36, height: 50, overlap: 18, radius: 4 },
} as const

const currentSize = computed(() => sizeConfig[props.size])

function compactStyle(index: number): Record<string, string | number> {
  if (!props.compact) return {}
  const { width, overlap } = currentSize.value
  return {
    zIndex: index,
    marginLeft: index === 0 ? 0 : `-${width - overlap}px`,
  }
}

const containerStyle = computed(() => {
  if (!props.compact || sortedCards.value.length === 0) {
    return {}
  }
  const { width: cardWidth, overlap } = currentSize.value
  const totalWidth = cardWidth + (sortedCards.value.length - 1) * overlap
  return { width: `${totalWidth}px` }
})

const sizeClass = computed(() =>
  props.size !== 'default' ? `playing-card--${props.size}` : '',
)
</script>

<template>
  <div class="card-display">
    <div v-if="showCount && cards.length > 0" class="mb-1 text-sm text-gray-500">
      {{ t('game.cardsCount', { n: cards.length }) }}
    </div>
    <div
      class="card-container"
      :class="{ 'card-container--compact': compact }"
      :style="containerStyle"
    >
      <div
        v-for="(card, index) in sortedCards"
        :key="card"
        class="playing-card"
        :class="[
          isRedSuit(card) ? 'playing-card--red' : 'playing-card--black',
          card === 'BJ' ? 'playing-card--black-joker' : '',
          card === 'RJ' ? 'playing-card--red-joker' : '',
          isSelected(card) ? 'playing-card--selected' : '',
          interactive ? 'playing-card--interactive' : '',
          sizeClass,
          playing ? 'playing-card--playing' : '',
        ]"
        :style="compactStyle(index)"
        @click="toggleCard(card)"
      >
        <div class="card-corner card-corner--top">
          <span class="card-rank">{{ getCardInfo(card).rank }}</span>
          <span class="card-suit">{{ getCardInfo(card).suit }}</span>
        </div>
        <div class="card-center">
          <span v-if="!getCardInfo(card).isJoker" class="card-suit-large">{{
            getCardInfo(card).suit
          }}</span>
          <span v-else class="card-joker-text">{{ getCardInfo(card).rank }}</span>
        </div>
        <div class="card-corner card-corner--bottom">
          <span class="card-rank">{{ getCardInfo(card).rank }}</span>
          <span class="card-suit">{{ getCardInfo(card).suit }}</span>
        </div>
      </div>
    </div>
    <div v-if="cards.length === 0" class="text-sm text-gray-400">{{ t('common.none') }}</div>
  </div>
</template>

<style scoped>
.card-display {
  display: inline-block;
}

.card-container {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.card-container--compact {
  flex-wrap: nowrap;
  gap: 0;
}

.playing-card {
  position: relative;
  width: 60px;
  height: 84px;
  border-radius: 6px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);
  border: 1px solid #e5e7eb;
  flex-shrink: 0;
  transition:
    transform 0.15s ease,
    box-shadow 0.15s ease;
  overflow: hidden;
}

.playing-card--black {
  color: #1f2937;
}

.playing-card--red {
  color: #dc2626;
}

.playing-card--black-joker {
  background: linear-gradient(135deg, #1f2937 0%, #fff 50%, #1f2937 100%);
}

.playing-card--red-joker {
  background: linear-gradient(135deg, #dc2626 0%, #fff 50%, #dc2626 100%);
}

.playing-card--interactive {
  cursor: pointer;
}

.playing-card--interactive:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.playing-card--selected {
  transform: translateY(-8px);
  border-color: #3b82f6;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
}

.playing-card--mini {
  width: 36px;
  height: 50px;
  border-radius: 4px;
}

.playing-card--mini .card-rank {
  font-size: 9px;
}

.playing-card--mini .card-suit {
  font-size: 7px;
}

.playing-card--mini .card-suit-large {
  font-size: 18px;
}

.playing-card--mini .card-joker-text {
  font-size: 8px;
}

.playing-card--mini .card-corner--top {
  top: 2px;
  left: 2px;
}

.playing-card--mini .card-corner--bottom {
  bottom: 2px;
  right: 2px;
}

.playing-card--table {
  width: 52px;
  height: 72px;
  border-radius: 6px;
}

.playing-card--table .card-rank {
  font-size: 13px;
}

.playing-card--table .card-suit {
  font-size: 10px;
}

.playing-card--table .card-suit-large {
  font-size: 24px;
}

.playing-card--table .card-joker-text {
  font-size: 10px;
}

.playing-card--table .card-corner--top {
  top: 3px;
  left: 3px;
}

.playing-card--table .card-corner--bottom {
  bottom: 3px;
  right: 3px;
}

.playing-card--playing {
  animation: cardPlay 0.35s ease-out forwards;
}

@keyframes cardPlay {
  0% {
    opacity: 0;
    transform: scale(0.5) translateY(20px);
  }
  60% {
    opacity: 1;
    transform: scale(1.05) translateY(-2px);
  }
  100% {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

.card-corner {
  position: absolute;
  display: flex;
  flex-direction: column;
  align-items: center;
  line-height: 1;
}

.card-corner--top {
  top: 4px;
  left: 4px;
}

.card-corner--bottom {
  bottom: 4px;
  right: 4px;
  transform: rotate(180deg);
}

.card-rank {
  font-size: 12px;
  font-weight: 700;
  font-family: 'Arial', sans-serif;
}

.card-suit {
  font-size: 10px;
}

.card-center {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}

.card-suit-large {
  font-size: 28px;
}

.card-joker-text {
  font-size: 10px;
  font-weight: 700;
  text-align: center;
  line-height: 1.2;
}
</style>
