<script setup lang="ts">
import { cn } from '@/lib/cn'

const props = withDefaults(
  defineProps<{
    size?: 'sm' | 'md' | 'lg'
    label?: string
    class?: string
    overlay?: boolean
  }>(),
  {
    size: 'md',
    overlay: false,
  },
)

const sizeClass = {
  sm: 'h-4 w-4 border-2',
  md: 'h-6 w-6 border-2',
  lg: 'h-8 w-8 border-[3px]',
}
</script>

<template>
  <div
    :class="
      cn(
        'flex flex-col items-center justify-center gap-2',
        overlay && 'absolute inset-0 z-10 bg-ink-paper/70',
        props.class,
      )
    "
  >
    <div
      :class="
        cn(
          'animate-spin rounded-full border-ink-primary border-t-transparent',
          sizeClass[size],
        )
      "
      role="status"
      :aria-label="label ?? '加载中'"
    />
    <span v-if="label" class="text-xs text-ink-text-muted">{{ label }}</span>
  </div>
</template>
