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
  type PlayerPolicyKind,
} from '@/api/experimentConfigApi'
import { formatPercentage } from '@/utils/format'
import { downloadJson, pickJsonFile } from '@/utils/jsonFile'
import UiButton from '@/components/ui/Button.vue'
import UiDialog from '@/components/ui/Dialog.vue'
import UiInput from '@/components/ui/Input.vue'
import UiTextarea from '@/components/ui/Textarea.vue'
import UiSelect from '@/components/ui/Select.vue'
import UiInputNumber from '@/components/ui/InputNumber.vue'
import UiSpinner from '@/components/ui/Spinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { systemApi, type ProviderInfo } from '@/api/systemApi'
import { providerName } from '@/utils/systemLabels'

const { t } = useI18n()

const router = useRouter()
const configs = ref<ExperimentConfig[]>([])
const configStats = ref<Map<string, ExperimentConfigStats>>(new Map())
const loading = ref(false)
const packing = ref(false)
const dialogVisible = ref(false)
const isEditing = ref(false)

const providers = ref<ProviderInfo[]>([])
const providerOptions = computed(() =>
  providers.value.map((p) => ({ label: providerName(p.id, p.name), value: p.id })),
)

const policyKindOptions = computed(() => [
  { label: t('config.policyKindLlm'), value: 'llm' },
  { label: t('config.policyKindToolLoop'), value: 'tool_loop' },
  { label: t('config.policyKindSearch'), value: 'search' },
  { label: t('config.policyKindHeuristic'), value: 'heuristic' },
  { label: t('config.policyKindRandom'), value: 'random' },
  { label: t('config.policyKindFirst'), value: 'first' },
])

function policyLabel(kind: PlayerPolicyKind | undefined): string {
  switch (kind) {
    case 'tool_loop':
      return t('config.policyKindToolLoop')
    case 'search':
      return t('config.policyKindSearch')
    case 'heuristic':
      return t('config.policyKindHeuristic')
    case 'random':
      return t('config.policyKindRandom')
    case 'first':
      return t('config.policyKindFirst')
    default:
      return t('config.policyKindLlm')
  }
}

function isBaselineKind(kind: PlayerPolicyKind | undefined): boolean {
  return kind === 'heuristic' || kind === 'random' || kind === 'first'
}

const defaultModelConfig = () => ({
  provider: 'openai',
  model_name: 'gpt-4o-mini',
  temperature: 0.7,
  top_p: 0.95,
  max_tokens: 1024,
})

const defaultForm = (): CreateExperimentConfigRequest => ({
  id: '',
  name: '',
  notes: '',
  policy_kind: 'llm',
  model_config_data: defaultModelConfig(),
})

const form = ref<CreateExperimentConfigRequest>(defaultForm())
const isBaselineForm = computed(() => {
  const kind = form.value.policy_kind ?? 'llm'
  return kind === 'heuristic' || kind === 'random' || kind === 'first'
})

function onProviderChange(val: string) {
  const provider = providers.value.find((p) => p.id === val)
  if (provider?.default_model && form.value.model_config_data) {
    form.value.model_config_data.model_name = provider.default_model
  }
}

