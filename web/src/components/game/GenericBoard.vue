<script setup lang="ts">
import { computed } from 'vue'
import type { ObserverSnapshot } from '@/types/observer'
import { displayCard, isRedCard } from '@/utils/card'
import { cn } from '@/lib/cn'
import UiSpinner from '@/components/ui/Spinner.vue'
import UiEmpty from '@/components/ui/Empty.vue'

const props = defineProps<{
  snapshot: ObserverSnapshot | null
  thinkingPlayerId?: string
  playerNames?: Record<string, string>
  loading?: boolean
  emptyHint?: string
}>()

const phaseLabel = computed(() => {
  const p = props.snapshot?.phase
  if (p === 'bidding') return '叫分'
  if (p === 'playing') return '出牌'
  return p || '—'
})

function displayName(id: string): string {
  return props.playerNames?.[id] || id
}

function actionLabel(type?: string, label?: string): string {
  if (label) return label
  if (type === 'PASS') return '不出'
  return type || ''
}
</script>

<template>
  <div class="relative flex h-full min-h-0 flex-col bg-ink-obs-bg text-ink-obs-text">
    <UiSpinner v-if="loading" overlay label="加载中…" class="text-ink-obs-text" />

    <header
      v-if="snapshot"
      class="flex shrink-0 flex-wrap items-center gap-3 border-b border-ink-obs-border px-4 py-3"
    >
      <span class="rounded-[6px] bg-ink-obs-surface px-2 py-0.5 text-xs text-ink-obs-muted">
        {{ snapshot.game_type }}
      </span>
      <span class="text-sm font-medium">{{ phaseLabel }}</span>
      <span class="text-sm text-ink-obs-muted">第 {{ snapshot.round }} 轮</span>
      <div
        v-for="slot in snapshot.table?.slots || []"
        :key="slot.key"
        class="flex items-center gap-1.5 rounded-[6px] border border-ink-obs-border bg-ink-obs-surface px-2 py-1"
      >
        <span class="text-xs text-ink-obs-muted">{{ slot.label }}</span>
        <span
          v-for="(card, i) in slot.cards || []"
          :key="`${slot.key}-${i}`"
          class="text-sm font-semibold"
          :class="isRedCard(card) ? 'text-red-400' : 'text-ink-obs-text'"
        >
          {{ displayCard(card) }}
        </span>
      </div>
    </header>

    <div v-if="!snapshot && !loading" class="flex flex-1 items-center justify-center">
      <UiEmpty :title="emptyHint || '等待对局状态'" class="text-ink-obs-muted" />
    </div>

    <ul v-else-if="snapshot" class="flex-1 space-y-2 overflow-y-auto p-4">
      <li
        v-for="player in snapshot.players"
        :key="player.id"
        :class="
          cn(
            'rounded-ink-md border border-ink-obs-border bg-ink-obs-surface px-4 py-3 transition-shadow duration-300',
            player.is_active && 'border-ink-obs-accent/50',
            thinkingPlayerId === player.id && 'animate-pulse shadow-[0_0_0_1px_var(--ink-obs-pulse)]',
          )
        "
      >
        <div class="flex flex-wrap items-center gap-2">
          <span class="font-medium">{{ displayName(player.id) }}</span>
          <span
            v-for="badge in player.badges || []"
            :key="badge"
            class="rounded-[6px] bg-ink-obs-bg px-1.5 py-0.5 text-[11px] text-ink-obs-muted"
          >
            {{ badge }}
          </span>
          <span
            v-if="thinkingPlayerId === player.id"
            class="text-xs text-ink-obs-accent"
          >
            思考中…
          </span>
          <span v-else-if="player.is_active" class="text-xs text-ink-obs-accent">行动中</span>
          <span class="ml-auto text-xs text-ink-obs-muted">剩余 {{ player.hand_count }}</span>
        </div>

        <div v-if="player.hand_cards?.length" class="mt-2 flex flex-wrap gap-1">
          <span
            v-for="(card, i) in player.hand_cards"
            :key="i"
            class="inline-block text-sm font-semibold"
            :class="isRedCard(card) ? 'text-red-400' : 'text-ink-obs-text'"
          >
            {{ displayCard(card) }}
          </span>
        </div>
        <p v-else class="mt-2 text-xs text-ink-obs-muted">手牌隐藏 · 剩余 {{ player.hand_count }} 张</p>

        <div
          v-if="player.last_action"
          class="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-ink-obs-muted"
        >
          <span>最近：</span>
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
  </div>
</template>
