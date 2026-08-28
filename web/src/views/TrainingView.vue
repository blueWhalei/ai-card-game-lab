<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { toast } from '@/components/ui/toast'
import { confirmDialog } from '@/components/ui/confirm'
import { showApiError } from '@/utils/error'
import { useTrainingStore } from '@/stores/useTrainingStore'
import { dataApi } from '@/api/dataApi'
import type { DatasetItem } from '@/api/dataApi'
import { TRAINING_STATUS_MAP } from '@/utils/constants'
import { formatDateTime } from '@/utils/format'
import UiButton from '@/components/ui/Button.vue'
import UiDialog from '@/components/ui/Dialog.vue'
import UiInput from '@/components/ui/Input.vue'
import UiSelect from '@/components/ui/Select.vue'
import UiInputNumber from '@/components/ui/InputNumber.vue'
import UiCheckbox from '@/components/ui/Checkbox.vue'
import UiBadge from '@/components/ui/Badge.vue'
import UiProgress from '@/components/ui/Progress.vue'
import UiSpinner from '@/components/ui/Spinner.vue'
import UiEmpty from '@/components/ui/Empty.vue'
import UiTable from '@/components/ui/Table.vue'
import type { TableColumn } from '@/components/ui/Table.vue'
import { systemApi } from '@/api/systemApi'

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
  batch_size: 1,
  num_epochs: 1,
  use_mock: true,
  lora_r: 8,
})

const baseModelOptions = ref([
  { label: 'Qwen2.5-1.5B', value: 'Qwen/Qwen2.5-1.5B' },
  { label: 'Qwen2.5-7B', value: 'Qwen/Qwen2.5-7B' },
  { label: 'Llama-3.2-3B', value: 'meta-llama/Llama-3.2-3B' },
])

const datasetOptions = computed(() =>
  datasets.value.map((ds) => ({
    label: `${ds.name} (${ds.sample_count} 条)`,
    value: ds.id,
  })),
)

type TaskRow = (typeof store.tasks)[number] & Record<string, unknown>

const taskColumns: TableColumn<TaskRow>[] = [
  { key: 'name', label: '任务名称' },
  { key: 'base_model', label: '基座模型', class: 'w-48' },
  { key: 'status', label: '状态', class: 'w-40' },
  { key: 'progress', label: '进度', class: 'w-40' },
  { key: 'created_at', label: '创建时间', class: 'w-44' },
]

const taskRows = computed(() => store.tasks as TaskRow[])

function statusVariant(status: string): 'muted' | 'success' | 'warning' | 'danger' | 'default' {
  const type = TRAINING_STATUS_MAP[status]?.type
  if (type === 'success') return 'success'
  if (type === 'warning') return 'warning'
  if (type === 'danger') return 'danger'
  if (type === 'info' || type === '') return type === '' ? 'default' : 'muted'
  return 'muted'
}

async function fetchDatasets() {
  try {
    const res = await dataApi.listDatasets()
    datasets.value = res.data
  } catch {
    /* ignore */
  }
}

function openCreateDialog() {
  createForm.value = {
    name: '',
    dataset_id: '',
    base_model: 'Qwen/Qwen2.5-1.5B',
    training_type: 'sft',
    learning_rate: 2e-5,
    batch_size: 1,
    num_epochs: 1,
    use_mock: true,
    lora_r: 8,
  }
  showCreateDialog.value = true
  fetchDatasets()
}

async function handleCreate() {
  if (!createForm.value.name.trim()) {
    toast.warning('请输入任务名称')
    return
  }
  if (!createForm.value.dataset_id) {
    toast.warning('请选择数据集')
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
        use_mock: createForm.value.use_mock,
        lora_r: createForm.value.lora_r,
      },
    })
    toast.success('训练任务已创建')
    showCreateDialog.value = false
  } catch (e: unknown) {
    showApiError(e, '创建失败')
  }
}

async function handleDeleteTask(id: string) {
  const ok = await confirmDialog({ message: '确定删除此训练任务？', title: '确认', danger: true })
  if (!ok) return
  try {
    await store.deleteTask(id)
    toast.success('已删除')
  } catch (e: unknown) {
    showApiError(e, '删除失败')
  }
}

async function handleDeleteModel(id: string) {
  const ok = await confirmDialog({ message: '确定删除此模型？', title: '确认', danger: true })
  if (!ok) return
  try {
    await store.deleteModel(id)
    toast.success('已删除')
  } catch (e: unknown) {
    showApiError(e, '删除失败')
  }
}

