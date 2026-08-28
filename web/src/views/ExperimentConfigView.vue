<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { toast } from '@/components/ui/toast'
import { confirmDialog } from '@/components/ui/confirm'
import { showApiError } from '@/utils/error'
import {
  experimentConfigApi,
  type ExperimentConfig,
  type ExperimentConfigStats,
  type CreateExperimentConfigRequest,
  type UpdateExperimentConfigRequest,
} from '@/api/experimentConfigApi'
import { formatDateTime, formatPercentage } from '@/utils/format'
import UiButton from '@/components/ui/Button.vue'
import UiDialog from '@/components/ui/Dialog.vue'
import UiInput from '@/components/ui/Input.vue'
import UiTextarea from '@/components/ui/Textarea.vue'
import UiSelect from '@/components/ui/Select.vue'
import UiInputNumber from '@/components/ui/InputNumber.vue'
import UiSpinner from '@/components/ui/Spinner.vue'
import UiBadge from '@/components/ui/Badge.vue'
import UiEmpty from '@/components/ui/Empty.vue'
import { systemApi, type ProviderInfo } from '@/api/systemApi'

const configs = ref<ExperimentConfig[]>([])
const configStats = ref<Map<string, ExperimentConfigStats>>(new Map())
const loading = ref(false)
const dialogVisible = ref(false)
const isEditing = ref(false)

const providers = ref<ProviderInfo[]>([])
const providerOptions = computed(() =>
  providers.value.map((p) => ({ label: p.name, value: p.id })),
)

function onProviderChange(val: string) {
  const provider = providers.value.find((p) => p.id === val)
  if (provider?.default_model) {
    form.value.model_config_data.model_name = provider.default_model
  }
}

const defaultForm = (): CreateExperimentConfigRequest => ({
  id: '',
  name: '',
  notes: '',
  model_config_data: {
    provider: 'openai',
    model_name: 'gpt-4o-mini',
    temperature: 0.7,
    top_p: 0.95,
    max_tokens: 1024,
  },
})

const form = ref<CreateExperimentConfigRequest>(defaultForm())

const EMPTY_STATS: ExperimentConfigStats = {
  config_id: '',
  games_played: 0,
  wins: 0,
  losses: 0,
  win_rate: 0,
  last_game_id: null,
  last_game_at: null,
}

function getConfigStats(configId: string): ExperimentConfigStats {
  return configStats.value.get(configId) ?? { ...EMPTY_STATS, config_id: configId }
}

async function fetchConfigs() {
  loading.value = true
  try {
    const [configsRes, statsRes, providersRes] = await Promise.all([
      experimentConfigApi.list(),
      experimentConfigApi.getAllStats(),
      systemApi.listProviders(),
    ])
    configs.value = configsRes.data
    providers.value = providersRes.data
    const statsMap = new Map<string, ExperimentConfigStats>()
    for (const stat of statsRes.data) {
      statsMap.set(stat.config_id, stat)
    }
    configStats.value = statsMap
  } catch (e: unknown) {
    showApiError(e, '加载失败')
  } finally {
    loading.value = false
  }
}

function openCreateDialog() {
  isEditing.value = false
  form.value = defaultForm()
  dialogVisible.value = true
}

function openEditDialog(config: ExperimentConfig) {
  isEditing.value = true
  form.value = {
    id: config.id,
    name: config.name,
    notes: config.notes,
    model_config_data: { ...config.model_config },
  }
  dialogVisible.value = true
}

async function handleSubmit() {
  try {
    if (isEditing.value) {
      const updateData: UpdateExperimentConfigRequest = {
        name: form.value.name,
        notes: form.value.notes,
        model_config_data: form.value.model_config_data,
      }
      await experimentConfigApi.update(form.value.id, updateData)
      toast.success('更新成功')
    } else {
      await experimentConfigApi.create(form.value)
      toast.success('创建成功')
    }
    dialogVisible.value = false
    await fetchConfigs()
  } catch (e: unknown) {
    showApiError(e, '操作失败')
  }
}

async function handleDelete(config: ExperimentConfig) {
  const ok = await confirmDialog({
    message: `确定删除实验配置「${config.name}」吗？`,
    title: '删除确认',
    confirmText: '删除',
    danger: true,
  })
  if (!ok) return
  try {
    await experimentConfigApi.delete(config.id)
    toast.success('已删除')
    await fetchConfigs()
  } catch (e: unknown) {
    showApiError(e, '删除失败')
  }
}

onMounted(fetchConfigs)
</script>

