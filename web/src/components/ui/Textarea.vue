<script setup lang="ts">
import { computed, useAttrs } from 'vue'
import { cn } from '@/lib/cn'

defineOptions({ inheritAttrs: false })

const props = withDefaults(
  defineProps<{
    modelValue?: string
    placeholder?: string
    disabled?: boolean
    rows?: number
    id?: string
  }>(),
  {
    modelValue: '',
    disabled: false,
    rows: 4,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const attrs = useAttrs()
const classes = computed(() => cn('ink-input resize-y', attrs.class as string))

function onInput(e: Event): void {
  emit('update:modelValue', (e.target as HTMLTextAreaElement).value)
}
</script>

<template>
  <textarea
    :id="id"
    :value="modelValue"
    :placeholder="placeholder"
    :disabled="disabled"
    :rows="rows"
    :class="classes"
    v-bind="{ ...attrs, class: undefined }"
    @input="onInput"
  />
</template>
