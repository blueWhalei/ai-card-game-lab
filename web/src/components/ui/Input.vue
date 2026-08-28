<script setup lang="ts">
import { computed, useAttrs } from 'vue'
import { cn } from '@/lib/cn'

defineOptions({ inheritAttrs: false })

const props = withDefaults(
  defineProps<{
    modelValue?: string | number
    type?: string
    placeholder?: string
    disabled?: boolean
    id?: string
  }>(),
  {
    modelValue: '',
    type: 'text',
    disabled: false,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const attrs = useAttrs()
const classes = computed(() => cn('ink-input', attrs.class as string))

function onInput(e: Event): void {
  emit('update:modelValue', (e.target as HTMLInputElement).value)
}
</script>

<template>
  <input
    :id="id"
    :type="type"
    :value="modelValue"
    :placeholder="placeholder"
    :disabled="disabled"
    :class="classes"
    v-bind="{ ...attrs, class: undefined }"
    @input="onInput"
  />
</template>