async function handleExportModel(id: string) {
  try {
    const result = await store.exportModel(id, { merge: true, try_create: false })
    const deployDir = String(result.deploy_dir ?? '')
    const tag = String(result.ollama_tag ?? '')
    const merged = result.merged === true
    toast.success(
      merged
        ? `已导出到 ${deployDir}（含 merged）。转 GGUF 后: ollama create ${tag} -f Modelfile`
        : `已导出脚本到 ${deployDir}。安装 training 依赖后可合并 LoRA；详见目录内 README`,
    )
  } catch (e: unknown) {
    showApiError(e, '导出失败（Mock 模型无法导出）')
  }
}

async function handleVerifyModel(id: string, runGame: boolean) {
  try {
    const result = await store.verifyModel(id, { run_game: runGame })
    if (result.ok) {
      const gameId = (result.game as { game_id?: string } | undefined)?.game_id
      toast.success(
        runGame && gameId ? `验证通过，测试对局 ${gameId}` : '决策冒烟验证通过',
      )
    } else {
      toast.warning(String(result.error || '验证未通过，请先完成 GGUF + ollama create'))
    }
  } catch (e: unknown) {
    showApiError(e, '验证失败')
  }
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

onMounted(async () => {
  try {
    const cfg = await systemApi.getConfig()
    const models = cfg.data.default_base_models
    if (models?.length) {
      baseModelOptions.value = models.map((m) => ({
        label: m.split('/').pop() || m,
        value: m,
      }))
      createForm.value.base_model = models[0] ?? createForm.value.base_model
    }
    if (typeof cfg.data.training_use_mock === 'boolean') {
      createForm.value.use_mock = cfg.data.training_use_mock
    }
  } catch {
    /* keep fallbacks */
  }
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
    <div class="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <p class="text-base text-ink-text-secondary">
        默认 Mock 演示；真实 LoRA 需先
        <code class="rounded bg-ink-surface-muted px-1.5 py-0.5 text-sm">poetry install --with training</code>
        并关闭「使用 Mock」。
      </p>
      <UiButton @click="openCreateDialog">创建训练任务</UiButton>
    </div>

    <div class="mb-6 flex gap-1 rounded-ink border border-ink-border bg-ink-surface-muted p-1 w-fit">
      <button
        type="button"
        class="rounded-[6px] px-4 py-2 text-base font-medium transition-colors"
        :class="
          activeTab === 'tasks'
            ? 'bg-ink-surface text-ink-text shadow-[var(--ink-shadow)]'
            : 'text-ink-text-muted hover:text-ink-text'
        "
        @click="activeTab = 'tasks'"
      >
        训练任务
      </button>
      <button
        type="button"
        class="rounded-[6px] px-4 py-2 text-base font-medium transition-colors"
        :class="
          activeTab === 'models'
            ? 'bg-ink-surface text-ink-text shadow-[var(--ink-shadow)]'
            : 'text-ink-text-muted hover:text-ink-text'
        "
        @click="activeTab = 'models'; store.fetchModels()"
      >
        模型仓库
      </button>
    </div>

    <div v-if="activeTab === 'tasks'" class="relative">
      <UiSpinner v-if="store.isLoading" overlay label="加载中…" />
      <UiTable :columns="taskColumns" :rows="taskRows" row-key="id">
        <template #cell-base_model="{ row }">
          <span class="font-mono text-xs">{{ row.base_model }}</span>
        </template>
        <template #cell-status="{ row }">
          <div class="flex flex-wrap items-center gap-1">
            <UiBadge :variant="statusVariant(String(row.status))">
              {{ TRAINING_STATUS_MAP[String(row.status)]?.label || row.status }}
            </UiBadge>
            <UiBadge v-if="row.result?.mock === true" variant="muted">Mock</UiBadge>
            <UiBadge
              v-else-if="row.status === 'completed' && row.result?.mock === false"
              variant="success"
            >
              LoRA
            </UiBadge>
          </div>
        </template>
        <template #cell-progress="{ row }">
          <UiProgress
            v-if="['exporting', 'training'].includes(String(row.status))"
            :value="Math.round(Number(row.progress) * 100)"
            class="mt-1"
          />
          <span v-else-if="row.status === 'completed'" class="text-sm text-ink-success">
            {{ formatProgress(Number(row.progress)) }}
          </span>
          <span v-else class="text-sm text-ink-text-muted">-</span>
        </template>
        <template #cell-created_at="{ row }">
          {{ formatDateTime(String(row.created_at)) }}
        </template>
        <template #actions="{ row }">
          <UiButton
            variant="ghost"
            size="sm"
            class="text-ink-danger"
            @click="handleDeleteTask(String(row.id))"
          >
            删除
          </UiButton>
        </template>
      </UiTable>
    </div>

    <div v-if="activeTab === 'models'">
      <UiEmpty v-if="store.models.length === 0" title="暂无训练产出模型" />
      <div v-else class="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
        <div
          v-for="m in store.models"
          :key="m.id"
          class="rounded-ink-md border border-ink-border bg-ink-surface p-5 transition-shadow hover:shadow-[var(--ink-shadow-md)]"
        >
          <div class="mb-2 text-sm font-semibold text-ink-text">{{ m.name }}</div>
          <div class="mb-1 text-xs text-ink-text-muted">
            基座: <span class="font-mono">{{ m.base_model }}</span>
          </div>
          <div class="mb-1 truncate text-xs text-ink-text-muted" :title="m.model_path || ''">
            {{ m.model_path }}
          </div>
          <div class="mb-3 text-xs text-ink-text-muted">{{ formatDateTime(m.created_at) }}</div>
          <div class="flex flex-wrap gap-2">
            <UiButton variant="secondary" size="sm" @click="handleExportModel(m.id)">
              导出部署包
            </UiButton>
            <UiButton variant="secondary" size="sm" @click="handleVerifyModel(m.id, false)">
              验证决策
            </UiButton>
            <UiButton variant="secondary" size="sm" @click="handleVerifyModel(m.id, true)">
              测一局
            </UiButton>
            <UiButton
              variant="ghost"
              size="sm"
              class="text-ink-danger"
              @click="handleDeleteModel(m.id)"
            >
              删除
            </UiButton>
          </div>
        </div>
      </div>
    </div>

    <UiDialog
      :open="showCreateDialog"
      title="创建训练任务"
      class="w-[min(92vw,550px)]"
      @update:open="showCreateDialog = $event"
    >
      <div class="space-y-4">
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-text">
            任务名称 <span class="text-ink-danger">*</span>
          </label>
          <UiInput v-model="createForm.name" placeholder="如：斗地主SFT-v1" class="w-full" />
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-text">
            数据集 <span class="text-ink-danger">*</span>
          </label>
          <UiSelect
            v-model="createForm.dataset_id"
            :options="datasetOptions"
            placeholder="选择数据集"
            class="w-full"
          />
          <div v-if="datasets.length === 0" class="mt-1 text-xs text-ink-accent">
            暂无数据集，请先在「数据看板」创建
          </div>
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-text">基座模型</label>
          <UiSelect
            v-model="createForm.base_model"
            :options="baseModelOptions"
            class="w-full"
          />
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-text">训练超参</label>
          <div class="grid grid-cols-3 gap-3">
            <div>
              <div class="mb-1 text-xs text-ink-text-muted">学习率</div>
              <UiInputNumber
                :model-value="createForm.learning_rate"
                :min="1e-6"
                :max="1e-3"
                :step="1e-5"
                class="w-full"
                @update:model-value="(v) => (createForm.learning_rate = v ?? 2e-5)"
              />
            </div>
            <div>
              <div class="mb-1 text-xs text-ink-text-muted">Batch Size</div>
              <UiInputNumber
                :model-value="createForm.batch_size"
                :min="1"
                :max="64"
                class="w-full"
                @update:model-value="(v) => (createForm.batch_size = v ?? 1)"
              />
            </div>
            <div>
              <div class="mb-1 text-xs text-ink-text-muted">Epochs</div>
              <UiInputNumber
                :model-value="createForm.num_epochs"
                :min="1"
                :max="20"
                class="w-full"
                @update:model-value="(v) => (createForm.num_epochs = v ?? 1)"
              />
            </div>
          </div>
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-text">LoRA / 模式</label>
          <div class="flex flex-wrap items-center gap-4">
            <UiCheckbox v-model="createForm.use_mock" label="使用 Mock（不跑真实训练）" />
            <div v-if="!createForm.use_mock" class="flex items-center gap-2">
              <span class="text-xs text-ink-text-muted">LoRA r</span>
              <UiInputNumber
                :model-value="createForm.lora_r"
                :min="1"
                :max="64"
                class="w-24"
                @update:model-value="(v) => (createForm.lora_r = v ?? 8)"
              />
            </div>
          </div>
          <div class="mt-1 text-xs text-ink-text-muted">
            真实 SFT：安装训练组依赖后取消 Mock，产物为 LoRA adapter 目录。
          </div>
        </div>
      </div>
      <template #footer>
        <UiButton variant="secondary" @click="showCreateDialog = false">取消</UiButton>
        <UiButton @click="handleCreate">创建</UiButton>
      </template>
    </UiDialog>
  </div>
</template>
