<script setup lang="ts">
import { SwitchRoot, SwitchThumb } from 'reka-ui'
import { cn } from '@/lib/cn'

const props = withDefaults(
  defineProps<{
    modelValue?: boolean
    disabled?: boolean
    id?: string
    class?: string
  }>(),
  {
    modelValue: false,
    disabled: false,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

function onUpdate(v: boolean): void {
  emit('update:modelValue', v === true)
}
</script>

<template>
  <SwitchRoot
    :id="id"
    :model-value="modelValue"
    :true-value="true"
    :false-value="false"
    :disabled="disabled"
    :class="
      cn(
        'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border border-transparent transition-colors data-[state=checked]:bg-ink-primary data-[state=unchecked]:bg-ink-surface-muted disabled:opacity-50',
        props.class,
      )
    "
    @update:model-value="onUpdate"
  >
    <SwitchThumb
      class="pointer-events-none block h-4 w-4 translate-x-0.5 rounded-full bg-ink-surface shadow-[var(--ink-shadow)] transition-transform data-[state=checked]:translate-x-[18px]"
    />
  </SwitchRoot>
</template>
