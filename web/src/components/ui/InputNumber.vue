<script setup lang="ts">
import { computed, useAttrs } from 'vue'
import { cn } from '@/lib/cn'

defineOptions({ inheritAttrs: false })

const props = withDefaults(
  defineProps<{
    modelValue?: number | null
    min?: number
    max?: number
    step?: number
    disabled?: boolean
    placeholder?: string
  }>(),
  {
    modelValue: null,
    min: undefined,
    max: undefined,
    step: 1,
    disabled: false,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: number | null]
}>()

const attrs = useAttrs()
const classes = computed(() => cn('ink-input', attrs.class as string))

function onInput(e: Event): void {
  const raw = (e.target as HTMLInputElement).value
  if (raw === '') {
    emit('update:modelValue', null)
    return
  }
  emit('update:modelValue', Number(raw))
}
</script>

<template>
  <input
    type="number"
    :value="modelValue ?? ''"
    :min="min"
    :max="max"
    :step="step"
    :disabled="disabled"
    :placeholder="placeholder"
    :class="classes"
    v-bind="{ ...attrs, class: undefined }"
    @input="onInput"
  />
</template>
