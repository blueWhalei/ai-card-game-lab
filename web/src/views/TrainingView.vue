<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { toast } from '@/components/ui/toast'
import { confirmDialog } from '@/components/ui/confirm'
import { showApiError, getVerifyErrorMessage } from '@/utils/error'
import { useTrainingStore } from '@/stores/useTrainingStore'
import { dataApi } from '@/api/dataApi'
import type { DatasetItem } from '@/api/dataApi'
import { TRAINING_STATUS_MAP } from '@/utils/constants'
import UiButton from '@/components/ui/Button.vue'
import UiDialog from '@/components/ui/Dialog.vue'
import UiInput from '@/components/ui/Input.vue'
import UiSelect from '@/components/ui/Select.vue'
import UiInputNumber from '@/components/ui/InputNumber.vue'
import UiCheckbox from '@/components/ui/Checkbox.vue'
import type { TableColumn } from '@/components/ui/Table.vue'
import { systemApi, type PreflightResult } from '@/api/systemApi'
import { experimentConfigApi } from '@/api/experimentConfigApi'
import type { ModelItem } from '@/api/trainingApi'
import {
  configIdForModel,
  configNameForModel,
  ollamaTagForModel,
} from '@/utils/adapterConfig'
import TrainingLivePanel from '@/components/training/TrainingLivePanel.vue'
import TrainingModelsPanel, {
  type ModelBusyAction,
  type ModelBusyState,
} from '@/components/training/TrainingModelsPanel.vue'
import TrainingTasksPanel from '@/components/training/TrainingTasksPanel.vue'
import PreflightBanner from '@/components/common/PreflightBanner.vue'

const { t } = useI18n()
const store = useTrainingStore()
const route = useRoute()
const router = useRouter()
const datasets = ref<DatasetItem[]>([])
const showCreateDialog = ref(false)
const activeTab = ref<'tasks' | 'models'>('tasks')
const trainingDepsAvailable = ref(false)
const trainingEnvLoaded = ref(false)
const preflight = ref<PreflightResult | null>(null)
const cancelling = ref(false)
const modelBusy = ref<ModelBusyState | null>(null)
const registerAfterPush = ref(false)
let pendingToastId: number | null = null
let pollTimer: ReturnType<typeof setInterval> | null = null

function beginModelAction(id: string, action: ModelBusyAction, pendingMessage: string): void {
  modelBusy.value = { id, action }
  if (pendingToastId != null) toast.dismiss(pendingToastId)
  pendingToastId = toast.pending(pendingMessage)
}

function endModelAction(): void {
  if (pendingToastId != null) {
    toast.dismiss(pendingToastId)
    pendingToastId = null
  }
  modelBusy.value = null
}

const experimentIdFilter = computed(() => {
  const v = route.query.experiment_id
  return typeof v === 'string' && v ? v : undefined
})

const returnToControl = computed(
  () => route.query.return_control === '1' && Boolean(experimentIdFilter.value),
)

function goBackToControl(): void {
  const id = experimentIdFilter.value
  if (!id) return
  void router.push({ path: `/experiments/${id}`, query: { open_control: '1' } })
}

function applyTabFromRoute(): void {
  activeTab.value = route.query.tab === 'models' ? 'models' : 'tasks'
}

async function refreshTasks(): Promise<void> {
  await store.fetchTasks(
    experimentIdFilter.value ? { experiment_id: experimentIdFilter.value } : undefined,
  )
}

function setTab(tab: 'tasks' | 'models'): void {
  activeTab.value = tab
  const query = { ...route.query }
  if (tab === 'models') {
    query.tab = 'models'
  } else {
    delete query.tab
  }
  void router.replace({ query })
  if (tab === 'models') {
    void store.fetchModels()
  }
}

const CPU_SMOKE_BASE_MODEL = 'Qwen/Qwen2.5-0.5B'
const CPU_SMOKE_MAX_STEPS = 20

const createForm = ref({
  name: '',
  dataset_id: '',
  base_model: CPU_SMOKE_BASE_MODEL,
  training_type: 'sft',
  learning_rate: 2e-5,
  batch_size: 1,
  num_epochs: 1,
  lora_r: 8,
  max_steps: CPU_SMOKE_MAX_STEPS,
  qlora: false,
})

