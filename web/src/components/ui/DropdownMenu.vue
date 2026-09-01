<script setup lang="ts">
import {
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuPortal,
  DropdownMenuRoot,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from 'reka-ui'
import { cn } from '@/lib/cn'

export type DropdownMenuItemDef = {
  id: string
  label: string
  disabled?: boolean
  danger?: boolean
}

const props = withDefaults(
  defineProps<{
    items: DropdownMenuItemDef[]
    align?: 'start' | 'center' | 'end'
    contentClass?: string
  }>(),
  {
    align: 'end',
  },
)

const emit = defineEmits<{
  select: [id: string]
}>()
</script>

<template>
  <DropdownMenuRoot>
    <DropdownMenuTrigger as-child>
      <slot />
    </DropdownMenuTrigger>
    <DropdownMenuPortal>
      <DropdownMenuContent
        :align="align"
        :side-offset="4"
        :class="
          cn(
            'z-50 min-w-[10rem] overflow-hidden rounded-ink border border-ink-border bg-ink-surface p-1 shadow-[var(--ink-shadow-md)]',
            props.contentClass,
          )
        "
      >
        <template v-for="(item, index) in items" :key="item.id">
          <DropdownMenuSeparator
            v-if="index > 0 && item.danger && !items[index - 1]?.danger"
            class="my-1 h-px bg-ink-border"
          />
          <DropdownMenuItem
            :disabled="item.disabled"
            class="flex cursor-pointer items-center rounded-[6px] px-2.5 py-1.5 text-sm outline-none select-none data-[disabled]:pointer-events-none data-[highlighted]:bg-ink-surface-muted data-[disabled]:opacity-50"
            :class="item.danger ? 'text-ink-danger' : 'text-ink-text'"
            @select="emit('select', item.id)"
          >
            {{ item.label }}
          </DropdownMenuItem>
        </template>
      </DropdownMenuContent>
    </DropdownMenuPortal>
  </DropdownMenuRoot>
</template>
