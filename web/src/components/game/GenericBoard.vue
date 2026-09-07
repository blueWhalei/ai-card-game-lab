<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ObserverPlayer, ObserverSnapshot } from '@/types/observer'
import { displayCard, isRedCard } from '@/utils/card'
import { gameTypeLabel } from '@/utils/constants'
import { cn } from '@/lib/cn'
import CardDisplay from '@/components/game/CardDisplay.vue'
import UiSpinner from '@/components/ui/Spinner.vue'
import UiEmpty from '@/components/ui/Empty.vue'

const props = defineProps<{
  snapshot: ObserverSnapshot | null
  thinkingPlayerId?: string
  /** First line of the live thought, shown on the thinking seat. */
  thinkingExcerpt?: string
  playerNames?: Record<string, string>
  loading?: boolean
  emptyHint?: string
}>()

const { t } = useI18n()

const phaseLabel = computed(() => {
  const p = props.snapshot?.phase
  if (p === 'bidding') return t('game.phaseBidding')
  if (p === 'playing') return t('game.phasePlaying')
  if (p === 'endgame') return t('game.phaseEndgame')
  return p || t('common.dash')
})

const tableSlots = computed(() => props.snapshot?.table?.slots ?? [])
const players = computed(() => props.snapshot?.players ?? [])

/** Seat areas by player count — table stays center; no game_type branch. */
const layoutClass = computed(() => {
  const n = players.value.length
  if (n <= 1) return 'board-grid--one'
  if (n === 2) return 'board-grid--two'
  if (n === 3) return 'board-grid--three'
  return 'board-grid--many'
})

function seatArea(index: number): string {
  const n = players.value.length
  if (n <= 1) return 'seat-main'
  if (n === 2) return index === 0 ? 'seat-top' : 'seat-bottom'
  if (n === 3) {
    if (index === 0) return 'seat-top'
    if (index === 1) return 'seat-left'
    return 'seat-right'
  }
  if (index === 0) return 'seat-top'
  if (index === 1) return 'seat-left'
  if (index === 2) return 'seat-right'
  return 'seat-bottom'
}

function displayName(id: string): string {
  return props.playerNames?.[id] || id
}

function actionLabel(type?: string, label?: string): string {
  if (type === 'PASS') return t('action.PASS')
  if (label) return label
  return type || ''
}

function badgeLabel(badge: string): string {
  if (badge === 'landlord') return t('game.landlord')
  if (badge === 'peasant') return t('game.peasant')
  if (badge === 'unknown') return t('game.roleUnknown')
  return badge
}

function slotDisplayLabel(key: string, label: string): string {
  if (key === 'landlord') return t('game.bottomCards')
  return label
}

function seatClasses(player: ObserverPlayer): string {
  return cn(
    'rounded-ink-md border border-ink-obs-border/80 bg-ink-obs-surface/80 px-ink-4 py-ink-3 transition-shadow duration-(--ink-duration-content)',
    player.is_active && 'border-ink-obs-accent/50',
    props.thinkingPlayerId === player.id && 'ink-obs-glow',
  )
}
</script>