const baseModelOptions = ref([
  { label: 'Qwen2.5-1.5B', value: 'Qwen/Qwen2.5-1.5B' },
  { label: 'Qwen2.5-7B', value: 'Qwen/Qwen2.5-7B' },
  { label: 'Llama-3.2-3B', value: 'meta-llama/Llama-3.2-3B' },
  { label: t('training.cpuSmoke'), value: CPU_SMOKE_BASE_MODEL },
])

const datasetOptions = computed(() =>
  datasets.value.map((ds) => {
    const fmt = ds.filters?.format === 'chatml' ? 'ChatML' : 'JSONL'
    return {
      label: `${ds.name} (${ds.sample_count} · ${fmt})`,
      value: ds.id,
    }
  }),
)

type TaskRow = (typeof store.tasks)[number] & Record<string, unknown>

const taskColumns = computed(
  (): TableColumn<TaskRow>[] => [
    { key: 'name', label: t('training.colTaskName') },
    { key: 'base_model', label: t('training.colBase'), class: 'w-48' },
    { key: 'status', label: t('common.status'), class: 'w-40' },
    { key: 'progress', label: t('common.progress'), class: 'w-40' },
    { key: 'created_at', label: t('common.createdAt'), class: 'w-44' },
  ],
)

const taskRows = computed(() => store.tasks as TaskRow[])

type ModelRow = ModelItem & Record<string, unknown>

const modelColumns = computed(
  (): TableColumn<ModelRow>[] => [
    { key: 'name', label: t('common.name'), class: 'w-[28%]' },
    { key: 'base_model', label: t('training.colBaseShort'), class: 'w-[18%]' },
    { key: 'model_path', label: t('common.path'), class: 'w-[14%]' },
    { key: 'created_at', label: t('common.createdAt'), class: 'w-[16%]' },
  ],
)

const modelRows = computed(() => store.models as ModelRow[])

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
  } catch (e: unknown) {
    showApiError(e, t('training.loadDatasetsFailed'))
  }
}

function openCreateDialog() {
  createForm.value = {
    name: '',
    dataset_id: '',
    base_model: CPU_SMOKE_BASE_MODEL,
    training_type: 'sft',
    learning_rate: 2e-5,
    batch_size: 1,
    num_epochs: 1,
    lora_r: 8,
    max_steps: CPU_SMOKE_MAX_STEPS,
    qlora: false,
  }
  showCreateDialog.value = true
  fetchDatasets()
}

async function handleCreate() {
  if (!createForm.value.name.trim()) {
    toast.warning(t('training.needTaskName'))
    return
  }
  if (!createForm.value.dataset_id) {
    toast.warning(t('training.needDataset'))
    return
  }
  if (!trainingDepsAvailable.value) {
    toast.warning(t('training.noDepsToast'))
    return
  }
  const ok = await confirmDialog({
    title: t('training.confirmStartTitle'),
    message: t('training.confirmStartMsg'),
    confirmText: t('training.startTrain'),
    cancelText: t('common.cancel'),
  })
  if (!ok) return
  const trainingConfig: Record<string, unknown> = {
    learning_rate: createForm.value.learning_rate,
    batch_size: createForm.value.batch_size,
    num_epochs: createForm.value.num_epochs,
    output_format: 'pytorch',
    lora_r: createForm.value.lora_r,
  }
  if (createForm.value.qlora) {
    trainingConfig.qlora = true
  }
  if (createForm.value.max_steps > 0) {
    trainingConfig.max_steps = createForm.value.max_steps
  }
  try {
    await store.createTask({
      name: createForm.value.name,
      dataset_id: createForm.value.dataset_id,
      base_model: createForm.value.base_model,
      training_type: createForm.value.training_type,
      config: trainingConfig,
    })
    toast.success(t('training.taskCreated'))
    showCreateDialog.value = false
  } catch (e: unknown) {
    showApiError(e, t('error.createFailed'))
  }
}

async function handleCancelTask(id: string) {
  const ok = await confirmDialog({
    title: t('training.cancelTitle'),
    message: t('training.cancelMsg'),
    confirmText: t('training.cancelTrain'),
    danger: true,
  })
  if (!ok) return
  cancelling.value = true
  try {
    await store.cancelTask(id)
    toast.success(t('training.cancelRequested'))
  } catch (e: unknown) {
    showApiError(e, t('training.cancelFailed'))
  } finally {
    cancelling.value = false
  }
}

