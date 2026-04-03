<script setup lang="ts">
import type { ReplayData } from '@/api/gameApi'

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
    <span class="rounded-full bg-[#f5f5f7] px-3 py-1 text-xs font-medium text-[#86868b]">回放 {{ replayIndex + 1 }} / {{ replayData.rounds.length }}</span>
    <button :disabled="replayIndex <= 0" class="apple-btn-secondary disabled:opacity-40" @click="$emit('prev')">上一步</button>
    <button v-if="!replayPlaying" class="apple-btn" :disabled="replayIndex >= replayData.rounds.length - 1" @click="$emit('play')">播放</button>
    <button v-else class="apple-btn-secondary" @click="$emit('pause')">暂停</button>
    <button :disabled="replayIndex >= replayData.rounds.length - 1" class="apple-btn-secondary disabled:opacity-40" @click="$emit('next')">下一步</button>
    <select :value="replaySpeed" class="rounded-full bg-[#f5f5f7] px-3 py-1.5 text-xs text-[#424245]" @change="$emit('update:replaySpeed', Number(($event.target as HTMLSelectElement).value))">
      <option :value="2000">0.5x</option>
      <option :value="1000">1x</option>
      <option :value="500">2x</option>
      <option :value="250">4x</option>
    </select>
  </template>
</template>
