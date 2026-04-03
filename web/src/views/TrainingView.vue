<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { showApiError } from '@/utils/error'
import { useTrainingStore } from '@/stores/useTrainingStore'
import { dataApi } from '@/api/dataApi'
import type { DatasetItem } from '@/api/dataApi'
import { TRAINING_STATUS_MAP } from '@/utils/constants'
import { formatDateTime } from '@/utils/format'

const store = useTrainingStore()
const datasets = ref<DatasetItem[]>([])
const showCreateDialog = ref(false)
const activeTab = ref<'tasks' | 'models'>('tasks')
let pollTimer: ReturnType<typeof setInterval> | null = null

const createForm = ref({
  name: '',
  dataset_id: '',
  base_model: 'Qwen/Qwen2.5-1.5B',
  training_type: 'sft',
  learning_rate: 2e-5,
  batch_size: 8,
  num_epochs: 3,
})

async function fetchDatasets() {
  try {
    const res = await dataApi.listDatasets()
    datasets.value = res.data
  } catch { /* ignore */ }
}

function openCreateDialog() {
  createForm.value = {
    name: '',
    dataset_id: '',
    base_model: 'Qwen/Qwen2.5-1.5B',
    training_type: 'sft',
    learning_rate: 2e-5,
    batch_size: 8,
    num_epochs: 3,
  }
  showCreateDialog.value = true
  fetchDatasets()
}
async function handleCreate() {
  if (!createForm.value.name.trim()) {
    ElMessage.warning('请输入任务名称')
    return
  }
  if (!createForm.value.dataset_id) {
    ElMessage.warning('请选择数据集')
    return
  }
  try {
    await store.createTask({
      name: createForm.value.name,
      dataset_id: createForm.value.dataset_id,
      base_model: createForm.value.base_model,
      training_type: createForm.value.training_type,
      config: {
        learning_rate: createForm.value.learning_rate,
        batch_size: createForm.value.batch_size,
        num_epochs: createForm.value.num_epochs,
        output_format: 'pytorch',
      },
    })
    ElMessage.success('训练任务已创建')
    showCreateDialog.value = false
  } catch (e: unknown) {
    showApiError(e, '创建失败')
  }
}

async function handleDeleteTask(id: string) {
  try {
    await ElMessageBox.confirm('确定删除此训练任务？', '确认')
    await store.deleteTask(id)
    ElMessage.success('已删除')
  } catch { /* cancelled */ }
}

async function handleDeleteModel(id: string) {
  try {
    await ElMessageBox.confirm('确定删除此模型？', '确认')
    await store.deleteModel(id)
    ElMessage.success('已删除')
  } catch { /* cancelled */ }
}

function formatProgress(p: number): string {
  return `${Math.round(p * 100)}%`
}

function startPolling() {
  pollTimer = setInterval(async () => {
    const hasRunning = store.tasks.some((t) =>
      ['pending', 'exporting', 'training'].includes(t.status),
    )
    if (hasRunning) {
      await store.fetchTasks()
    }
  }, 3000)
}

onMounted(() => {
  store.fetchTasks()
  store.fetchModels()
  startPolling()
})

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})
</script>