async function handleDeleteTask(id: string) {
  const ok = await confirmDialog({
    message: t('training.deleteTask'),
    title: t('common.confirm'),
    danger: true,
  })
  if (!ok) return
  try {
    await store.deleteTask(id)
    toast.success(t('error.deleted'))
  } catch (e: unknown) {
    showApiError(e, t('error.deleteFailed'))
  }
}

async function handleDeleteModel(id: string) {
  const ok = await confirmDialog({
    message: t('training.deleteModel'),
    title: t('common.confirm'),
    danger: true,
  })
  if (!ok) return
  beginModelAction(id, 'delete', t('training.actionDeletePending'))
  try {
    await store.deleteModel(id)
    toast.success(t('error.deleted'))
  } catch (e: unknown) {
    showApiError(e, t('error.deleteFailed'))
  } finally {
    endModelAction()
  }
}

async function handleExportModel(id: string) {
  beginModelAction(id, 'export', t('training.actionExportPending'))
  try {
    const result = await store.exportModel(id, { merge: true, try_create: false })
    const merged = result.merged === true
    toast.success(
      merged ? t('training.exportedMerged') : t('training.exportedScript'),
      6000,
    )
  } catch (e: unknown) {
    showApiError(e, t('training.exportFailed'))
  } finally {
    endModelAction()
  }
}

function isLoraModel(m: ModelItem): boolean {
  return Boolean(m.model_path && !m.model_path.endsWith('model.bin'))
}

async function handlePushToOllama(m: ModelItem) {
  if (!isLoraModel(m)) {
    toast.warning(t('training.notLora'))
    return
  }
  beginModelAction(m.id, 'push', t('training.actionPushPending'))
  try {
    const result = await store.pushToOllama(m.id)
    const tag = String(result.ollama_tag ?? ollamaTagForModel(m.id))
    toast.success(t('training.pushed', { tag }))
    if (registerAfterPush.value) {
      await handleRegisterAsPlayer(m, { skipBusy: true, ollamaTag: tag })
    }
  } catch (e: unknown) {
    showApiError(e, t('training.pushFailed'))
  } finally {
    endModelAction()
  }
}

async function handleVerifyModel(id: string, runGame: boolean) {
  beginModelAction(
    id,
    runGame ? 'verify_game' : 'verify',
    runGame ? t('training.actionVerifyGamePending') : t('training.actionVerifyPending'),
  )
  try {
    const result = await store.verifyModel(id, { run_game: runGame })
    if (result.ok) {
      const gameId = (result.game as { game_id?: string } | undefined)?.game_id
      toast.success(
        runGame && gameId
          ? t('training.verifiedGame', { id: gameId })
          : t('training.verifiedSmoke'),
      )
    } else {
      toast.warning(getVerifyErrorMessage(result))
    }
  } catch (e: unknown) {
    showApiError(e, t('training.verifyFailed'))
  } finally {
    endModelAction()
  }
}

async function handleRegisterAsPlayer(
  m: ModelItem,
  opts?: { skipBusy?: boolean; ollamaTag?: string },
) {
  if (!m.model_path || m.model_path.endsWith('model.bin')) {
    toast.warning(t('training.notLoraPlayer'))
    return
  }
  if (!opts?.skipBusy) {
    beginModelAction(m.id, 'register', t('training.actionRegisterPending'))
  }
  const configId = configIdForModel(m.id)
  const tag = opts?.ollamaTag ?? ollamaTagForModel(m.id)
  const name = configNameForModel(m.name)
  const notes = [
    `from training task ${m.id}`,
    `base_model=${m.base_model}`,
    `adapter=${m.model_path}`,
    `ollama_tag=${tag}`,
    t('training.ollamaNeedTag'),
  ].join('; ')

  try {
    const existing = await experimentConfigApi.get(configId).catch(() => null)
    if (existing?.data) {
      toast.info(t('training.playerExists', { name: existing.data.name, id: configId }))
      if (returnToControl.value) {
        goBackToControl()
        return
      }
      void router.push('/experiment-configs')
      return
    }
  } catch {
    /* treat as missing */
  }

  try {
    await experimentConfigApi.create({
      id: configId,
      name,
      notes,
      model_config_data: {
        provider: 'ollama',
        model_name: tag,
        temperature: 0.3,
        top_p: 0.9,
        max_tokens: 256,
      },
    })
    toast.success(t('training.playerAdded', { name, tag }))
    if (returnToControl.value) {
      goBackToControl()
    }
  } catch (e: unknown) {
    showApiError(e, t('training.addPlayerFailed'))
  } finally {
    if (!opts?.skipBusy) endModelAction()
  }
}

