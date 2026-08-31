<script setup lang="ts">
import { computed, ref, useAttrs } from 'vue'
import { cn } from '@/lib/cn'
import { useFieldWidth } from '@/composables/useFieldWidth'
import { hasExplicitWidth, INPUT_CHROME_PX } from '@/utils/fieldWidth'

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
const inputRef = ref<HTMLInputElement | null>(null)
const autoEnabled = computed(
  () => Boolean(props.placeholder) && !hasExplicitWidth(attrs.class),
)
const { style: autoStyle } = useFieldWidth({
  enabled: () => autoEnabled.value,
  texts: () => [props.placeholder ?? '', String(props.modelValue ?? '')],
  chromePx: INPUT_CHROME_PX,
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
  emit('update:modelValue', (e.target as HTMLInputElement).value)
}
</script>

<template>
  <input
    :id="id"
    ref="inputRef"
    :type="type"
    :value="modelValue"
    :placeholder="placeholder"
    :disabled="disabled"
    :class="classes"
    :style="mergedStyle"
    v-bind="{ ...attrs, class: undefined, style: undefined }"
    @input="onInput"
  />
</template>
