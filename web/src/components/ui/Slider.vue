<script setup lang="ts">
import { cn } from '@/lib/cn'

const props = withDefaults(
  defineProps<{
    modelValue?: number
    min?: number
    max?: number
    step?: number
    disabled?: boolean
    class?: string
  }>(),
  {
    modelValue: 0,
    min: 0,
    max: 100,
    step: 1,
    disabled: false,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: number]
}>()
</script>

<template>
  <input
    type="range"
    :min="min"
    :max="max"
    :step="step"
    :value="modelValue"
    :disabled="disabled"
    :class="cn('h-2 w-full cursor-pointer accent-[var(--ink-primary)]', props.class)"
    @input="emit('update:modelValue', Number(($event.target as HTMLInputElement).value))"
  />
</template>
