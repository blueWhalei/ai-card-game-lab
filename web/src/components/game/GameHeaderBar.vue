<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Icon } from '@iconify/vue'
import type { GameItem } from '@/api/gameApi'
import UiButton from '@/components/ui/Button.vue'
import UiBadge from '@/components/ui/Badge.vue'

defineProps<{
  game: GameItem | null
  title: string
  phaseLabel?: string
  isConnected: boolean
  isStarted: boolean
  isPaused: boolean
  isFinished: boolean
  isReplayMode: boolean
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
    class="flex shrink-0 items-center justify-between border-b border-ink-obs-border bg-ink-obs-surface/90 px-ink-4 py-ink-3 backdrop-blur"
  >
    <div class="flex min-w-0 flex-wrap items-center gap-ink-3">
      <button
        type="button"
        class="inline-flex items-center gap-1 text-body text-ink-obs-accent hover:underline"
        @click="$emit('back')"
      >
        <Icon icon="lucide:arrow-left" class="h-4 w-4" />
        {{ t('common.back') }}
      </button>
      <span class="truncate text-body font-medium">{{ title }}</span>
      <span
        v-if="phaseLabel"
        class="text-caption text-ink-obs-muted"
      >
        {{ phaseLabel }}
      </span>
      <span
        class="inline-block h-2 w-2 shrink-0 rounded-full"
        :class="isConnected ? 'bg-ink-success' : 'bg-ink-danger'"
        :title="isConnected ? t('game.connected') : t('game.connecting')"
        :aria-label="isConnected ? t('game.connected') : t('game.connecting')"
      />
    </div>
    <div class="flex items-center gap-ink-2">
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
    </div>
  </div>
</template>
