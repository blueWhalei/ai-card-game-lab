<script setup lang="ts">
import { computed } from 'vue'
import type { PreflightCheck } from '@/api/systemApi'
import { cn } from '@/lib/cn'

const props = defineProps<{
  checks: PreflightCheck[]
  class?: string
}>()

const failed = computed(() => props.checks.filter((c) => !c.ok))
</script>

<template>
  <div
    v-if="failed.length > 0"
    :class="
      cn(
        'space-y-1.5 rounded-ink-md border px-3 py-2.5',
        failed.some((c) => c.severity === 'block')
          ? 'border-ink-danger/30 bg-ink-danger/5'
          : 'border-ink-accent/30 bg-ink-accent-muted/40',
        props.class,
      )
    "
  >
    <p
      v-for="item in failed"
      :key="item.id"
      class="text-sm leading-snug"
      :class="
        item.severity === 'block' ? 'text-ink-danger' : 'text-ink-text-secondary'
      "
    >
      {{ item.message }}
    </p>
  </div>
</template>
