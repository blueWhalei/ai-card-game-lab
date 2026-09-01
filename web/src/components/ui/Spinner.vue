<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
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

const { t } = useI18n()
const aria = computed(() => props.label ?? t('common.loading'))

/** ViewBox 48×24 — Pac-C on the left, three card-dots on the right. */
const frameClass = {
  sm: 'h-4 w-8',
  md: 'h-6 w-12',
  lg: 'h-8 w-16',
} as const
</script>

<template>
  <div
    :class="
      cn(
        'flex flex-col items-center justify-center gap-2',
        overlay && 'absolute inset-0 z-10 bg-ink-paper/70 backdrop-blur-[1px]',
        props.class,
      )
    "
    role="status"
    :aria-label="aria"
  >
    <svg
      :class="cn('ink-c-pac text-ink-primary', frameClass[size])"
      viewBox="0 0 48 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <!-- Open / closed mouths crossfade = CardLab “C” chomp -->
      <path
        class="ink-c-pac-shape ink-c-pac-open"
        fill="currentColor"
        d="M12 12 L20.2 4.8 A9 9 0 1 0 20.2 19.2 Z"
      />
      <path
        class="ink-c-pac-shape ink-c-pac-shut"
        fill="currentColor"
        d="M12 12 L18.6 8.4 A9 9 0 1 0 18.6 15.6 Z"
      />
      <circle class="ink-c-pac-dot ink-c-pac-dot-1" cx="27" cy="12" r="2.15" fill="currentColor" />
      <circle class="ink-c-pac-dot ink-c-pac-dot-2" cx="35" cy="12" r="2.15" fill="currentColor" />
      <circle class="ink-c-pac-dot ink-c-pac-dot-3" cx="43" cy="12" r="2.15" fill="currentColor" />
    </svg>
    <span v-if="label" class="text-xs text-ink-text-muted">{{ label }}</span>
  </div>
</template>