function formatProgress(p: number): string {
  return `${Math.round(p * 100)}%`
}

function startPolling() {
  pollTimer = setInterval(async () => {
    const hasRunning = store.tasks.some((task) =>
      ['pending', 'exporting', 'training'].includes(task.status),
    )
    if (hasRunning) {
      await refreshTasks()
    }
  }, 3000)
}

onMounted(async () => {
  try {
    const [cfg, pf] = await Promise.all([
      systemApi.getConfig(),
      systemApi.preflight({ scope: 'train' }).catch(() => null),
    ])
    const models = cfg.data.default_base_models
    if (models?.length) {
      baseModelOptions.value = models.map((m) => ({
        label: m.split('/').pop() || m,
        value: m,
      }))
      createForm.value.base_model = models[0] ?? createForm.value.base_model
    }
    createForm.value.max_steps = CPU_SMOKE_MAX_STEPS
    preflight.value = pf?.data ?? null
    trainingDepsAvailable.value =
      preflight.value?.can_train ?? cfg.data.training_deps_available === true
  } catch (e: unknown) {
    showApiError(e, t('training.configFallback'))
  } finally {
    trainingEnvLoaded.value = true
  }
  applyTabFromRoute()
  if (activeTab.value === 'models') {
    void store.fetchModels()
  }
  await refreshTasks()
  store.fetchModels()
  startPolling()
})

watch(
  () => route.query.tab,
  () => {
    applyTabFromRoute()
  },
)