<template>
  <div class="page-container">
    <div class="mb-8 flex items-center justify-between">
      <h2 class="page-title">训练控制台</h2>
      <button class="apple-btn" @click="openCreateDialog">创建训练任务</button>
    </div>

    <!-- Segmented Control -->
    <div class="mb-6">
      <div class="apple-segmented">
        <button
          :class="activeTab === 'tasks' ? 'apple-segmented-item-active' : 'apple-segmented-item'"
          @click="activeTab = 'tasks'"
        >
          训练任务
        </button>
        <button
          :class="activeTab === 'models' ? 'apple-segmented-item-active' : 'apple-segmented-item'"
          @click="activeTab = 'models'; store.fetchModels()"
        >
          模型仓库
        </button>
      </div>
    </div>

    <!-- Tasks Tab -->
    <div v-if="activeTab === 'tasks'" class="apple-card">
      <el-table v-loading="store.isLoading" :data="store.tasks">
        <el-table-column prop="name" label="任务名称" min-width="150" />
        <el-table-column prop="base_model" label="基座模型" width="200">
          <template #default="{ row }">
            <span class="font-mono text-xs">{{ row.base_model }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag
              size="small"
              :type="(TRAINING_STATUS_MAP[row.status]?.type as 'success' | 'warning' | 'danger' | 'info' | '') || 'info'"
            >
              {{ TRAINING_STATUS_MAP[row.status]?.label || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="160">
          <template #default="{ row }">
            <el-progress
              v-if="['exporting', 'training'].includes(row.status)"
              :percentage="Math.round(row.progress * 100)"
              :stroke-width="8"
              :text-inside="true"
            />
            <span v-else-if="row.status === 'completed'" class="text-sm text-green-600">
              {{ formatProgress(row.progress) }}
            </span>
            <span v-else class="text-sm text-gray-400">-</span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button type="danger" text size="small" @click="handleDeleteTask(row.id)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
    <!-- Models Tab -->
    <div v-if="activeTab === 'models'">
      <div v-if="store.models.length === 0" class="py-16 text-center text-[#86868b]">
        暂无训练产出模型
      </div>
      <div v-else class="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
        <div v-for="m in store.models" :key="m.id" class="apple-card-hover">
          <div class="mb-2 text-sm font-semibold text-[#1d1d1f]">{{ m.name }}</div>
          <div class="mb-1 text-xs text-[#86868b]">
            基座: <span class="font-mono">{{ m.base_model }}</span>
          </div>
          <div class="mb-3 text-xs text-[#aeaeb2]">{{ formatDateTime(m.created_at) }}</div>
          <button class="rounded-full px-4 py-1.5 text-xs font-medium text-[#ff3b30] transition-all hover:bg-red-50" @click="handleDeleteModel(m.id)">
            删除
          </button>
        </div>
      </div>
    </div>

    <!-- Create Dialog -->
    <el-dialog v-model="showCreateDialog" title="创建训练任务" width="550px" destroy-on-close>
      <el-form :model="createForm" label-position="top">
        <el-form-item label="任务名称" required>
          <el-input v-model="createForm.name" placeholder="如：斗地主SFT-v1" />
        </el-form-item>
        <el-form-item label="数据集" required>
          <el-select v-model="createForm.dataset_id" placeholder="选择数据集" style="width: 100%">
            <el-option
              v-for="ds in datasets"
              :key="ds.id"
              :label="`${ds.name} (${ds.sample_count} 条)`"
              :value="ds.id"
            />
          </el-select>
          <div v-if="datasets.length === 0" class="mt-1 text-xs text-orange-500">
            暂无数据集，请先在「数据看板」创建
          </div>
        </el-form-item>
        <el-form-item label="基座模型">
          <el-select v-model="createForm.base_model" style="width: 100%">
            <el-option label="Qwen2.5-1.5B" value="Qwen/Qwen2.5-1.5B" />
            <el-option label="Qwen2.5-7B" value="Qwen/Qwen2.5-7B" />
            <el-option label="Llama-3.2-3B" value="meta-llama/Llama-3.2-3B" />
          </el-select>
        </el-form-item>
        <el-form-item label="训练超参">
          <div class="grid grid-cols-3 gap-3">
            <div>
              <div class="mb-1 text-xs text-gray-500">学习率</div>
              <el-input-number v-model="createForm.learning_rate" :min="1e-6" :max="1e-3" :step="1e-5" :precision="6" size="small" controls-position="right" />
            </div>
            <div>
              <div class="mb-1 text-xs text-gray-500">Batch Size</div>
              <el-input-number v-model="createForm.batch_size" :min="1" :max="64" size="small" controls-position="right" />
            </div>
            <div>
              <div class="mb-1 text-xs text-gray-500">Epochs</div>
              <el-input-number v-model="createForm.num_epochs" :min="1" :max="20" size="small" controls-position="right" />
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>
