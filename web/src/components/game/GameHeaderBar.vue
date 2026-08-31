<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { GameItem } from '@/api/gameApi'
import UiButton from '@/components/ui/Button.vue'
import UiBadge from '@/components/ui/Badge.vue'

defineProps<{
  game: GameItem | null
  isConnected: boolean
  isStarted: boolean
  isPaused: boolean
  isFinished: boolean
  isReplayMode: boolean
  totalTokens: number
  latestModelName: string | undefined
}>()

defineEmits<{
  back: []
  start: []
  pause: []
  resume: []
}>()

const { t } = useI18n()
</script>

<template>
  <div
    class="flex shrink-0 items-center justify-between border-b border-ink-obs-border bg-ink-obs-surface/90 px-4 py-3 backdrop-blur"
  >
    <div class="flex flex-wrap items-center gap-3">
      <button
        type="button"
        class="text-sm text-ink-obs-accent hover:underline"
        @click="$emit('back')"
      >
        {{ t('game.back') }}
      </button>
      <span v-if="game" class="font-mono text-xs text-ink-obs-muted">{{ game.id }}</span>
      <span
        class="inline-block h-2 w-2 rounded-full"
        :class="isConnected ? 'bg-ink-success' : 'bg-ink-danger'"
      />
      <span class="text-xs" :class="isConnected ? 'text-ink-success' : 'text-ink-danger'">
        {{ isConnected ? t('game.connected') : t('game.connecting') }}
      </span>
      <UiBadge v-if="totalTokens > 0" variant="accent">
        Token {{ totalTokens.toLocaleString() }}
      </UiBadge>
      <span v-if="latestModelName" class="text-xs text-ink-obs-muted">{{ latestModelName }}</span>
    </div>
    <div class="flex items-center gap-2">
      <UiButton v-if="!isStarted && !isFinished" size="sm" @click="$emit('start')">{{
        t('common.start')
      }}</UiButton>
      <UiButton
        v-if="isStarted && !isPaused && !isFinished"
        size="sm"
        variant="secondary"
        @click="$emit('pause')"
      >
        {{ t('common.pause') }}
      </UiButton>
      <UiButton v-if="isPaused" size="sm" @click="$emit('resume')">{{ t('common.resume') }}</UiButton>
      <UiBadge v-if="isFinished && !isReplayMode" variant="danger">{{ t('game.ended') }}</UiBadge>
      <slot name="replay-controls" />
    </div>
  </div>
</template>
