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
import { computed, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { cn } from '@/lib/cn'
import { useI18n } from 'vue-i18n'
import { localeRef } from '@/i18n'
import { useFieldWidth } from '@/composables/useFieldWidth'
import { hasExplicitWidth, SELECT_CHROME_PX } from '@/utils/fieldWidth'

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
    placeholder: undefined,
    disabled: false,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

function onUpdate(v: string | undefined): void {
  if (v === undefined) return
  emit('update:modelValue', v)
}

const { t } = useI18n()
const locale = localeRef()
const resolvedPlaceholder = computed(() => props.placeholder ?? t('common.select'))
const wrapRef = ref<HTMLElement | null>(null)
const fillWidth = computed(() => hasExplicitWidth(props.class))
const measureTexts = computed(() => [
  resolvedPlaceholder.value,
  ...props.options.map((opt) => opt.label),
])
const { style: autoStyle } = useFieldWidth({
  enabled: () => !fillWidth.value,
  texts: () => measureTexts.value,
  chromePx: SELECT_CHROME_PX,
  fontSource: wrapRef,
  className: () => props.class,
})
const wrapClass = computed(() =>
  fillWidth.value ? 'block w-full max-w-full' : 'inline-flex max-w-full align-middle',
)
</script>

<template>
  <div :key="locale" ref="wrapRef" :class="wrapClass" :style="autoStyle">
    <SelectRoot
      class="w-full"
      :model-value="modelValue || undefined"
      :disabled="disabled"
      @update:model-value="onUpdate"
    >
      <SelectTrigger
        :class="
          cn(
            'ink-input flex w-full items-center justify-between gap-2 whitespace-nowrap disabled:opacity-50',
            props.class,
            'h-10 min-w-0 py-0 leading-none',
          )
        "
      >
        <SelectValue
          :placeholder="resolvedPlaceholder"
          class="flex min-h-0 min-w-0 flex-1 items-center justify-center truncate leading-none [&[data-placeholder]]:text-ink-text-secondary [&>span]:flex [&>span]:w-full [&>span]:items-center [&>span]:justify-center"
        />
        <SelectIcon as-child>
          <Icon icon="lucide:chevron-down" class="h-4 w-4 shrink-0 text-ink-text-secondary" />
        </SelectIcon>
      </SelectTrigger>
      <SelectPortal>
        <SelectContent
          class="z-50 min-w-[var(--reka-select-trigger-width)] w-max max-w-[min(24rem,calc(100vw-2rem))] overflow-hidden rounded-ink-md border border-ink-border bg-ink-surface shadow-[var(--ink-shadow-md)]"
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
  </div>
</template>
