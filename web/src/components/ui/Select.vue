<script setup lang="ts">
import {
  SelectContent,
  SelectIcon,
  SelectItem,
  SelectItemIndicator,
  SelectItemText,
  SelectPortal,
  SelectRoot,
  SelectTrigger,
  SelectValue,
  SelectViewport,
} from 'reka-ui'
import { Icon } from '@iconify/vue'
import { cn } from '@/lib/cn'

export type SelectOption = {
  label: string
  value: string
  disabled?: boolean
}

const props = withDefaults(
  defineProps<{
    modelValue?: string
    options: SelectOption[]
    placeholder?: string
    disabled?: boolean
    class?: string
  }>(),
  {
    modelValue: '',
    placeholder: '请选择',
    disabled: false,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

function onUpdate(v: string): void {
  emit('update:modelValue', v)
}
</script>

<template>
  <SelectRoot :model-value="modelValue || undefined" :disabled="disabled" @update:model-value="onUpdate">
    <SelectTrigger
      :class="
        cn(
          'ink-input flex h-10 items-center justify-between gap-2 text-left disabled:opacity-50',
          props.class,
        )
      "
    >
      <SelectValue :placeholder="placeholder" />
      <SelectIcon as-child>
        <Icon icon="lucide:chevron-down" class="h-4 w-4 shrink-0 text-ink-text-muted" />
      </SelectIcon>
    </SelectTrigger>
    <SelectPortal>
      <SelectContent
        class="z-50 min-w-[var(--reka-select-trigger-width)] overflow-hidden rounded-ink-md border border-ink-border bg-ink-surface shadow-[var(--ink-shadow-md)]"
        :side-offset="4"
        position="popper"
      >
        <SelectViewport class="max-h-60 p-1">
          <SelectItem
            v-for="opt in options"
            :key="opt.value"
            :value="opt.value"
            :disabled="opt.disabled"
            class="relative flex cursor-pointer items-center rounded-[6px] py-2 pr-8 pl-2 text-base text-ink-text outline-none data-[highlighted]:bg-ink-primary-muted data-[disabled]:opacity-50"
          >
            <SelectItemText>{{ opt.label }}</SelectItemText>
            <SelectItemIndicator class="absolute right-2">
              <Icon icon="lucide:check" class="h-3.5 w-3.5 text-ink-primary" />
            </SelectItemIndicator>
          </SelectItem>
        </SelectViewport>
      </SelectContent>
    </SelectPortal>
  </SelectRoot>
</template>
