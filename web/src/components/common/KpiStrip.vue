<script setup lang="ts">
import { cn } from '@/lib/cn'
import MetricHint from '@/components/common/MetricHint.vue'

export type KpiItem = {
  id: string
  label: string
  value: string
  title?: string
  tone?: 'default' | 'primary' | 'danger' | 'muted'
  onClick?: () => void
  hintPlain?: string
  hintFormula?: string
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
    <div
      v-for="item in items"
      :key="item.id"
      class="ink-kpi rounded-ink border border-ink-border bg-ink-surface px-3 py-2 text-left"
      :class="item.onClick ? 'hover:border-ink-primary/40 hover:bg-ink-primary-muted/40' : ''"
      :title="item.title"
    >
      <component
        :is="item.onClick ? 'button' : 'div'"
        class="w-full text-left"
        :type="item.onClick ? 'button' : undefined"
        @click="item.onClick?.()"
      >
        <div :class="cn('ink-kpi-value', toneClass[item.tone ?? 'default'])">
          {{ item.value }}
        </div>
      </component>
      <div class="mt-0.5 flex items-center gap-1">
        <div class="ink-kpi-label min-w-0">{{ item.label }}</div>
        <MetricHint
          v-if="item.hintPlain"
          :plain="item.hintPlain"
          :formula="item.hintFormula"
        />
      </div>
    </div>
  </div>
</template>
