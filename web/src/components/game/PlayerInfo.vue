<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { PlayerInfoProps } from '@/types/game'
import UiSpinner from '@/components/ui/Spinner.vue'

const props = withDefaults(defineProps<PlayerInfoProps>(), {
  showRole: true,
  showCardsLeft: true,
  isCurrentPlayer: false,
  isThinking: false,
  responseTimeMs: undefined,
})

const { t } = useI18n()

const roleDisplay = computed(() => {
  if (props.role === 'landlord') return t('game.landlord')
  if (props.role === 'peasant') return t('game.peasant')
  if (props.role === 'unknown') return t('game.roleUnknown')
  return props.role
})

const formattedResponseTime = computed(() => {
  if (!props.responseTimeMs) return ''
  if (props.responseTimeMs < 1000) {
    return `${props.responseTimeMs}ms`
  }
  return `${(props.responseTimeMs / 1000).toFixed(1)}s`
})
</script>

<template>
  <div
    class="player-info rounded-ink border border-ink-border bg-ink-surface p-ink-3 transition-all"
    :class="[
      isCurrentPlayer ? 'border-ink-primary bg-ink-primary-muted ring-2 ring-ink-primary-muted' : '',
      isThinking ? 'animate-pulse' : '',
    ]"
  >
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-ink-2">
        <span class="font-medium text-ink-text">{{ name }}</span>
        <span
          v-if="showRole"
          class="rounded-ink bg-ink-surface-muted px-1.5 py-0.5 text-caption font-medium text-ink-text-secondary"
        >
          {{ roleDisplay }}
        </span>
      </div>
      <div class="flex items-center gap-ink-2">
        <span
          v-if="showCardsLeft"
          class="text-caption text-ink-text-muted"
        >
          {{ t('game.cardsCount', { n: cardsLeft }) }}
        </span>
        <span
          v-if="formattedResponseTime"
          class="rounded-ink bg-ink-surface-muted px-1.5 py-0.5 text-caption text-ink-text-secondary"
        >
          {{ formattedResponseTime }}
        </span>
      </div>
    </div>
    <div v-if="isThinking" class="mt-ink-2 text-caption text-ink-primary">
      <span class="inline-flex items-center gap-1.5">
        <UiSpinner size="sm" class="!gap-0 text-current" />
        {{ t('game.thinkingDots') }}
      </span>
    </div>
  </div>
</template>
