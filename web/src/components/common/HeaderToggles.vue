<script setup lang="ts">
import { cn } from '@/lib/cn'
import LocaleToggle from '@/components/common/LocaleToggle.vue'
import ThemeToggle from '@/components/common/ThemeToggle.vue'

const props = defineProps<{
  class?: string
}>()
</script>

<template>
  <div :class="cn('flex items-center gap-0.5', props.class)">
    <LocaleToggle />
    <ThemeToggle />
  </div>
</template>
