<script setup lang="ts">
import { cn } from '@/lib/cn'

const props = withDefaults(
  defineProps<{
    variant?: 'default' | 'success' | 'warning' | 'danger' | 'accent' | 'muted'
    class?: string
  }>(),
  {
    variant: 'default',
  },
)

const variantClass: Record<string, string> = {
  default: 'bg-ink-primary-muted text-ink-primary',
  success: 'bg-ink-success/15 text-ink-success',
  warning: 'bg-ink-accent-muted text-ink-accent',
  danger: 'bg-ink-danger/15 text-ink-danger',
  accent: 'bg-ink-accent-muted text-ink-accent',
  muted: 'bg-ink-surface-muted text-ink-text-muted',
}
</script>

<template>
  <span
    :class="
      cn(
        'inline-flex items-center justify-center rounded-[6px] px-2 py-0.5 text-sm font-medium leading-none',
        variantClass[variant],
        props.class,
      )
    "
  >
    <slot />
  </span>
</template>
