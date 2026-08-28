<script setup lang="ts">
import { CheckboxIndicator, CheckboxRoot } from 'reka-ui'
import { Icon } from '@iconify/vue'
import { cn } from '@/lib/cn'

const props = withDefaults(
  defineProps<{
    modelValue?: boolean
    disabled?: boolean
    id?: string
    label?: string
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
</script>

<template>
  <label :class="cn('inline-flex cursor-pointer items-center gap-2 text-sm text-ink-text', props.class)">
    <CheckboxRoot
      :id="id"
      :checked="modelValue"
      :disabled="disabled"
      class="flex h-4 w-4 shrink-0 items-center justify-center rounded-[4px] border border-ink-border-strong bg-ink-surface data-[state=checked]:border-ink-primary data-[state=checked]:bg-ink-primary"
      @update:checked="(v: boolean | 'indeterminate') => emit('update:modelValue', v === true)"
    >
      <CheckboxIndicator>
        <Icon icon="lucide:check" class="h-3 w-3 text-[var(--ink-primary-fg)]" />
      </CheckboxIndicator>
    </CheckboxRoot>
    <span v-if="label || $slots.default"><slot>{{ label }}</slot></span>
  </label>
</template>
