<script setup lang="ts">
import { computed } from 'vue'
import type { PlayerInfoProps } from '@/types/game'

const props = withDefaults(defineProps<PlayerInfoProps>(), {
  showRole: true,
  showCardsLeft: true,
  isCurrentPlayer: false,
  isThinking: false,
  responseTimeMs: undefined,
})

const roleDisplay = computed(() => {
  const roleMap: Record<string, string> = {
    landlord: '地主',
    peasant: '农民',
    unknown: '未知',
  }
  return roleMap[props.role] || props.role
})

const roleColor = computed(() => {
  const colorMap: Record<string, string> = {
    landlord: 'bg-red-100 text-red-800',
    peasant: 'bg-green-100 text-green-800',
    unknown: 'bg-gray-100 text-gray-800',
  }
  return colorMap[props.role] || 'bg-gray-100 text-gray-800'
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
    class="player-info rounded-lg border p-3 transition-all"
    :class="[
      isCurrentPlayer ? 'border-blue-500 bg-blue-50 ring-2 ring-blue-200' : 'border-gray-200 bg-white',
      isThinking ? 'animate-pulse' : '',
    ]"
  >
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <span class="font-medium text-gray-900">{{ name }}</span>
        <span
          v-if="showRole"
          class="rounded px-1.5 py-0.5 text-xs font-medium"
          :class="roleColor"
        >
          {{ roleDisplay }}
        </span>
      </div>
      <div class="flex items-center gap-2">
        <span
          v-if="showCardsLeft"
          class="text-sm text-gray-500"
        >
          {{ cardsLeft }} 张
        </span>
        <span
          v-if="formattedResponseTime"
          class="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600"
        >
          {{ formattedResponseTime }}
        </span>
      </div>
    </div>
    <div v-if="isThinking" class="mt-2 text-sm text-blue-600">
      <span class="inline-flex items-center gap-1">
        <svg class="h-4 w-4 animate-spin" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        思考中...
      </span>
    </div>
  </div>
</template>
