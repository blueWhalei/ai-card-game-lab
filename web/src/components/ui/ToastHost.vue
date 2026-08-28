<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { cn } from '@/lib/cn'
import { dismissToast, useToast, type ToastKind } from './toast'

const { items } = useToast()

const kindClass: Record<ToastKind, string> = {
  success: 'border-ink-success/30 bg-ink-surface text-ink-success',
  error: 'border-ink-danger/30 bg-ink-surface text-ink-danger',
  warning: 'border-ink-accent/40 bg-ink-surface text-ink-accent',
  info: 'border-ink-border bg-ink-surface text-ink-text',
}

const kindIcon: Record<ToastKind, string> = {
  success: 'lucide:check-circle',
  error: 'lucide:alert-circle',
  warning: 'lucide:alert-triangle',
  info: 'lucide:info',
}
</script>

<template>
  <div
    class="pointer-events-none fixed bottom-4 left-1/2 z-[100] flex w-[min(92vw,360px)] -translate-x-1/2 flex-col gap-2"
    aria-live="polite"
  >
    <div
      v-for="item in items"
      :key="item.id"
      :class="
        cn(
          'pointer-events-auto flex items-start gap-2 rounded-ink-md border px-3 py-2.5 text-sm shadow-[var(--ink-shadow-md)]',
          kindClass[item.kind],
        )
      "
    >
      <Icon :icon="kindIcon[item.kind]" class="mt-0.5 h-4 w-4 shrink-0" />
      <p class="flex-1 text-ink-text">{{ item.message }}</p>
      <button
        type="button"
        class="rounded p-0.5 text-ink-text-muted hover:text-ink-text"
        aria-label="关闭"
        @click="dismissToast(item.id)"
      >
        <Icon icon="lucide:x" class="h-3.5 w-3.5" />
      </button>
    </div>
  </div>
</template>
