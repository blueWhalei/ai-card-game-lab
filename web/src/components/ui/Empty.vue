<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { cn } from '@/lib/cn'

const props = defineProps<{
  title?: string
  description?: string
  class?: string
}>()

const { t } = useI18n()
const resolvedTitle = computed(() => props.title ?? t('common.noContent'))
</script>

<template>
  <div :class="cn('flex flex-col items-center justify-center gap-2 px-4 py-12 text-center', props.class)">
    <Icon icon="lucide:inbox" class="h-10 w-10 text-ink-text-muted opacity-60" />
    <p class="text-sm font-medium text-ink-text">{{ resolvedTitle }}</p>
    <p v-if="description" class="text-sm text-ink-text-secondary">{{ description }}</p>
    <div v-if="$slots.default" class="mt-2">
      <slot />
    </div>
  </div>
</template>
