<script setup lang="ts">
import { cn } from '@/lib/cn'

export type KpiItem = {
  id: string
  label: string
  value: string
  title?: string
  tone?: 'default' | 'primary' | 'danger' | 'muted'
  onClick?: () => void
}

defineProps<{
  items: KpiItem[]
  class?: string
}>()

const toneClass: Record<NonNullable<KpiItem['tone']>, string> = {
  default: 'text-ink-text',
  primary: 'text-ink-primary',
  danger: 'text-ink-danger',
  muted: 'text-ink-text-muted',
}
</script>

<template>
  <div
    :class="
      cn(
        'grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-6',
        $props.class,
      )
    "
  >
    <component
      :is="item.onClick ? 'button' : 'div'"
      v-for="item in items"
      :key="item.id"
      type="button"
      class="ink-kpi rounded-ink border border-ink-border bg-ink-surface px-3 py-2 text-left"
      :class="item.onClick ? 'hover:border-ink-primary/40 hover:bg-ink-primary-muted/40' : ''"
      :title="item.title"
      @click="item.onClick?.()"
    >
      <div :class="cn('ink-kpi-value', toneClass[item.tone ?? 'default'])">
        {{ item.value }}
      </div>
      <div class="ink-kpi-label">{{ item.label }}</div>
    </component>
  </div>
</template>
