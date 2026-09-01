<script setup lang="ts">
import { computed } from 'vue'
import { cn } from '@/lib/cn'

const props = withDefaults(
  defineProps<{
    names: string[]
    /** Max chips before overflow “+N”. */
    max?: number
    class?: string
  }>(),
  {
    max: 3,
  },
)

const visible = computed(() => props.names.slice(0, props.max))
const overflow = computed(() => Math.max(0, props.names.length - props.max))
const overflowTitle = computed(() =>
  overflow.value > 0 ? props.names.slice(props.max).join(' · ') : undefined,
)
</script>

<template>
  <div :class="cn('flex min-w-0 flex-nowrap items-center gap-1', props.class)">
    <span
      v-for="(name, i) in visible"
      :key="`${name}-${i}`"
      class="inline-flex max-w-[7rem] shrink-0 truncate rounded-[6px] bg-ink-surface-muted px-1.5 py-0.5 text-xs text-ink-text-secondary"
      :title="name"
    >
      {{ name }}
    </span>
    <span
      v-if="overflow > 0"
      class="shrink-0 rounded-[6px] bg-ink-surface-muted px-1.5 py-0.5 text-xs tabular-nums text-ink-text-muted"
      :title="overflowTitle"
    >
      +{{ overflow }}
    </span>
  </div>
</template>
