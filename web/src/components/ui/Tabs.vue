<script setup lang="ts">
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from 'reka-ui'
import { cn } from '@/lib/cn'

export type TabItem = {
  value: string
  label: string
}

const props = defineProps<{
  modelValue: string
  tabs: TabItem[]
  class?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()
</script>

<template>
  <TabsRoot
    :model-value="modelValue"
    :class="cn('w-full', props.class)"
    @update:model-value="(v) => emit('update:modelValue', String(v))"
  >
    <TabsList class="inline-flex gap-0.5 rounded-ink bg-ink-surface-muted p-0.5">
      <TabsTrigger
        v-for="tab in tabs"
        :key="tab.value"
        :value="tab.value"
        class="rounded-[6px] px-3 py-1.5 text-base font-medium text-ink-text-muted transition-colors data-[state=active]:bg-ink-surface data-[state=active]:text-ink-text data-[state=active]:shadow-[var(--ink-shadow)]"
      >
        {{ tab.label }}
      </TabsTrigger>
    </TabsList>
    <slot />
  </TabsRoot>
</template>

<script lang="ts">
export { TabsContent }
</script>
