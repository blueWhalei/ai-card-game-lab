<script setup lang="ts">
import { computed, useAttrs } from 'vue'
import { buttonVariants, type ButtonVariants } from './buttonVariants'
import { cn } from '@/lib/cn'

defineOptions({ inheritAttrs: false })

const props = withDefaults(
  defineProps<{
    variant?: ButtonVariants['variant']
    size?: ButtonVariants['size']
    type?: 'button' | 'submit' | 'reset'
    disabled?: boolean
    loading?: boolean
  }>(),
  {
    variant: 'primary',
    size: 'md',
    type: 'button',
    disabled: false,
    loading: false,
  },
)

const attrs = useAttrs()
const classes = computed(() =>
  cn(buttonVariants({ variant: props.variant, size: props.size }), attrs.class as string),
)
</script>

<template>
  <button
    :type="type"
    :disabled="disabled || loading"
    :class="classes"
    v-bind="{ ...attrs, class: undefined }"
  >
    <span
      v-if="loading"
      class="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent"
    />
    <slot />
  </button>
</template>
