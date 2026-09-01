<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import { cn } from '@/lib/cn'
import LocaleToggle from '@/components/common/LocaleToggle.vue'
import ThemeToggle from '@/components/common/ThemeToggle.vue'

const props = defineProps<{
  class?: string
}>()

const { t } = useI18n()
const route = useRoute()
</script>

<template>
  <div :class="cn('flex items-center gap-0.5', props.class)">
    <RouterLink
      to="/guide"
      class="inline-flex h-8 w-8 items-center justify-center rounded-ink text-ink-text-secondary transition-colors hover:bg-ink-surface-muted hover:text-ink-text"
      :class="route.path === '/guide' ? 'bg-ink-primary-muted text-ink-primary' : ''"
      :aria-label="t('guide.button')"
      :title="t('guide.button')"
    >
      <Icon icon="lucide:book-open" class="h-4 w-4" />
    </RouterLink>
    <LocaleToggle />
    <ThemeToggle />
  </div>
</template>
