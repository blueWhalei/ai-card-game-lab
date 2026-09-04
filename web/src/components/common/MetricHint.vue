<script setup lang="ts">
import { PopoverContent, PopoverPortal, PopoverRoot, PopoverTrigger } from 'reka-ui'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'
import { Icon } from '@iconify/vue'

defineProps<{
  plain: string
  formula?: string
}>()

const { t } = useI18n()
</script>

<template>
  <PopoverRoot>
    <PopoverTrigger as-child>
      <button
        type="button"
        class="inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold text-ink-text-muted hover:bg-ink-surface-muted hover:text-ink-text"
        :aria-label="t('metricHint.aria')"
        @click.stop
      >
        <Icon icon="lucide:circle-help" class="h-3.5 w-3.5" />
      </button>
    </PopoverTrigger>
    <PopoverPortal>
      <PopoverContent
        side="bottom"
        align="start"
        :side-offset="6"
        class="z-50 w-72 rounded-ink border border-ink-border bg-ink-surface p-3 text-left shadow-[var(--ink-shadow-md)]"
        @click.stop
      >
        <p class="text-sm leading-relaxed text-ink-text">{{ plain }}</p>
        <p v-if="formula" class="mt-1.5 text-xs leading-relaxed text-ink-text-secondary">
          {{ formula }}
        </p>
        <RouterLink
          :to="{ path: '/guide', hash: '#metrics' }"
          class="mt-2 inline-block text-xs text-ink-primary hover:underline"
        >
          {{ t('metricHint.moreInGuide') }}
        </RouterLink>
      </PopoverContent>
    </PopoverPortal>
  </PopoverRoot>
</template>
