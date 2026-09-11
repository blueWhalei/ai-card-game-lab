<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { ReplayData } from '@/api/gameApi'
import UiButton from '@/components/ui/Button.vue'

defineProps<{
  replayData: ReplayData | null
  replayIndex: number
  replayPlaying: boolean
  replaySpeed: number
}>()

defineEmits<{
  seek: [index: number]
  prev: []
  play: []
  pause: []
  next: []
  'update:replaySpeed': [speed: number]
}>()

const { t } = useI18n()
</script>

<template>
  <div
    v-if="replayData"
    class="flex shrink-0 flex-wrap items-center justify-center gap-ink-2 border-b border-ink-obs-border bg-ink-obs-surface/80 px-ink-4 py-ink-2"
  >
    <div class="flex w-full max-w-3xl items-center gap-3">
      <input
        type="range"
        min="0"
        :max="Math.max(0, replayData.rounds.length - 1)"
        :value="replayIndex"
        :disabled="replayData.rounds.length < 2"
        :aria-label="t('game.replayPosition')"
        :aria-valuetext="
          t('game.replay', {
            current: replayData.rounds.length ? replayIndex + 1 : 0,
            total: replayData.rounds.length,
          })
        "
        class="min-w-0 flex-1 accent-[var(--ink-obs-accent)]"
        @input="$emit('seek', Number(($event.target as HTMLInputElement).value))"
      />
      <span class="rounded-ink bg-ink-obs-bg px-3 py-1 text-caption font-medium text-ink-obs-muted">
        {{
          t('game.replay', {
            current: replayData.rounds.length ? replayIndex + 1 : 0,
            total: replayData.rounds.length,
          })
        }}
      </span>
    </div>
    <UiButton size="sm" variant="secondary" :disabled="replayIndex <= 0" @click="$emit('prev')">
      {{ t('game.prevStep') }}
    </UiButton>
    <UiButton
      v-if="!replayPlaying"
      size="sm"
      :disabled="replayIndex >= replayData.rounds.length - 1"
      @click="$emit('play')"
    >
      {{ t('game.playBtn') }}
    </UiButton>
    <UiButton v-else size="sm" variant="secondary" @click="$emit('pause')">{{
      t('common.pause')
    }}</UiButton>
    <UiButton
      size="sm"
      variant="secondary"
      :disabled="replayIndex >= replayData.rounds.length - 1"
      @click="$emit('next')"
    >
      {{ t('game.nextStep') }}
    </UiButton>
    <select
      :value="replaySpeed"
      :aria-label="t('game.replaySpeed')"
      class="w-max rounded-ink border border-ink-obs-border bg-ink-obs-bg px-3 py-1.5 text-caption text-ink-obs-text"
      @change="$emit('update:replaySpeed', Number(($event.target as HTMLSelectElement).value))"
    >
      <option :value="2000">0.5x</option>
      <option :value="1000">1x</option>
      <option :value="500">2x</option>
      <option :value="250">4x</option>
    </select>
  </div>
</template>
