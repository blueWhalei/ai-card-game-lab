<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import Button from './Button.vue'
import Select from './Select.vue'
import type { SelectOption } from './Select.vue'
import { cn } from '@/lib/cn'
import { PAGE_SIZE_OPTIONS, parsePageSize } from '@/utils/pagination'

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
  'update:pageSize': [pageSize: number]
}>()

const { t } = useI18n()

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))

const pageSizeOptions: SelectOption[] = PAGE_SIZE_OPTIONS.map((n) => ({
  label: String(n),
  value: String(n),
}))

function go(p: number): void {
  const next = Math.min(totalPages.value, Math.max(1, p))
  if (next !== props.page) emit('update:page', next)
}

function onPageSize(v: string): void {
  const next = parsePageSize(v)
  if (next !== props.pageSize) emit('update:pageSize', next)
}
</script>

<template>
  <div
    :class="
      cn('flex flex-wrap items-center justify-end gap-2 text-sm text-ink-text-secondary', props.class)
    "
  >
    <label class="flex items-center gap-1.5">
      <span>{{ t('common.pageSize') }}</span>
      <Select
        :model-value="String(pageSize)"
        :options="pageSizeOptions"
        class="text-sm"
        :placeholder="t('common.pageSizePlaceholder')"
        @update:model-value="onPageSize"
      />
      <span v-if="t('common.pageSizeUnit')">{{ t('common.pageSizeUnit') }}</span>
    </label>
    <span>{{ t('common.totalItems', { n: total }) }}</span>
    <Button variant="secondary" size="sm" :disabled="page <= 1" @click="go(page - 1)">
      {{ t('common.prevPage') }}
    </Button>
    <span class="min-w-16 text-center text-ink-text">{{ page }} / {{ totalPages }}</span>
    <Button
      variant="secondary"
      size="sm"
      :disabled="page >= totalPages"
      @click="go(page + 1)"
    >
      {{ t('common.nextPage') }}
    </Button>
  </div>
</template>