<template>
  <div class="page-container">
    <div class="mb-5 flex flex-wrap items-center justify-between gap-3">
      <p class="text-base text-ink-text-secondary">
        采样参数配置档；提示词在「提示词」页统一管理。
      </p>
      <UiButton @click="openCreateDialog">新增配置</UiButton>
    </div>

    <div class="relative min-h-[200px]">
      <UiSpinner v-if="loading" overlay label="加载中…" />
      <div class="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
        <div
          v-for="config in configs"
          :key="config.id"
          class="rounded-ink-md border border-ink-border bg-ink-surface p-5 transition-shadow hover:shadow-[var(--ink-shadow-md)]"
        >
          <div class="mb-4">
            <h3 class="font-semibold text-ink-text">{{ config.name }}</h3>
            <span class="text-xs text-ink-text-muted">{{ config.id }}</span>
          </div>
          <div class="mb-4 flex flex-wrap gap-2">
            <UiBadge variant="muted">{{ config.model_config.provider }}</UiBadge>
            <UiBadge>{{ config.model_config.model_name }}</UiBadge>
            <UiBadge variant="warning">T={{ config.model_config.temperature }}</UiBadge>
            <UiBadge variant="muted">top_p={{ config.model_config.top_p }}</UiBadge>
            <UiBadge variant="muted">max={{ config.model_config.max_tokens }}</UiBadge>
          </div>
          <p v-if="config.notes" class="mb-4 text-sm text-ink-text-secondary">{{ config.notes }}</p>

          <div class="mb-4 border-t border-ink-border pt-4">
            <div class="grid grid-cols-3 gap-2 text-center">
              <div>
                <div class="text-lg font-semibold text-ink-text">
                  {{ getConfigStats(config.id).games_played }}
                </div>
                <div class="text-xs text-ink-text-muted">对局</div>
              </div>
              <div>
                <div
                  class="text-lg font-semibold"
                  :class="
                    getConfigStats(config.id).win_rate >= 0.5
                      ? 'text-ink-success'
                      : 'text-ink-danger'
                  "
                >
                  {{ formatPercentage(getConfigStats(config.id).win_rate) }}
                </div>
                <div class="text-xs text-ink-text-muted">胜率</div>
              </div>
              <div>
                <div class="text-lg font-semibold text-ink-text">
                  {{ getConfigStats(config.id).wins }}
                </div>
                <div class="text-xs text-ink-text-muted">胜场</div>
              </div>
            </div>
            <div
              v-if="getConfigStats(config.id).last_game_at"
              class="mt-2 text-center text-xs text-ink-text-muted"
            >
              最近对局: {{ formatDateTime(getConfigStats(config.id).last_game_at) }}
            </div>
          </div>

          <div class="flex gap-2">
            <UiButton variant="secondary" size="sm" @click="openEditDialog(config)">编辑</UiButton>
            <UiButton variant="ghost" size="sm" class="text-ink-danger" @click="handleDelete(config)">
              删除
            </UiButton>
          </div>
        </div>

        <div v-if="!loading && configs.length === 0" class="col-span-full">
          <UiEmpty title="暂无实验配置" description="点击上方按钮创建" />
        </div>
      </div>
    </div>

    <UiDialog
      :open="dialogVisible"
      :title="isEditing ? '编辑实验配置' : '新增实验配置'"
      class="w-[min(92vw,560px)]"
      @update:open="dialogVisible = $event"
    >
      <div class="space-y-4">
        <div v-if="!isEditing">
          <label class="mb-1.5 block text-sm font-medium text-ink-text">
            配置 ID <span class="text-ink-danger">*</span>
          </label>
          <UiInput v-model="form.id" placeholder="如 cfg_temp_09" class="w-full" />
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-text">
            名称 <span class="text-ink-danger">*</span>
          </label>
          <UiInput v-model="form.name" placeholder="如 Temp 0.9" class="w-full" />
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-text">备注</label>
          <UiTextarea
            v-model="form.notes"
            :rows="2"
            placeholder="实验意图说明，如「高 temperature 对照」"
            class="w-full"
          />
        </div>

        <div class="rounded-ink-md bg-ink-surface-muted p-4">
          <h4 class="mb-3 font-medium text-ink-text">模型配置</h4>
          <div class="space-y-3">
            <div>
              <label class="mb-1.5 block text-sm font-medium text-ink-text">供应商</label>
              <UiSelect
                v-model="form.model_config_data.provider"
                :options="providerOptions"
                class="w-full"
                @update:model-value="onProviderChange"
              />
            </div>
            <div>
              <label class="mb-1.5 block text-sm font-medium text-ink-text">模型名称</label>
              <UiInput
                v-model="form.model_config_data.model_name"
                placeholder="gpt-4o-mini"
                class="w-full"
              />
            </div>
            <div class="grid grid-cols-3 gap-3">
              <div>
                <label class="mb-1.5 block text-sm font-medium text-ink-text">Temperature</label>
                <UiInputNumber
                  :model-value="form.model_config_data.temperature"
                  :min="0"
                  :max="2"
                  :step="0.1"
                  class="w-full"
                  @update:model-value="(v) => (form.model_config_data.temperature = v ?? 0.7)"
                />
              </div>
              <div>
                <label class="mb-1.5 block text-sm font-medium text-ink-text">Top P</label>
                <UiInputNumber
                  :model-value="form.model_config_data.top_p"
                  :min="0"
                  :max="1"
                  :step="0.05"
                  class="w-full"
                  @update:model-value="(v) => (form.model_config_data.top_p = v ?? 0.95)"
                />
              </div>
              <div>
                <label class="mb-1.5 block text-sm font-medium text-ink-text">Max Tokens</label>
                <UiInputNumber
                  :model-value="form.model_config_data.max_tokens"
                  :min="64"
                  :max="4096"
                  :step="64"
                  class="w-full"
                  @update:model-value="(v) => (form.model_config_data.max_tokens = v ?? 1024)"
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <UiButton variant="secondary" @click="dialogVisible = false">取消</UiButton>
        <UiButton @click="handleSubmit">{{ isEditing ? '保存' : '创建' }}</UiButton>
      </template>
    </UiDialog>
  </div>
</template>
