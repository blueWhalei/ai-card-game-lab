<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { DecisionBoards, PairedDecision } from '@/api/researchApi'
import GenericBoard from '@/components/game/GenericBoard.vue'

const props = defineProps<{
  boards?: DecisionBoards
  point: PairedDecision
  showAll: boolean
  playerNames: Record<string, string>
}>()
const { t } = useI18n()
const snapshot = computed(() => {
  const value = props.boards?.frames[props.point.round_number]
  if (
    !value ||
    value.decision_id !== props.point.id ||
    value.snapshot.round !== props.point.round_number ||
    value.snapshot.current_player_id !== props.point.player_id
  )
    return null
  return {
    ...value.snapshot,
    players: value.snapshot.players.map((p) => ({
      ...p,
      hand_cards: props.showAll || p.id === props.point.player_id ? p.hand_cards : undefined,
    })),
  }
})
</script>

<template>
  <section :aria-label="t('pairedBoard.title')" class="space-y-ink-2">
    <p class="text-caption text-ink-text-secondary">{{ t('pairedBoard.before') }}</p>
    <GenericBoard v-if="snapshot" :snapshot="snapshot" :player-names="playerNames" compact />
    <p v-else role="status" class="text-caption text-ink-text-secondary">
      {{
        t(
          boards?.status === 'unsupported_engine'
            ? 'pairedBoard.unsupported'
            : 'pairedBoard.unverified',
        )
      }}
    </p>
  </section>
</template>
