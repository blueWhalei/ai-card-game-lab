<script setup lang="ts">
import { computed } from 'vue'
import Button from './Button.vue'
import { cn } from '@/lib/cn'

const props = withDefaults(
  defineProps<{
    page: number
    pageSize: number
    total: number
    class?: string
  }>(),
  {},
)

const emit = defineEmits<{
  'update:page': [page: number]
}>()

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))

function go(p: number): void {
  const next = Math.min(totalPages.value, Math.max(1, p))
  if (next !== props.page) emit('update:page', next)
}
</script>

<template>
  <div :class="cn('flex items-center justify-end gap-2 text-base text-ink-text-muted', props.class)">
    <span>共 {{ total }} 条</span>
    <Button variant="secondary" size="sm" :disabled="page <= 1" @click="go(page - 1)">上一页</Button>
    <span class="min-w-16 text-center text-ink-text">{{ page }} / {{ totalPages }}</span>
    <Button
      variant="secondary"
      size="sm"
      :disabled="page >= totalPages"
      @click="go(page + 1)"
    >
      下一页
    </Button>
  </div>
</template>
