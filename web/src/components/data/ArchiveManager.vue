<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
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

const { t } = useI18n()
const stats = ref<ArchiveStats | null>(null)
const files = ref<ArchiveFile[]>([])
const loading = ref(false)
const daysOld = ref(30)
const dryRun = ref(true)

const fileColumns = computed(
  (): TableColumn<ArchiveFile>[] => [
    { key: 'filename', label: t('data.colFilename') },
    { key: 'size', label: t('data.colSize'), render: (row) => formatBytes(row.size_bytes) },
    { key: 'games_count', label: t('data.colGames') },
    { key: 'created_at', label: t('common.createdAt'), render: (row) => formatDateTime(row.created_at) },
  ],
)

async function refresh() {
  loading.value = true
  try {
    const [s, list] = await Promise.all([getArchiveStats(), listArchives()])
    stats.value = s
    files.value = list
  } catch (e: unknown) {
    showApiError(e, t('data.archiveFailed'))
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
        ? t('data.previewArchive', { n: result.archived_games })
        : t('data.archived', { n: result.archived_games, file: result.archive_file ?? '' }),
    )
    await refresh()
  } catch (e: unknown) {
    showApiError(e, t('data.doArchiveFailed'))
  }
}

async function handleCleanup() {
  const ok = await confirmDialog({
    title: t('data.confirmCleanup'),
    message: dryRun.value ? t('data.previewCleanupQ') : t('data.cleanupWarn'),
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
        ? t('data.previewDelete', { n: result.deleted_games })
        : t('data.deletedFreed', {
            n: result.deleted_games,
            bytes: formatBytes(result.freed_bytes),
          }),
    )
    await refresh()
  } catch (e: unknown) {
    showApiError(e, t('data.cleanupFailed'))
  }
}

async function handleDeleteFile(filename: string) {
  const ok = await confirmDialog({
    title: t('common.confirm'),
    message: t('data.deleteArchive', { name: filename }),
    danger: true,
  })
  if (!ok) return
  try {
    await deleteArchive(filename)
    toast.success(t('error.deleted'))
    await refresh()
  } catch (e: unknown) {
    showApiError(e, t('error.deleteFailed'))
  }
}
</script>

<template>
  <div class="relative space-y-6">
    <UiSpinner v-if="loading" overlay :label="t('common.loading')" />

    <div class="ink-card">
      <h3 class="mb-4 text-base font-semibold text-ink-text">{{ t('data.archiveStats') }}</h3>
      <div v-if="stats" class="grid grid-cols-2 gap-4 md:grid-cols-4">
        <div>
          <div class="text-xl font-semibold">{{ stats.total_games }}</div>
          <div class="text-xs text-ink-text-muted">{{ t('data.archivable') }}</div>
        </div>
        <div>
          <div class="text-xl font-semibold">{{ stats.archive_files }}</div>
          <div class="text-xs text-ink-text-muted">{{ t('data.archiveFiles') }}</div>
        </div>
        <div>
          <div class="text-xl font-semibold">{{ formatBytes(stats.archive_size_bytes) }}</div>
          <div class="text-xs text-ink-text-muted">{{ t('data.archiveSize') }}</div>
        </div>
        <div>
          <div class="text-xl font-semibold">{{ formatDateTime(stats.oldest_game) }}</div>
          <div class="text-xs text-ink-text-muted">{{ t('data.oldestGame') }}</div>
        </div>
      </div>
    </div>

    <div class="ink-card">
      <h3 class="mb-4 text-base font-semibold text-ink-text">{{ t('data.operations') }}</h3>
      <div class="mb-4 flex flex-wrap items-center gap-4">
        <div class="flex items-center gap-2">
          <span class="text-sm text-ink-text-muted">{{ t('data.dayThreshold') }}</span>
          <UiInputNumber v-model="daysOld" :min="1" :max="3650" />
        </div>
        <UiCheckbox v-model="dryRun" :label="t('data.dryRun')" />
        <UiButton @click="handleArchive">{{ t('data.archiveOld') }}</UiButton>
        <UiButton variant="danger" @click="handleCleanup">{{ t('data.cleanupOld') }}</UiButton>
      </div>
      <p class="text-xs text-ink-text-muted">{{ t('data.cleanupHint') }}</p>
    </div>

    <div class="ink-card">
      <h3 class="mb-4 text-base font-semibold text-ink-text">{{ t('data.archiveFilesTitle') }}</h3>
      <UiTable :columns="fileColumns" :rows="files" row-key="filename">
        <template #actions="{ row }">
          <UiButton size="sm" variant="danger" @click="handleDeleteFile(row.filename)">
            {{ t('common.delete') }}
          </UiButton>
        </template>
      </UiTable>
    </div>
  </div>
</template>
