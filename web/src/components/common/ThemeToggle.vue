<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { useTheme } from '@/composables/useTheme'
import { cn } from '@/lib/cn'

const props = withDefaults(
  defineProps<{
    class?: string
  }>(),
  {},
)

const { isDark, toggleTheme } = useTheme()
</script>

<template>
  <button
    type="button"
    :class="
      cn(
        'inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-ink text-ink-text-secondary transition-colors hover:bg-ink-surface-muted hover:text-ink-text',
        props.class,
      )
    "
    :aria-label="isDark ? '切换到浅色模式' : '切换到深色模式'"
    :title="isDark ? '浅色模式' : '深色模式'"
    @click="toggleTheme"
  >
    <Icon :icon="isDark ? 'lucide:sun' : 'lucide:moon'" class="h-[18px] w-[18px]" />
  </button>
</template>
