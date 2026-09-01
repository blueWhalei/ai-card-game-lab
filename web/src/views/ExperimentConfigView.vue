<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
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
import UiTable from '@/components/ui/Table.vue'
import type { TableColumn } from '@/components/ui/Table.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { systemApi, type ProviderInfo } from '@/api/systemApi'

const { t } = useI18n()

type ConfigRow = ExperimentConfig & Record<string, unknown>

const configColumns = computed((): TableColumn<ConfigRow>[] => [
  { key: 'name', label: t('common.name') },
  { key: 'model', label: t('common.model'), class: 'w-48' },
  { key: 'sampling', label: t('common.sampling'), class: 'w-40' },
  { key: 'games', label: t('common.games'), class: 'w-20' },
  { key: 'win_rate', label: t('common.winRate'), class: 'w-20' },
  { key: 'recent', label: t('common.recent'), class: 'hidden w-44 md:table-cell' },
])

const configRows = computed(() => configs.value as ConfigRow[])

const router = useRouter()
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
    showApiError(e, t('config.loadFailed'))
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
  const id = form.value.id.trim()
  const name = form.value.name.trim()
  if (!isEditing.value && !id) {
    toast.warning(t('config.needId'))
    return
  }
  if (!name) {
    toast.warning(t('config.needName'))
    return
  }
  try {
    if (isEditing.value) {
      const updateData: UpdateExperimentConfigRequest = {
        name,
        notes: form.value.notes,
        model_config_data: form.value.model_config_data,
      }
      await experimentConfigApi.update(form.value.id, updateData)
      toast.success(t('config.updated'))
    } else {
      await experimentConfigApi.create({ ...form.value, id, name })
      toast.success(t('config.created'))
    }
    dialogVisible.value = false
    await fetchConfigs()
  } catch (e: unknown) {
    showApiError(e, t('error.operationFailed'))
  }
}

async function handleDelete(config: ExperimentConfig) {
  const id = String(config.id ?? '')
  const ok = await confirmDialog({
    message: t('config.deleteConfirm', { name: config.name || id || t('common.noId') }),
    title: t('config.deleteTitle'),
    confirmText: t('common.delete'),
    danger: true,
  })
  if (!ok) return
  try {
    await experimentConfigApi.delete(id)
    toast.success(t('error.deleted'))
    await fetchConfigs()
  } catch (e: unknown) {
    showApiError(e, t('error.deleteFailed'))
  }
}

onMounted(fetchConfigs)
</script>

