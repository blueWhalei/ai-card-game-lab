<script setup lang="ts">
import { cn } from '@/lib/cn'

const props = withDefaults(
  defineProps<{
    variant?: 'default' | 'success' | 'warning' | 'danger' | 'accent' | 'muted'
    size?: 'sm' | 'xs'
    class?: string
  }>(),
  {
    variant: 'default',
    size: 'sm',
  },
)

const sizeClass: Record<NonNullable<typeof props.size>, string> = {
  sm: 'px-2 py-0.5 text-sm',
  xs: 'px-1.5 py-0.5 text-xs',
}

const variantClass: Record<string, string> = {
  default: 'bg-ink-primary-muted text-ink-primary',
  success: 'bg-ink-success/15 text-ink-success',
  warning: 'bg-ink-accent-muted text-ink-accent',
  danger: 'bg-ink-danger/15 text-ink-danger',
  accent: 'bg-ink-accent-muted text-ink-accent',
  muted: 'bg-ink-surface-muted text-ink-text-secondary',
}
</script>

<template>
  <span
    :class="
      cn(
        'inline-flex items-center justify-center rounded-[6px] font-medium leading-none',
        sizeClass[size],
        variantClass[variant],
        props.class,
      )
    "
  >
    <slot />
  </span>
</template>
