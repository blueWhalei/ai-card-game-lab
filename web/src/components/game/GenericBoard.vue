<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ObserverSnapshot } from '@/types/observer'
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
        v-if="tableSlots.length > 0"
        class="mx-ink-4 mt-ink-3 rounded-ink-md border border-ink-obs-border/80 bg-black/20 px-ink-4 py-ink-3"
      >
        <div v-for="slot in tableSlots" :key="slot.key" class="flex flex-wrap items-center gap-ink-3">
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
      </div>

      <ul class="flex-1 space-y-ink-3 overflow-y-auto px-ink-4 py-ink-4">
        <li
          v-for="player in snapshot.players"
          :key="player.id"
          :class="
            cn(
              'rounded-ink-md border border-ink-obs-border/80 bg-ink-obs-surface/80 px-ink-4 py-ink-3 transition-shadow duration-(--ink-duration-content)',
              player.is_active && 'border-ink-obs-accent/50',
              thinkingPlayerId === player.id && 'ink-obs-glow',
            )
          "
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
        </li>
      </ul>
    </template>
  </div>
</template>

<style scoped>
.ink-obs-felt {
  background:
    radial-gradient(ellipse 90% 70% at 50% 30%, #1a2a24 0%, var(--ink-obs-bg) 72%);
}
</style>
