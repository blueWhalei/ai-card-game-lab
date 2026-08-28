<script setup lang="ts">
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
</script>

<template>
  <template v-if="replayData">
    <span class="rounded-ink bg-ink-obs-bg px-3 py-1 text-xs font-medium text-ink-obs-muted">
      回放 {{ replayIndex + 1 }} / {{ replayData.rounds.length }}
    </span>
    <UiButton
      size="sm"
      variant="secondary"
      :disabled="replayIndex <= 0"
      @click="$emit('prev')"
    >
      上一步
    </UiButton>
    <UiButton
      v-if="!replayPlaying"
      size="sm"
      :disabled="replayIndex >= replayData.rounds.length - 1"
      @click="$emit('play')"
    >
      播放
    </UiButton>
    <UiButton v-else size="sm" variant="secondary" @click="$emit('pause')">暂停</UiButton>
    <UiButton
      size="sm"
      variant="secondary"
      :disabled="replayIndex >= replayData.rounds.length - 1"
      @click="$emit('next')"
    >
      下一步
    </UiButton>
    <select
      :value="replaySpeed"
      class="rounded-ink border border-ink-obs-border bg-ink-obs-bg px-3 py-1.5 text-xs text-ink-obs-text"
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
