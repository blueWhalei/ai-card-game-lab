<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import UiButton from '@/components/ui/Button.vue'
import type { GameHighlight } from '@/api/gameApi'
import { formatPlayAction } from '@/utils/traceOutput'

const props = withDefaults(
  defineProps<{
    items: GameHighlight[]
    gameId: string
    playerNames?: Record<string, string>
    tone?: 'lab' | 'observer'
    showJump?: boolean
  }>(),
  {
    playerNames: () => ({}),
    tone: 'lab',
    showJump: true,
  },
)

const emit = defineEmits<{
  jump: [item: GameHighlight]
}>()

const { t } = useI18n()
const router = useRouter()

function reasonLabel(reason: string): string {
  const key = `game.highlight.${reason}`
  const translated = t(key)
  return translated === key ? reason : translated
}

function playerLabel(id: string): string {
  return props.playerNames[id] || id
}

function actionLabel(item: GameHighlight): string {
  return formatPlayAction({ action_type: item.action_type, cards: item.cards })
}

function goDecision(item: GameHighlight): void {
  void router.push({
    path: '/decisions',
    query: { game_id: props.gameId, decision_id: item.decision_id },
  })
}
</script>

<template>
  <div v-if="items.length" class="space-y-2 text-left">
    <ol class="space-y-2">
      <li
        v-for="item in items"
        :key="item.decision_id || `${item.round_number}-${item.player_id}`"
        :class="
          tone === 'observer'
            ? 'rounded-ink border border-ink-obs-border bg-ink-obs-bg px-3 py-2'
            : 'rounded-ink border border-ink-border bg-ink-surface-muted px-3 py-2'
        "
      >
        <div class="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-xs">
          <span
            :class="tone === 'observer' ? 'font-mono text-ink-obs-muted' : 'font-mono text-ink-text-muted'"
          >
            R{{ item.round_number }}
          </span>
          <span :class="tone === 'observer' ? 'text-ink-obs-text' : 'text-ink-text'">
            {{ playerLabel(item.player_id) }}
          </span>
          <span :class="tone === 'observer' ? 'text-ink-obs-muted' : 'text-ink-text-muted'">
            {{ reasonLabel(item.reason) }}
          </span>
        </div>
        <div
          class="mt-0.5 text-sm"
          :class="tone === 'observer' ? 'text-ink-obs-text' : 'text-ink-text'"
        >
          {{ actionLabel(item) }}
        </div>
        <div class="mt-1.5 flex flex-wrap gap-1">
          <UiButton
            v-if="showJump"
            size="sm"
            variant="ghost"
            @click="emit('jump', item)"
          >
            {{ t('game.jumpToMove') }}
          </UiButton>
          <UiButton size="sm" variant="ghost" @click="goDecision(item)">
            {{ t('game.viewDecision') }}
          </UiButton>
        </div>
      </li>
    </ol>
  </div>
</template>
