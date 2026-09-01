<script setup lang="ts">
import { cn } from '@/lib/cn'

const props = withDefaults(
  defineProps<{
    rows?: number
    class?: string
  }>(),
  {
    rows: 5,
  },
)
</script>

<template>
  <div :class="cn('space-y-2', props.class)" aria-hidden="true">
    <div v-for="i in rows" :key="i" class="ink-skeleton h-12 rounded-ink" />
  </div>
</template>
