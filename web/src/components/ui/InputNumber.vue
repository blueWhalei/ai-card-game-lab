<script setup lang="ts">
import { computed, ref, useAttrs } from 'vue'
import { cn } from '@/lib/cn'
import { useFieldWidth } from '@/composables/useFieldWidth'
import { hasExplicitWidth, INPUT_CHROME_PX, NUMBER_EXTRA_PX } from '@/utils/fieldWidth'

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
const inputRef = ref<HTMLInputElement | null>(null)
const autoEnabled = computed(() => !hasExplicitWidth(attrs.class))
const { style: autoStyle } = useFieldWidth({
  enabled: () => autoEnabled.value,
  texts: () => [
    props.placeholder ?? '',
    props.modelValue != null ? String(props.modelValue) : '',
    props.max != null ? String(props.max) : '',
    props.min != null ? String(props.min) : '',
    '0',
  ],
  chromePx: INPUT_CHROME_PX + NUMBER_EXTRA_PX,
  fontSource: inputRef,
  className: () => attrs.class,
})
const classes = computed(() =>
  cn('ink-input', attrs.class as string, 'h-10 py-0', autoEnabled.value ? 'w-auto' : undefined),
)
const mergedStyle = computed(() => {
  const fromAttrs = attrs.style
  const auto = autoStyle.value
  if (!auto) return fromAttrs
  if (!fromAttrs) return auto
  return [fromAttrs, auto]
})

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
    ref="inputRef"
    type="number"
    :value="modelValue ?? ''"
    :min="min"
    :max="max"
    :step="step"
    :disabled="disabled"
    :placeholder="placeholder"
    :class="classes"
    :style="mergedStyle"
    v-bind="{ ...attrs, class: undefined, style: undefined }"
    @input="onInput"
  />
</template>
