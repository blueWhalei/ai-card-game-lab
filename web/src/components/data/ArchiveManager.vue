<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { toast } from '@/components/ui/toast'
import { confirmDialog } from '@/components/ui/confirm'
import {
  archiveOldGames,
  cleanupOldData,
  deleteArchive,
  getArchiveStats,
  listArchives,
  type ArchiveFile,
  type ArchiveStats,
} from '@/api/archive'
import { formatBytes, formatDateTime } from '@/utils/format'
import { showApiError } from '@/utils/error'
import UiButton from '@/components/ui/Button.vue'
import UiCheckbox from '@/components/ui/Checkbox.vue'
import UiInputNumber from '@/components/ui/InputNumber.vue'
import UiSpinner from '@/components/ui/Spinner.vue'
import UiTable from '@/components/ui/Table.vue'
import type { TableColumn } from '@/components/ui/Table.vue'

const stats = ref<ArchiveStats | null>(null)
const files = ref<ArchiveFile[]>([])
const loading = ref(false)
const daysOld = ref(30)
const dryRun = ref(true)

const fileColumns: TableColumn<ArchiveFile>[] = [
  { key: 'filename', label: '文件名' },
  { key: 'size', label: '大小', render: (row) => formatBytes(row.size_bytes) },
  { key: 'games_count', label: '对局数' },
  { key: 'created_at', label: '创建时间', render: (row) => formatDateTime(row.created_at) },
]

async function refresh() {
  loading.value = true
  try {
    const [s, list] = await Promise.all([getArchiveStats(), listArchives()])
    stats.value = s
    files.value = list
  } catch (e: unknown) {
    showApiError(e, '加载归档信息失败')
  } finally {
    loading.value = false
  }
}

onMounted(refresh)

async function handleArchive() {
  try {
    const result = await archiveOldGames({
      days_old: daysOld.value,
      dry_run: dryRun.value,
    })
    toast.success(
      dryRun.value
        ? `预览：可归档 ${result.archived_games} 局`
        : `已归档 ${result.archived_games} 局 → ${result.archive_file ?? ''}`,
    )
    await refresh()
  } catch (e: unknown) {
    showApiError(e, '归档失败')
  }
}

async function handleCleanup() {
  const ok = await confirmDialog({
    title: '确认清理',
    message: dryRun.value ? '预览清理结果？' : '将永久删除旧数据，不可恢复。继续？',
    danger: !dryRun.value,
  })
  if (!ok) return
  try {
    const result = await cleanupOldData({
      days_old: Math.max(daysOld.value, 90),
      dry_run: dryRun.value,
    })
    toast.success(
      dryRun.value
        ? `预览：可删除 ${result.deleted_games} 局`
        : `已删除 ${result.deleted_games} 局，释放 ${formatBytes(result.freed_bytes)}`,
    )
    await refresh()
  } catch (e: unknown) {
    showApiError(e, '清理失败')
  }
}

async function handleDeleteFile(filename: string) {
  const ok = await confirmDialog({
    title: '确认',
    message: `删除归档文件 ${filename}？`,
    danger: true,
  })
  if (!ok) return
  try {
    await deleteArchive(filename)
    toast.success('已删除')
    await refresh()
  } catch (e: unknown) {
    showApiError(e, '删除失败')
  }
}
</script>

<template>
  <div class="relative space-y-6">
    <UiSpinner v-if="loading" overlay />

    <div class="ink-card">
      <h3 class="mb-4 text-base font-semibold text-ink-text">归档统计</h3>
      <div v-if="stats" class="grid grid-cols-2 gap-4 md:grid-cols-4">
        <div>
          <div class="text-xl font-semibold">{{ stats.total_games }}</div>
          <div class="text-xs text-ink-text-muted">可归档对局</div>
        </div>
        <div>
          <div class="text-xl font-semibold">{{ stats.archive_files }}</div>
          <div class="text-xs text-ink-text-muted">归档文件数</div>
        </div>
        <div>
          <div class="text-xl font-semibold">{{ formatBytes(stats.archive_size_bytes) }}</div>
          <div class="text-xs text-ink-text-muted">归档体积</div>
        </div>
        <div>
          <div class="text-xl font-semibold">{{ formatDateTime(stats.oldest_game) }}</div>
          <div class="text-xs text-ink-text-muted">最早对局</div>
        </div>
      </div>
    </div>

    <div class="ink-card">
      <h3 class="mb-4 text-base font-semibold text-ink-text">操作</h3>
      <div class="mb-4 flex flex-wrap items-center gap-4">
        <div class="flex items-center gap-2">
          <span class="text-sm text-ink-text-muted">天数阈值</span>
          <UiInputNumber v-model="daysOld" :min="1" :max="3650" class="w-28" />
        </div>
        <UiCheckbox v-model="dryRun" label="仅预览（dry run）" />
        <UiButton @click="handleArchive">归档旧对局</UiButton>
        <UiButton variant="danger" @click="handleCleanup">清理旧数据</UiButton>
      </div>
      <p class="text-xs text-ink-text-muted">清理默认至少 90 天；生产环境请先 dry run。</p>
    </div>

    <div class="ink-card">
      <h3 class="mb-4 text-base font-semibold text-ink-text">归档文件</h3>
      <UiTable :columns="fileColumns" :rows="files" row-key="filename">
        <template #actions="{ row }">
          <UiButton size="sm" variant="danger" @click="handleDeleteFile(row.filename)">
            删除
          </UiButton>
        </template>
      </UiTable>
    </div>
  </div>
</template>