<template>
  <div class="page-container">
    <div class="mb-5 flex flex-wrap items-center justify-end gap-2">
      <UiButton @click="openCreateDialog">{{ t('config.add') }}</UiButton>
    </div>

    <div class="relative min-h-[200px]">
      <UiSpinner v-if="loading" overlay :label="t('common.loading')" />
      <EmptyState
        v-else-if="configs.length === 0"
        :title="t('config.emptyTitle')"
      >
        <template #action>
          <UiButton @click="openCreateDialog">{{ t('config.add') }}</UiButton>
        </template>
      </EmptyState>
      <UiTable
        v-else
        :columns="configColumns"
        :rows="configRows"
        row-key="id"
      >
        <template #cell-name="{ row }">
          <div class="min-w-0">
            <div class="font-medium text-ink-text">{{ row.name }}</div>
            <div class="truncate font-mono text-xs text-ink-text-muted">
              {{ String(row.id || t('common.noId')) }}
            </div>
          </div>
        </template>
        <template #cell-model="{ row }">
          <span
            class="block max-w-[12rem] truncate text-sm text-ink-text"
            :title="`${row.model_config.provider} / ${row.model_config.model_name}`"
          >
            {{ row.model_config.provider }} / {{ row.model_config.model_name }}
          </span>
        </template>
        <template #cell-sampling="{ row }">
          <span
            class="block max-w-[10rem] truncate text-sm text-ink-text-secondary"
            :title="`T=${row.model_config.temperature} · top_p=${row.model_config.top_p} · max=${row.model_config.max_tokens}`"
          >
            T={{ row.model_config.temperature }} · top_p={{ row.model_config.top_p }} · max={{
              row.model_config.max_tokens
            }}
          </span>
        </template>
        <template #cell-games="{ row }">
          <span class="tabular-nums">{{ getConfigStats(String(row.id)).games_played }}</span>
        </template>
        <template #cell-win_rate="{ row }">
          <span
            class="tabular-nums"
            :class="
              getConfigStats(String(row.id)).win_rate >= 0.5 ? 'text-ink-success' : 'text-ink-danger'
            "
          >
            {{ formatPercentage(getConfigStats(String(row.id)).win_rate) }}
          </span>
        </template>
        <template #cell-recent="{ row }">
          <template v-if="getConfigStats(String(row.id)).last_game_at">
            <div class="flex max-w-[11rem] items-center gap-1 truncate">
              <span
                class="min-w-0 truncate text-sm text-ink-text-secondary"
                :title="formatDateTime(getConfigStats(String(row.id)).last_game_at)"
              >
                {{ formatDateTime(getConfigStats(String(row.id)).last_game_at) }}
              </span>
              <button
                v-if="getConfigStats(String(row.id)).last_game_id"
                type="button"
                class="shrink-0 text-sm text-ink-primary hover:underline"
                @click="router.push(`/game/${getConfigStats(String(row.id)).last_game_id}`)"
              >
                {{ t('config.replay') }}
              </button>
            </div>
          </template>
          <span v-else class="text-ink-text-muted">{{ t('common.dash') }}</span>
        </template>
        <template #actions="{ row }">
          <div class="flex flex-nowrap items-center gap-1">
            <UiButton size="sm" variant="ghost" @click="openEditDialog(row as ExperimentConfig)">
              {{ t('common.edit') }}
            </UiButton>
            <UiButton
              size="sm"
              variant="ghost"
              class="text-ink-danger"
              @click="handleDelete(row as ExperimentConfig)"
            >
              {{ t('common.delete') }}
            </UiButton>
          </div>
        </template>
      </UiTable>
    </div>

    <UiDialog
      :open="dialogVisible"
      :title="isEditing ? t('config.editTitle') : t('config.createTitle')"
      class="w-[min(92vw,560px)]"
      @update:open="dialogVisible = $event"
    >
      <div class="space-y-4">
        <div v-if="!isEditing">
          <label class="mb-1.5 block text-sm font-medium text-ink-text">
            {{ t('config.playerId') }} <span class="text-ink-danger">*</span>
          </label>
          <UiInput v-model="form.id" :placeholder="t('config.idPlaceholder')" class="w-full" />
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-text">
            {{ t('common.name') }} <span class="text-ink-danger">*</span>
          </label>
          <UiInput v-model="form.name" :placeholder="t('config.namePlaceholder')" class="w-full" />
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-text">{{ t('common.notes') }}</label>
          <UiTextarea
            v-model="form.notes"
            :rows="2"
            :placeholder="t('config.notesPlaceholder')"
            class="w-full"
          />
        </div>

        <div class="rounded-ink-md bg-ink-surface-muted p-4">
          <h4 class="mb-3 font-medium text-ink-text">{{ t('config.modelSection') }}</h4>
          <div class="space-y-3">
            <div>
              <label class="mb-1.5 block text-sm font-medium text-ink-text">{{ t('config.provider') }}</label>
              <UiSelect
                v-model="form.model_config_data.provider"
                :options="providerOptions"
                class="w-full"
                @update:model-value="onProviderChange"
              />
            </div>
            <div>
              <label class="mb-1.5 block text-sm font-medium text-ink-text">{{ t('config.modelName') }}</label>
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
        <UiButton variant="secondary" @click="dialogVisible = false">{{ t('common.cancel') }}</UiButton>
        <UiButton @click="handleSubmit">{{ isEditing ? t('common.save') : t('common.create') }}</UiButton>
      </template>
    </UiDialog>
  </div>
</template>
