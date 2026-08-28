<script setup lang="ts">
import { cn } from '@/lib/cn'

export type RadioOption = {
  label: string
  value: string
}

const props = defineProps<{
  modelValue?: string
  options: RadioOption[]
  name?: string
  disabled?: boolean
  class?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()
</script>

<template>
  <div :class="cn('flex flex-wrap gap-3', props.class)" role="radiogroup">
    <label
      v-for="opt in options"
      :key="opt.value"
      class="inline-flex cursor-pointer items-center gap-2 text-base text-ink-text"
    >
      <input
        type="radio"
        class="h-4 w-4 accent-[var(--ink-primary)]"
        :name="name"
        :value="opt.value"
        :checked="modelValue === opt.value"
        :disabled="disabled"
        @change="emit('update:modelValue', opt.value)"
      />
      {{ opt.label }}
    </label>
  </div>
</template>
