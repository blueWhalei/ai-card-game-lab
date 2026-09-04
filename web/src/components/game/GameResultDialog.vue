<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import UiDialog from '@/components/ui/Dialog.vue'
import UiButton from '@/components/ui/Button.vue'
import UiBadge from '@/components/ui/Badge.vue'
import GameHighlightList from '@/components/game/GameHighlightList.vue'
import type { GameHighlight } from '@/api/gameApi'

const props = defineProps<{
  modelValue: boolean
  gameId: string
  winner: {
    name?: string
    id: string
    role?: string
    totalRounds?: number
  } | null
  highlights?: GameHighlight[]
  playerNames?: Record<string, string>
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  back: []
  jump: [item: GameHighlight]
}>()

const { t } = useI18n()
const router = useRouter()

function onBack(): void {
  emit('update:modelValue', false)
  emit('back')
}

function goDecisions(): void {
  emit('update:modelValue', false)
  void router.push({ path: '/decisions', query: { game_id: props.gameId } })
}

function onJump(item: GameHighlight): void {
  emit('update:modelValue', false)
  emit('jump', item)
}
</script>

<template>
  <UiDialog
    :open="modelValue"
    :title="t('game.resultTitle')"
    @update:open="emit('update:modelValue', $event)"
  >
    <div v-if="winner" class="py-2 text-center">
      <h3 class="mb-3 text-xl font-semibold text-ink-text">
        {{ t('game.won', { name: winner.name || winner.id }) }}
      </h3>
      <UiBadge :variant="winner.role === 'landlord' ? 'danger' : 'success'">
        {{ winner.role === 'landlord' ? t('game.landlord') : t('game.peasant') }}
      </UiBadge>
      <p class="mt-4 text-sm text-ink-text-muted">{{
        t('game.totalRounds', { n: winner.totalRounds })
      }}</p>
      <p class="mt-2 text-sm text-ink-text-secondary">
        {{ t('game.resultNextStep') }}
      </p>
    </div>
    <div v-if="highlights?.length" class="mt-4 border-t border-ink-border pt-3">
      <p class="mb-2 text-sm font-medium text-ink-text">{{ t('game.highlightsTitle') }}</p>
      <GameHighlightList
        :items="highlights"
        :game-id="gameId"
        :player-names="playerNames"
        @jump="onJump"
      />
    </div>
    <template #footer>
      <div class="flex w-full flex-wrap justify-end gap-2">
        <UiButton variant="ghost" @click="onBack">{{ t('game.backToList') }}</UiButton>
        <UiButton @click="goDecisions">{{ t('game.viewDecisions') }}</UiButton>
      </div>
    </template>
  </UiDialog>
</template>