function onPolicyKindChange(val: string) {
  const kind = (val as PlayerPolicyKind) || 'llm'
  form.value.policy_kind = kind
  if (
    (kind === 'llm' || kind === 'tool_loop' || kind === 'search') &&
    (!form.value.model_config_data || form.value.model_config_data.provider === 'baseline')
  ) {
    form.value.model_config_data = defaultModelConfig()
  }
}

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
    policy_kind: config.policy_kind ?? 'llm',
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
  const policyKind = form.value.policy_kind ?? 'llm'
  const usesLlm =
    policyKind === 'llm' || policyKind === 'tool_loop' || policyKind === 'search'
  try {
    if (isEditing.value) {
      const updateData: UpdateExperimentConfigRequest = {
        name,
        notes: form.value.notes,
        policy_kind: policyKind,
        model_config_data: usesLlm ? form.value.model_config_data : null,
      }
      await experimentConfigApi.update(form.value.id, updateData)
      toast.success(t('config.updated'))
    } else {
      await experimentConfigApi.create({
        id,
        name,
        notes: form.value.notes,
        policy_kind: policyKind,
        model_config_data: usesLlm ? form.value.model_config_data : null,
      })
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

async function exportPack(): Promise<void> {
  packing.value = true
  try {
    const res = await experimentConfigApi.exportPack()
    downloadJson('cardlab-players.json', res.data)
    toast.success(t('config.exportedPack'))
  } catch (e: unknown) {
    showApiError(e, t('config.exportFailed'))
  } finally {
    packing.value = false
  }
}

async function importPack(): Promise<void> {
  packing.value = true
  try {
    const raw = await pickJsonFile()
    if (raw == null) return
    const res = await experimentConfigApi.importPack(raw)
    toast.success(
      t('config.importedPack', {
        created: res.data.players_created.length,
        reused: res.data.players_reused.length,
      }),
    )
    const tags = res.data.requirements?.ollama_tags ?? []
    if (tags.length > 0) {
      toast.info(t('experiment.importOllamaTags', { tags: tags.join(', ') }))
    }
    await fetchConfigs()
  } catch (e: unknown) {
    if (e instanceof Error && e.message === 'invalid json') {
      toast.error(t('experiment.importInvalidJson'))
    } else {
      showApiError(e, t('config.importFailed'))
    }
  } finally {
    packing.value = false
  }
}
</script>

<template>
  <div class="page-container">
    <div class="mb-5 flex flex-wrap items-center justify-end gap-2">
      <UiButton variant="secondary" :loading="packing" @click="importPack">
        {{ t('config.importPack') }}
      </UiButton>
      <UiButton variant="secondary" :loading="packing" @click="exportPack">
        {{ t('config.exportPack') }}
      </UiButton>
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
          <UiButton variant="secondary" :loading="packing" @click="importPack">
            {{ t('config.importPack') }}
          </UiButton>
        </template>
      </EmptyState>
      <ul v-else class="grid gap-ink-3 sm:grid-cols-2 xl:grid-cols-3">
        <li
          v-for="row in configs"
          :key="row.id"
          class="rounded-ink-md border border-ink-border bg-ink-surface px-ink-4 py-ink-3"
        >
          <div class="flex items-start justify-between gap-ink-2">
            <div class="min-w-0">
              <h3 class="truncate text-body font-semibold text-ink-text">{{ row.name }}</h3>
              <p class="mt-ink-1 truncate text-caption text-ink-text-secondary">
                <template v-if="isBaselineKind(row.policy_kind)">
                  {{ policyLabel(row.policy_kind) }}
                </template>
                <template v-else>
                  {{ row.model_config.provider }} / {{ row.model_config.model_name }}
                </template>
              </p>
              <p
                v-if="!isBaselineKind(row.policy_kind)"
                class="mt-ink-1 text-caption text-ink-text-muted"
              >
                T={{ row.model_config.temperature }} · top_p={{ row.model_config.top_p }} · max={{
                  row.model_config.max_tokens
                }}
              </p>
              <p v-else class="mt-ink-1 text-caption text-ink-text-muted">
                {{ t('config.policyKindHint') }}
              </p>
            </div>
            <div class="flex shrink-0 items-center gap-ink-2 text-caption">
              <button
                type="button"
                class="text-ink-text-secondary hover:text-ink-text hover:underline"
                @click="openEditDialog(row)"
              >
                {{ t('common.edit') }}
              </button>
              <button
                type="button"
                class="text-ink-text-secondary hover:text-ink-danger hover:underline"
                @click="handleDelete(row)"
              >
                {{ t('common.delete') }}
              </button>
            </div>
          </div>
          <div class="mt-ink-3 flex flex-wrap items-baseline gap-ink-3 text-caption text-ink-text-muted">
            <span class="tabular-nums">
              {{ t('common.games') }} {{ getConfigStats(row.id).games_played }}
            </span>
            <span class="tabular-nums text-ink-text-secondary">
              {{ t('common.winRate') }}
              {{ formatPercentage(getConfigStats(row.id).win_rate) }}
            </span>
            <button
              v-if="getConfigStats(row.id).last_game_id"
              type="button"
              class="text-ink-primary hover:underline"
              @click="router.push(`/game/${getConfigStats(row.id).last_game_id}`)"
            >
              {{ t('config.replay') }}
            </button>
          </div>
        </li>
      </ul>
    </div>

    <UiDialog
      :open="dialogVisible"
      size="lg"
      :title="isEditing ? t('config.editTitle') : t('config.createTitle')"
      @update:open="dialogVisible = $event"
    >
      <div class="space-y-4">
        <div v-if="!isEditing">
          <label class="mb-1.5 block text-body font-medium text-ink-text">
            {{ t('config.playerId') }} <span class="text-ink-danger">*</span>
          </label>
          <UiInput v-model="form.id" :placeholder="t('config.idPlaceholder')" class="w-full" />
        </div>
        <div>
          <label class="mb-1.5 block text-body font-medium text-ink-text">
            {{ t('common.name') }} <span class="text-ink-danger">*</span>
          </label>
          <UiInput v-model="form.name" :placeholder="t('config.namePlaceholder')" class="w-full" />
        </div>
        <div>
          <label class="mb-1.5 block text-body font-medium text-ink-text">{{ t('common.notes') }}</label>
          <UiTextarea
            v-model="form.notes"
            :rows="2"
            :placeholder="t('config.notesPlaceholder')"
            class="w-full"
          />
        </div>

        <div>
          <label class="mb-1.5 block text-body font-medium text-ink-text">{{ t('config.policyKind') }}</label>
          <UiSelect
            :model-value="form.policy_kind ?? 'llm'"
            :options="policyKindOptions"
            class="w-full"
            @update:model-value="onPolicyKindChange"
          />
          <p v-if="isBaselineForm" class="mt-ink-1 text-caption text-ink-text-muted">
            {{ t('config.policyKindHint') }}
          </p>
        </div>

        <div v-if="!isBaselineForm && form.model_config_data" class="rounded-ink-md bg-ink-surface-muted p-ink-4">
          <h4 class="mb-ink-3 font-medium text-ink-text">{{ t('config.modelSection') }}</h4>
          <div class="space-y-ink-3">
            <div>
              <label class="mb-1.5 block text-body font-medium text-ink-text">{{ t('config.provider') }}</label>
              <UiSelect
                v-model="form.model_config_data.provider"
                :options="providerOptions"
                class="w-full"
                @update:model-value="onProviderChange"
              />
            </div>
            <div>
              <label class="mb-1.5 block text-body font-medium text-ink-text">{{ t('config.modelName') }}</label>
              <UiInput
                v-model="form.model_config_data.model_name"
                placeholder="gpt-4o-mini"
                class="w-full"
              />
            </div>
            <div class="grid grid-cols-3 gap-ink-3">
              <div>
                <label class="mb-1.5 block text-body font-medium text-ink-text">Temperature</label>
                <UiInputNumber
                  :model-value="form.model_config_data.temperature"
                  :min="0"
                  :max="2"
                  :step="0.1"
                  class="w-full"
                  @update:model-value="(v) => (form.model_config_data!.temperature = v ?? 0.7)"
                />
              </div>
              <div>
                <label class="mb-1.5 block text-body font-medium text-ink-text">Top P</label>
                <UiInputNumber
                  :model-value="form.model_config_data.top_p"
                  :min="0"
                  :max="1"
                  :step="0.05"
                  class="w-full"
                  @update:model-value="(v) => (form.model_config_data!.top_p = v ?? 0.95)"
                />
              </div>
              <div>
                <label class="mb-1.5 block text-body font-medium text-ink-text">Max Tokens</label>
                <UiInputNumber
                  :model-value="form.model_config_data.max_tokens"
                  :min="64"
                  :max="4096"
                  :step="64"
                  class="w-full"
                  @update:model-value="(v) => (form.model_config_data!.max_tokens = v ?? 1024)"
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