watch(experimentIdFilter, () => {
  void refreshTasks()
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
    <div class="mb-5 flex justify-end">
      <UiButton
        class="shrink-0 whitespace-nowrap"
        :disabled="!trainingEnvLoaded || !trainingDepsAvailable"
        @click="openCreateDialog"
      >
        {{ t('training.createTask') }}
      </UiButton>
    </div>

    <PreflightBanner
      v-if="trainingEnvLoaded && preflight?.checks?.length"
      class="mb-5"
      :checks="preflight!.checks"
    />
    <div
      v-else-if="trainingEnvLoaded && !trainingDepsAvailable"
      class="mb-5 rounded-ink-md border border-ink-accent/40 bg-ink-surface px-4 py-3 text-sm text-ink-text-secondary"
    >
      {{ t('training.noDeps') }}
      <code class="rounded bg-ink-surface-muted px-1.5 py-0.5 text-xs">cd server && poetry install --with training</code>
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
        @click="setTab('tasks')"
      >
        {{ t('training.tasks') }}
      </button>
      <button
        type="button"
        class="rounded-[6px] px-4 py-2 text-base font-medium transition-colors"
        :class="
          activeTab === 'models'
            ? 'bg-ink-surface text-ink-text shadow-[var(--ink-shadow)]'
            : 'text-ink-text-muted hover:text-ink-text'
        "
        @click="setTab('models')"
      >
        {{ t('training.models') }}
      </button>
    </div>

    <TrainingLivePanel
      :tasks="store.tasks"
      :cancelling="cancelling"
      @cancel="handleCancelTask"
    />

    <TrainingTasksPanel
      v-if="activeTab === 'tasks'"
      :columns="taskColumns"
      :rows="taskRows"
      :loading="store.isLoading"
      :status-variant="statusVariant"
      :format-progress="formatProgress"
      @delete="handleDeleteTask"
    />

    <p
      v-if="activeTab === 'models' && returnToControl"
      class="mb-4 rounded-ink-md border border-ink-border bg-ink-surface-muted/60 px-3 py-2 text-sm text-ink-text-secondary"
    >
      {{ t('training.returnToControlHint') }}
    </p>

    <TrainingModelsPanel
      v-if="activeTab === 'models'"
      :columns="modelColumns"
      :rows="modelRows"
      :empty="store.models.length === 0"
      :register-after-push="registerAfterPush"
      :model-busy="modelBusy"
      :is-lora-model="isLoraModel"
      @update:register-after-push="registerAfterPush = $event"
      @push="handlePushToOllama"
      @export="handleExportModel"
      @register="handleRegisterAsPlayer"
      @verify="handleVerifyModel"
      @delete="handleDeleteModel"
    />


    <UiDialog
      :open="showCreateDialog"
      :title="t('training.createTask')"
      class="w-[min(92vw,480px)]"
      @update:open="showCreateDialog = $event"
    >
      <div class="space-y-4">
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-text">
            {{ t('training.taskName') }} <span class="text-ink-danger">*</span>
          </label>
          <UiInput v-model="createForm.name" :placeholder="t('training.taskNamePh')" class="w-full" />
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-text">
            {{ t('training.dataset') }} <span class="text-ink-danger">*</span>
          </label>
          <UiSelect
            v-model="createForm.dataset_id"
            :options="datasetOptions"
            :placeholder="t('training.pickDataset')"
            class="w-full"
          />
          <div v-if="datasets.length === 0" class="mt-2 text-xs text-ink-accent">
            {{ t('training.noDatasetPrefix') }}
            <button
              type="button"
              class="underline"
              @click="showCreateDialog = false; router.push('/decisions')"
            >
              {{ t('nav.decisions') }}
            </button>
            {{ t('training.noDatasetSuffix') }}
          </div>
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-text">{{ t('training.baseModel') }}</label>
          <UiSelect
            v-model="createForm.base_model"
            :options="baseModelOptions"
            class="w-full"
          />
        </div>

        <details class="group rounded-ink border border-ink-border">
          <summary
            class="flex cursor-pointer list-none items-center gap-2 px-3 py-2 text-sm font-medium text-ink-text marker:content-none [&::-webkit-details-marker]:hidden"
          >
            <Icon
              icon="lucide:chevron-right"
              class="h-3.5 w-3.5 shrink-0 text-ink-text-secondary transition-transform group-open:rotate-90"
            />
            {{ t('training.advanced') }}
          </summary>
          <div class="space-y-4 border-t border-ink-border px-3 py-3">
            <div>
              <label class="mb-1.5 block text-sm font-medium text-ink-text">{{ t('training.params') }}</label>
              <div class="grid grid-cols-3 gap-3">
                <div>
                  <div class="mb-1 text-xs text-ink-text-muted">{{ t('training.lr') }}</div>
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
                  <div class="mb-1 text-xs text-ink-text-muted">{{ t('training.batch') }}</div>
                  <UiInputNumber
                    :model-value="createForm.batch_size"
                    :min="1"
                    :max="64"
                    class="w-full"
                    @update:model-value="(v) => (createForm.batch_size = v ?? 1)"
                  />
                </div>
                <div>
                  <div class="mb-1 text-xs text-ink-text-muted">{{ t('training.epochs') }}</div>
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
              <label class="mb-1.5 block text-sm font-medium text-ink-text">LoRA</label>
              <div class="flex flex-wrap items-center gap-4">
                <div class="flex items-center gap-2">
                  <span class="text-xs text-ink-text-muted">LoRA r</span>
                  <UiInputNumber
                    :model-value="createForm.lora_r"
                    :min="1"
                    :max="64"
                    @update:model-value="(v) => (createForm.lora_r = v ?? 8)"
                  />
                </div>
                <div class="flex items-center gap-2">
                  <span class="text-xs text-ink-text-muted">{{ t('training.maxSteps') }}</span>
                  <UiInputNumber
                    :model-value="createForm.max_steps"
                    :min="1"
                    :max="1000"
                    @update:model-value="(v) => (createForm.max_steps = v ?? CPU_SMOKE_MAX_STEPS)"
                  />
                </div>
              </div>
              <div class="mt-3">
                <UiCheckbox v-model="createForm.qlora" :label="t('training.qlora')" />
                <p class="mt-1 text-xs text-ink-text-muted">{{ t('training.qloraHint') }}</p>
              </div>
              <div class="mt-1 text-xs text-ink-text-muted">
                {{ t('training.loraHint') }}
              </div>
            </div>
          </div>
        </details>
      </div>
      <template #footer>
        <UiButton variant="secondary" @click="showCreateDialog = false">{{ t('common.cancel') }}</UiButton>
        <UiButton
          :disabled="!trainingEnvLoaded || !trainingDepsAvailable"
          @click="handleCreate"
        >
          {{ t('common.create') }}
        </UiButton>
      </template>
    </UiDialog>
  </div>
</template>
