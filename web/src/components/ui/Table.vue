<script setup lang="ts" generic="T extends Record<string, unknown>">
import { cn } from '@/lib/cn'

export type TableColumn<T> = {
  key: string
  label: string
  class?: string
  render?: (row: T) => string
}

const props = defineProps<{
  columns: TableColumn<T>[]
  rows: T[]
  rowKey?: string | ((row: T) => string)
  class?: string
  emptyText?: string
}>()

function keyOf(row: T, index: number): string {
  if (typeof props.rowKey === 'function') return props.rowKey(row)
  if (typeof props.rowKey === 'string') return String(row[props.rowKey] ?? index)
  return String(index)
}

function cell(row: T, col: TableColumn<T>): string {
  if (col.render) return col.render(row)
  const v = row[col.key]
  if (v == null) return '—'
  return String(v)
}
</script>

<template>
  <div :class="cn('overflow-x-auto rounded-ink-md border border-ink-border', props.class)">
    <table class="w-full min-w-[480px] border-collapse text-left text-base">
      <thead class="bg-ink-surface-muted text-ink-text-secondary">
        <tr>
          <th
            v-for="col in columns"
            :key="col.key"
            :class="cn('px-3 py-2.5 font-medium', col.class)"
          >
            {{ col.label }}
          </th>
          <th v-if="$slots.actions" class="px-3 py-2.5 font-medium">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="rows.length === 0">
          <td
            :colspan="columns.length + ($slots.actions ? 1 : 0)"
            class="px-3 py-8 text-center text-ink-text-muted"
          >
            {{ emptyText ?? '暂无数据' }}
          </td>
        </tr>
        <tr
          v-for="(row, i) in rows"
          :key="keyOf(row, i)"
          class="border-t border-ink-border bg-ink-surface hover:bg-ink-paper-elevated/60"
        >
          <td v-for="col in columns" :key="col.key" :class="cn('px-3 py-2.5 text-ink-text', col.class)">
            <slot :name="`cell-${col.key}`" :row="row">{{ cell(row, col) }}</slot>
          </td>
          <td v-if="$slots.actions" class="px-3 py-2.5">
            <slot name="actions" :row="row" />
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
