<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { cn } from '@/lib/cn'
import { useLocale } from '@/composables/useLocale'

const props = withDefaults(
  defineProps<{
    class?: string
  }>(),
  {},
)

const { t } = useI18n()
const { locale, toggleLocale } = useLocale()

const nextLabel = computed(() =>
  locale.value === 'zh-CN' ? t('locale.switchToEn') : t('locale.switchToZh'),
)

const currentShort = computed(() => (locale.value === 'zh-CN' ? '中' : 'EN'))
</script>

<template>
  <button
    type="button"
    :class="
      cn(
        'inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-ink text-xs font-semibold tracking-wide text-ink-text-secondary transition-colors hover:bg-ink-surface-muted hover:text-ink-text',
        props.class,
      )
    "
    :aria-label="nextLabel"
    :title="nextLabel"
    @click="toggleLocale"
  >
    {{ currentShort }}
  </button>
</template>
