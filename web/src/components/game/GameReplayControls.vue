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
  prev: []
  play: []
  pause: []
  next: []
  'update:replaySpeed': [speed: number]
}>()

const { t } = useI18n()
</script>

<template>
  <template v-if="replayData">
    <span class="rounded-ink bg-ink-obs-bg px-3 py-1 text-xs font-medium text-ink-obs-muted">
      {{ t('game.replay', { current: replayIndex + 1, total: replayData.rounds.length }) }}
    </span>
    <UiButton
      size="sm"
      variant="secondary"
      :disabled="replayIndex <= 0"
      @click="$emit('prev')"
    >
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
      class="w-max rounded-ink border border-ink-obs-border bg-ink-obs-bg px-3 py-1.5 text-xs text-ink-obs-text"
      @change="
        $emit('update:replaySpeed', Number(($event.target as HTMLSelectElement).value))
      "
    >
      <option :value="2000">0.5x</option>
      <option :value="1000">1x</option>
      <option :value="500">2x</option>
      <option :value="250">4x</option>
    </select>
  </template>
</template>
