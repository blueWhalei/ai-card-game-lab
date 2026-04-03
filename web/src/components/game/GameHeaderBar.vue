<script setup lang="ts">
import type { GameItem } from '@/api/gameApi'

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
</script>

<template>
  <div class="flex shrink-0 items-center justify-between border-b border-black/[0.06] bg-white/80 px-6 py-3 backdrop-blur-xl">
    <div class="flex items-center gap-3">
      <button class="rounded-full px-3 py-1.5 text-sm text-[#0071e3] transition-colors hover:bg-[#f5f5f7]" @click="$emit('back')">← 返回</button>
      <h2 class="text-base font-semibold text-[#1d1d1f]">对局观察</h2>
      <span v-if="game" class="rounded-full bg-[#f5f5f7] px-2.5 py-0.5 font-mono text-xs text-[#86868b]">{{ game.id }}</span>
      <span class="inline-block h-2 w-2 rounded-full transition-colors" :class="isConnected ? 'bg-[#34c759]' : 'bg-[#ff3b30]'" />
      <span class="text-xs" :class="isConnected ? 'text-[#34c759]' : 'text-[#ff3b30]'">{{ isConnected ? '已连接' : '连接中...' }}</span>
      <span v-if="totalTokens > 0" class="rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700">
        总Token: {{ totalTokens.toLocaleString() }}
      </span>
      <span v-if="latestModelName" class="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-600">
        {{ latestModelName }}
      </span>
    </div>
    <div class="flex items-center gap-2">
      <button v-if="!isStarted && !isFinished" class="apple-btn" @click="$emit('start')">启动对局</button>
      <button v-if="isStarted && !isPaused && !isFinished" class="apple-btn-secondary" @click="$emit('pause')">暂停</button>
      <button v-if="isPaused" class="apple-btn" @click="$emit('resume')">继续</button>
      <span v-if="isFinished && !isReplayMode" class="rounded-full bg-red-50 px-3 py-1 text-xs font-medium text-[#ff3b30]">已结束</span>
      <slot name="replay-controls" />
    </div>
  </div>
</template>
