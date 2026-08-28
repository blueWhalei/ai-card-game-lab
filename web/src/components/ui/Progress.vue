<script setup lang="ts">
import { ProgressIndicator, ProgressRoot } from 'reka-ui'
import { cn } from '@/lib/cn'

const props = withDefaults(
  defineProps<{
    value?: number
    class?: string
  }>(),
  {
    value: 0,
  },
)
</script>

<template>
  <ProgressRoot
    :model-value="Math.min(100, Math.max(0, value))"
    :class="cn('relative h-2 w-full overflow-hidden rounded-full bg-ink-surface-muted', props.class)"
  >
    <ProgressIndicator
      class="h-full rounded-full bg-ink-primary transition-[width] duration-300 ease-out"
      :style="{ width: `${Math.min(100, Math.max(0, value))}%` }"
    />
  </ProgressRoot>
</template>
