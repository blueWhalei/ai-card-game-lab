<script setup lang="ts">
import { cn } from '@/lib/cn'

export type CompactRecord = {
  id: string
  primary: string
  secondary?: string
  meta?: string
  trailing?: string
  badge?: string
  badgeTone?: 'success' | 'warning' | 'muted' | 'danger'
}

const props = withDefaults(
  defineProps<{
    records: CompactRecord[]
    selectedId?: string | null
    class?: string
    listClass?: string
  }>(),
  {
    selectedId: null,
  },
)

const emit = defineEmits<{
  select: [id: string]
}>()

const badgeClass: Record<NonNullable<CompactRecord['badgeTone']>, string> = {
  success: 'text-ink-success',
  warning: 'text-ink-accent',
  muted: 'text-ink-text-muted',
  danger: 'text-ink-danger',
}
</script>

<template>
  <div :class="cn('h-[min(70vh,calc(100vh-14rem))] overflow-y-auto', props.listClass, props.class)">
    <div class="divide-y divide-ink-border">
      <button
        v-for="row in records"
        :key="row.id"
        type="button"
        class="flex w-full items-center gap-3 rounded-ink px-3 py-3 text-left transition-colors focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ink-primary"
        :class="selectedId === row.id ? 'bg-ink-primary-muted' : 'hover:bg-ink-surface-muted'"
        :aria-pressed="selectedId === row.id"
        @click="emit('select', row.id)"
      >
        <div class="min-w-0 flex-1">
          <div class="flex min-w-0 flex-wrap items-baseline gap-x-1.5 gap-y-1 text-sm">
            <span class="truncate font-medium text-ink-text">{{ row.primary }}</span>
            <span v-if="row.secondary" class="truncate text-ink-text-secondary">
              {{ row.secondary }}
            </span>
          </div>
          <div v-if="row.meta" class="mt-0.5 truncate text-xs text-ink-text-muted">
            {{ row.meta }}
          </div>
        </div>
        <div class="flex shrink-0 flex-col items-end gap-0.5">
          <span v-if="row.trailing" class="tabular-nums text-xs text-ink-text-muted">
            {{ row.trailing }}
          </span>
          <span v-if="row.badge" class="text-xs" :class="badgeClass[row.badgeTone ?? 'muted']">
            {{ row.badge }}
          </span>
        </div>
      </button>
    </div>
  </div>
</template>
