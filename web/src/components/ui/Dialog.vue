<script setup lang="ts">
import {
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogOverlay,
  DialogPortal,
  DialogRoot,
  DialogTitle,
} from 'reka-ui'
import { Icon } from '@iconify/vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { cn } from '@/lib/cn'

const props = withDefaults(
  defineProps<{
    open?: boolean
    title?: string
    description?: string
    /** default 520px; lg 672px for create forms; wide 896px for archives */
    size?: 'default' | 'lg' | 'wide'
    class?: string
  }>(),
  {
    open: false,
    size: 'default',
  },
)

const emit = defineEmits<{
  'update:open': [value: boolean]
}>()

const { t } = useI18n()

const sizeClass = computed(() => {
  if (props.size === 'wide') return 'w-[min(94vw,56rem)]'
  if (props.size === 'lg') return 'w-[min(94vw,42rem)]'
  return 'w-[min(92vw,520px)]'
})
</script>

<template>
  <DialogRoot :open="open" @update:open="emit('update:open', $event)">
    <DialogPortal>
      <DialogOverlay class="ink-dialog-overlay fixed inset-0 z-50 bg-black/40" />
      <DialogContent
        :class="
          cn(
            'ink-dialog-content fixed top-1/2 left-1/2 z-50 max-h-[85vh] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-ink-md border border-ink-border bg-ink-surface p-ink-6 shadow-[var(--ink-shadow-md)] focus:outline-none',
            sizeClass,
            props.class,
          )
        "
      >
        <div class="mb-ink-4 flex items-start justify-between gap-ink-3">
          <div>
            <DialogTitle v-if="title" class="text-title font-semibold text-ink-text">
              {{ title }}
            </DialogTitle>
            <DialogDescription v-if="description" class="mt-ink-1 text-caption text-ink-text-secondary">
              {{ description }}
            </DialogDescription>
          </div>
          <DialogClose
            class="rounded-ink p-1 text-ink-text-secondary hover:bg-ink-surface-muted hover:text-ink-text"
            :aria-label="t('common.close')"
          >
            <Icon icon="lucide:x" class="h-4 w-4" />
          </DialogClose>
        </div>
        <slot />
        <div v-if="$slots.footer" class="mt-ink-6 flex justify-end gap-ink-2 border-t border-ink-border pt-ink-4">
          <slot name="footer" />
        </div>
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>