<template>
  <div class="ink-obs-felt relative flex h-full min-h-0 flex-col text-ink-obs-text">
    <UiSpinner v-if="loading" overlay :label="t('common.loading')" class="text-ink-obs-text" />

    <div v-if="!snapshot && !loading" class="flex flex-1 items-center justify-center">
      <UiEmpty :title="emptyHint || t('game.waitState')" class="text-ink-obs-muted" />
    </div>

    <template v-else-if="snapshot">
      <p class="shrink-0 px-ink-4 pt-ink-3 text-caption text-ink-obs-muted">
        {{ gameTypeLabel(snapshot.game_type) }}
        ·
        {{ phaseLabel }}
        ·
        {{ t('game.roundN', { n: snapshot.round }) }}
      </p>

      <div
        :class="cn('board-grid min-h-0 flex-1 gap-ink-3 overflow-y-auto px-ink-4 py-ink-4', layoutClass)"
      >
        <div
          v-for="(player, index) in players"
          :key="player.id"
          :class="seatClasses(player)"
          :style="{ gridArea: seatArea(index) }"
        >
          <div class="flex flex-wrap items-baseline gap-ink-2">
            <span class="text-body font-medium">{{ displayName(player.id) }}</span>
            <span
              v-for="badge in player.badges || []"
              :key="badge"
              class="text-caption text-ink-obs-muted"
            >
              {{ badgeLabel(badge) }}
            </span>
            <span
              v-if="thinkingPlayerId === player.id"
              class="text-caption text-ink-obs-accent"
            >
              {{ t('game.thinking') }}
            </span>
            <span v-else-if="player.is_active" class="text-caption text-ink-obs-accent">{{
              t('game.acting')
            }}</span>
            <span class="ml-auto text-caption text-ink-obs-muted">{{
              t('game.remaining', { n: player.hand_count })
            }}</span>
          </div>

          <div v-if="player.hand_cards?.length" class="mt-ink-2 overflow-x-auto">
            <CardDisplay :cards="player.hand_cards" :show-count="false" compact />
          </div>
          <p v-else class="mt-ink-2 text-caption text-ink-obs-muted">
            {{ t('game.hiddenHand', { n: player.hand_count }) }}
          </p>

          <p
            v-if="thinkingPlayerId === player.id && thinkingExcerpt"
            class="mt-ink-2 max-w-2xl text-lead text-ink-obs-text"
          >
            {{ thinkingExcerpt }}
          </p>

          <div
            v-if="player.last_action"
            class="mt-ink-2 flex flex-wrap items-center gap-ink-1 text-caption text-ink-obs-muted"
          >
            <span>{{ t('game.latest') }}</span>
            <span class="text-ink-obs-text">
              {{ actionLabel(player.last_action.type, player.last_action.label) }}
            </span>
            <span
              v-for="(card, i) in player.last_action.cards || []"
              :key="`la-${i}`"
              class="font-semibold"
              :class="isRedCard(card) ? 'text-red-400' : 'text-ink-obs-text'"
            >
              {{ displayCard(card) }}
            </span>
          </div>
        </div>

        <div
          class="flex min-h-[7rem] flex-col justify-center gap-ink-3 rounded-ink-md border border-ink-obs-border/60 bg-black/25 px-ink-4 py-ink-4"
          style="grid-area: table"
        >
          <template v-if="tableSlots.length > 0">
            <div
              v-for="slot in tableSlots"
              :key="slot.key"
              class="flex flex-wrap items-center justify-center gap-ink-3"
            >
              <span class="text-caption text-ink-obs-muted">
                {{ slotDisplayLabel(slot.key, slot.label) }}
              </span>
              <CardDisplay
                v-if="slot.cards?.length"
                :cards="slot.cards"
                :show-count="false"
                size="table"
              />
            </div>
          </template>
          <p v-else class="text-center text-caption text-ink-obs-muted">
            {{ t('game.tableEmpty') }}
          </p>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.ink-obs-felt {
  background:
    radial-gradient(ellipse 90% 70% at 50% 30%, #1a2a24 0%, var(--ink-obs-bg) 72%);
}

.board-grid {
  display: grid;
  align-content: stretch;
}

.board-grid--one {
  grid-template-areas:
    'table'
    'seat-main';
  grid-template-rows: minmax(7rem, 0.4fr) 1fr;
}

.board-grid--two {
  grid-template-areas:
    'seat-top'
    'table'
    'seat-bottom';
  grid-template-rows: auto minmax(7rem, 1fr) auto;
}

.board-grid--three {
  grid-template-areas:
    'seat-top seat-top'
    'seat-left table'
    'seat-right table';
  grid-template-columns: 1fr 1.2fr;
  grid-template-rows: auto minmax(7rem, 1fr) auto;
}

@media (min-width: 1024px) {
  .board-grid--three {
    grid-template-areas:
      '. seat-top .'
      'seat-left table seat-right';
    grid-template-columns: 1fr minmax(12rem, 1.4fr) 1fr;
    grid-template-rows: auto minmax(8rem, 1fr);
  }
}

.board-grid--many {
  grid-template-areas:
    'seat-top seat-top seat-top'
    'seat-left table seat-right'
    'seat-bottom seat-bottom seat-bottom';
  grid-template-columns: 1fr minmax(10rem, 1.2fr) 1fr;
  grid-template-rows: auto minmax(7rem, 1fr) auto;
}
</style>
