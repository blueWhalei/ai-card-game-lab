<script setup lang="ts">
import { computed, useId } from 'vue'
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

/** Do not nest CheckboxRoot (button) inside <label> — browsers double-toggle. */
const autoId = useId()
const inputId = computed(() => props.id ?? autoId)

/** Reka defaults trueValue/falseValue via factories that can leak as functions — pin booleans. */
function onUpdate(v: boolean | 'indeterminate'): void {
  emit('update:modelValue', v === true)
}
</script>

<template>
  <div
    :class="
      cn(
        'inline-flex items-center gap-2 text-sm text-ink-text',
        disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer',
        props.class,
      )
    "
  >
    <CheckboxRoot
      :id="inputId"
      :model-value="modelValue"
      :true-value="true"
      :false-value="false"
      :disabled="disabled"
      class="flex h-4 w-4 shrink-0 items-center justify-center rounded-[4px] border border-ink-border-strong bg-ink-surface data-[state=checked]:border-ink-primary data-[state=checked]:bg-ink-primary"
      @update:model-value="onUpdate"
    >
      <CheckboxIndicator>
        <Icon icon="lucide:check" class="h-3 w-3 text-[var(--ink-primary-fg)]" />
      </CheckboxIndicator>
    </CheckboxRoot>
    <label v-if="label || $slots.default" :for="inputId" class="cursor-inherit">
      <slot>{{ label }}</slot>
    </label>
  </div>
</template>
