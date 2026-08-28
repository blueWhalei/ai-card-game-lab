<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { toast } from '@/components/ui/toast'
import { confirmDialog } from '@/components/ui/confirm'
import { useDataStore } from '@/stores/useDataStore'
import type { CreateDatasetRequest, DatasetItem } from '@/api/dataApi'
import { showApiError } from '@/utils/error'
import { formatDateTime } from '@/utils/format'
import UiButton from '@/components/ui/Button.vue'
import UiDialog from '@/components/ui/Dialog.vue'
import UiInput from '@/components/ui/Input.vue'
import UiSelect from '@/components/ui/Select.vue'
import UiSpinner from '@/components/ui/Spinner.vue'
import UiTable from '@/components/ui/Table.vue'
import type { TableColumn } from '@/components/ui/Table.vue'

const store = useDataStore()
const showCreate = ref(false)
const form = ref<CreateDatasetRequest>({
  name: '',
  game_type: 'doudizhu',
  filters: {},
})

const columns: TableColumn<DatasetItem>[] = [
  { key: 'name', label: '名称' },
  { key: 'game_type', label: '游戏' },
  { key: 'sample_count', label: '样本数' },
  { key: 'created_at', label: '创建时间', render: (row) => formatDateTime(row.created_at) },
]

const gameTypeOptions = [{ label: '斗地主', value: 'doudizhu' }]

onMounted(async () => {
  try {
    await store.fetchDatasetsOnce()
  } catch (e: unknown) {
    showApiError(e, '加载数据集失败')
  }
})

async function handleCreate() {
  if (!form.value.name.trim()) {
    toast.warning('请输入数据集名称')
    return
  }
  try {
    await store.createDataset({
      ...form.value,
      name: form.value.name.trim(),
    })
    toast.success('数据集已创建')
    showCreate.value = false
    form.value = { name: '', game_type: 'doudizhu', filters: {} }
  } catch (e: unknown) {
    showApiError(e, '创建失败')
  }
}

async function handleDelete(id: string) {
  const ok = await confirmDialog({
    title: '删除数据集',
    message: '确定删除此数据集？文件也会一并删除。',
    danger: true,
  })
  if (!ok) return
  try {
    await store.deleteDataset(id)
    toast.success('已删除')
  } catch (e: unknown) {
    showApiError(e, '删除失败')
  }
}
</script>

<template>
  <div class="relative ink-card">
    <UiSpinner v-if="store.datasetsLoading" overlay />
    <div class="mb-4 flex items-center justify-between">
      <h3 class="text-base font-semibold text-ink-text">数据集</h3>
      <UiButton @click="showCreate = true">创建数据集</UiButton>
    </div>

    <UiTable :columns="columns" :rows="store.datasets" row-key="id">
      <template #actions="{ row }">
        <UiButton size="sm" variant="danger" @click="handleDelete(row.id)">删除</UiButton>
      </template>
    </UiTable>

    <UiDialog :open="showCreate" title="创建数据集" @update:open="(v) => (showCreate = v)">
      <div class="space-y-4">
        <label class="block space-y-1">
          <span class="ink-label">名称</span>
          <UiInput v-model="form.name" placeholder="如：斗地主-SFT-v1" />
        </label>
        <label class="block space-y-1">
          <span class="ink-label">游戏类型</span>
          <UiSelect v-model="form.game_type" :options="gameTypeOptions" />
        </label>
      </div>
      <template #footer>
        <UiButton variant="secondary" @click="showCreate = false">取消</UiButton>
        <UiButton @click="handleCreate">创建</UiButton>
      </template>
    </UiDialog>
  </div>
</template>
