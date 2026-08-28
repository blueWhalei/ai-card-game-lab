<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { cn } from '@/lib/cn'

const props = withDefaults(
  defineProps<{
    title?: string
    description?: string
    class?: string
  }>(),
  {
    title: '暂无内容',
  },
)
</script>

<template>
  <div :class="cn('flex flex-col items-center justify-center gap-2 px-4 py-12 text-center', props.class)">
    <Icon icon="lucide:inbox" class="h-10 w-10 text-ink-text-muted opacity-60" />
    <p class="text-sm font-medium text-ink-text">{{ title }}</p>
    <p v-if="description" class="text-sm text-ink-text-muted">{{ description }}</p>
    <div v-if="$slots.default" class="mt-2">
      <slot />
    </div>
  </div>
</template>
