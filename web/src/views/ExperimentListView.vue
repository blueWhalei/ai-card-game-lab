<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Icon } from '@iconify/vue'
import {
  experimentApi,
  experimentStatusLabel,
  isBenchmarkExperiment,
  EXPERIMENT_STATUS_VARIANT,
  type CollectMode,
  type Experiment,
} from '@/api/experimentApi'
import { experimentConfigApi, type ExperimentConfig } from '@/api/experimentConfigApi'
import {
  engineById,
  isValidPlayerSelection,
  maxSelectable,
  playerCountLabel,
  type EngineInfo,
} from '@/utils/engineSlots'
import { systemApi } from '@/api/systemApi'
import { toast } from '@/components/ui/toast'
import { showApiError } from '@/utils/error'
import { formatDateTime } from '@/utils/format'
import EmptyState from '@/components/common/EmptyState.vue'
import NameChips from '@/components/common/NameChips.vue'
import UiBadge from '@/components/ui/Badge.vue'
import UiButton from '@/components/ui/Button.vue'
import UiCheckbox from '@/components/ui/Checkbox.vue'
import UiDialog from '@/components/ui/Dialog.vue'
import UiInput from '@/components/ui/Input.vue'
import UiInputNumber from '@/components/ui/InputNumber.vue'
import UiSkeletonList from '@/components/ui/SkeletonList.vue'
import UiTable from '@/components/ui/Table.vue'
import type { TableColumn } from '@/components/ui/Table.vue'
import UiTextarea from '@/components/ui/Textarea.vue'

const { t } = useI18n()

type ExperimentRow = Experiment & Record<string, unknown>

const experimentColumns = computed((): TableColumn<ExperimentRow>[] => [
  { key: 'name', label: t('common.name') },
  { key: 'status', label: t('common.status'), class: 'w-28' },
  { key: 'progress', label: t('common.progress'), class: 'w-24' },
  { key: 'tags', label: t('experiment.tags'), class: 'hidden w-32 md:table-cell' },
  { key: 'players', label: t('common.players') },
  { key: 'summary_extra', label: t('experiment.summary'), class: 'hidden w-40 md:table-cell' },
  { key: 'created_at', label: t('common.createdAt'), class: 'hidden w-44 md:table-cell' },
])

const experimentRows = computed(() => experiments.value as ExperimentRow[])

const router = useRouter()
const loading = ref(true)
const seedingDemo = ref(false)
const creating = ref(false)
const createOpen = ref(false)
const experiments = ref<Experiment[]>([])
const configs = ref<ExperimentConfig[]>([])
const engines = ref<EngineInfo[]>([])
const formGameType = ref('doudizhu')

const formName = ref('')
const formNotes = ref('')
const formHypothesis = ref('')
const formTags = ref('')
const formCollectMode = ref<CollectMode>('free')
const formTarget = ref(10)
const selectedConfigIds = ref<string[]>([])

const currentEngine = computed(() => engineById(engines.value, formGameType.value))
const slotsLabel = computed(() => playerCountLabel(currentEngine.value))
const maxPlayers = computed(() => maxSelectable(currentEngine.value))

const canSubmit = computed(() => {
  const target = Number(formTarget.value)
  return (
    formName.value.trim().length > 0 &&
    isValidPlayerSelection(selectedConfigIds.value.length, currentEngine.value) &&
    Number.isFinite(target) &&
    target >= 1 &&
    target <= 50
  )
})

function configName(id: string): string {
  return configs.value.find((c) => c.id === id)?.name ?? id
}

function progressText(exp: Experiment): string {
  const s = exp.summary
  return `${s.finished_games}/${s.target_games}`
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const [expRes, cfgRes, engineRes] = await Promise.all([
      experimentApi.list(),
      experimentConfigApi.list(),
      systemApi.listEngines().catch(() => null),
    ])
    experiments.value = expRes.data ?? []
    configs.value = cfgRes.data ?? []
    engines.value = engineRes?.data ?? []
  } catch (e: unknown) {
    showApiError(e, t('experiment.loadFailed'))
  } finally {
    loading.value = false
  }
}

function openCreate(): void {
  formName.value = ''
  formNotes.value = ''
  formHypothesis.value = ''
  formTags.value = ''
  formCollectMode.value = 'free'
  formTarget.value = 10
  selectedConfigIds.value = configs.value.slice(0, maxPlayers.value).map((c) => c.id)
  createOpen.value = true
}

function toggleConfig(id: string, checked: boolean): void {
  if (checked) {
    if (selectedConfigIds.value.includes(id)) return
    if (selectedConfigIds.value.length >= maxPlayers.value) {
      toast.warning(t('experiment.needExactPlayers', { n: slotsLabel.value }))
      return
    }
    selectedConfigIds.value = [...selectedConfigIds.value, id]
    return
  }
  selectedConfigIds.value = selectedConfigIds.value.filter((x) => x !== id)
}

async function submitCreate(): Promise<void> {
  if (!canSubmit.value) return
  creating.value = true
  try {
    const tags = formTags.value
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
      .slice(0, 20)
    const res = await experimentApi.create({
      name: formName.value.trim(),
      notes: formNotes.value.trim(),
      hypothesis: formHypothesis.value.trim(),
      tags,
      game_type: 'doudizhu',
      player_ids: selectedConfigIds.value,
      target_games: Number(formTarget.value) || 10,
      collect_mode: formCollectMode.value,
    })
    createOpen.value = false
    toast.success(t('experiment.created'))
    await router.push(`/experiments/${res.data.id}`)
  } catch (e: unknown) {
    showApiError(e, t('experiment.createFailed'))
  } finally {
    creating.value = false
  }
}

async function loadDemo(): Promise<void> {
  seedingDemo.value = true
  try {
    const res = await systemApi.seedDemo()
    const gameId = res.data.game_id
    toast.success(res.data.created ? t('experiment.demoLoaded') : t('experiment.demoReady'))
    await router.push(`/game/${gameId}`)
  } catch (e: unknown) {
    showApiError(e, t('experiment.demoFailed'))
  } finally {
    seedingDemo.value = false
  }
}

function goDetail(id: string): void {
  void router.push(`/experiments/${id}`)
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="page-container space-y-6">
    <div class="flex flex-wrap items-center justify-end gap-2">
      <UiButton variant="secondary" @click="router.push('/experiments/compare')">
        {{ t('experiment.compare') }}
      </UiButton>
      <UiButton variant="secondary" :loading="seedingDemo" @click="loadDemo">
        {{ t('experiment.loadDemo') }}
      </UiButton>
      <UiButton @click="openCreate">
        <Icon icon="lucide:plus" class="mr-1.5 h-4 w-4" />
        {{ t('experiment.create') }}
      </UiButton>
    </div>

    <div v-if="loading" class="py-2">
      <UiSkeletonList :rows="6" />
    </div>

    <EmptyState
      v-else-if="experiments.length === 0"
      :title="t('experiment.emptyTitle')"
    >
      <template #action>
        <div class="flex flex-wrap justify-center gap-2">
          <UiButton @click="openCreate">{{ t('experiment.create') }}</UiButton>
          <UiButton variant="secondary" :loading="seedingDemo" @click="loadDemo">
            {{ t('experiment.loadDemo') }}
          </UiButton>
        </div>
      </template>
    </EmptyState>

    <UiTable
      v-else
      :columns="experimentColumns"
      :rows="experimentRows"
      row-key="id"
    >
      <template #cell-name="{ row }">
        <div class="flex flex-wrap items-center gap-1.5">
          <button
            type="button"
            class="text-left font-medium text-ink-primary hover:underline"
            @click="goDetail(String(row.id))"
          >
            {{ row.name }}
          </button>
          <UiBadge v-if="isBenchmarkExperiment(row as Experiment)" variant="accent" class="text-xs">
            {{ t('experiment.modeBenchmark') }}
          </UiBadge>
        </div>
      </template>
      <template #cell-tags="{ row }">
        <span v-if="!(row.tags as string[])?.length" class="text-ink-text-muted">{{ t('common.dash') }}</span>
        <span v-else class="truncate text-xs text-ink-text-secondary" :title="(row.tags as string[]).join(', ')">
          {{ (row.tags as string[]).join(', ') }}
        </span>
      </template>
      <template #cell-status="{ row }">
        <UiBadge :variant="EXPERIMENT_STATUS_VARIANT[row.summary.status]">
          {{ experimentStatusLabel(row.summary.status) }}
        </UiBadge>
      </template>
      <template #cell-progress="{ row }">
        <span class="tabular-nums text-sm">{{ progressText(row as Experiment) }}</span>
      </template>
      <template #cell-players="{ row }">
        <NameChips :names="(row.player_ids as string[]).map((pid) => configName(pid))" />
      </template>
      <template #cell-summary_extra="{ row }">
        <span class="text-sm text-ink-text-secondary">
          {{
            t('experiment.trainUsableWins', {
              usable: row.summary.train_usable_decisions,
              winners: row.summary.games_with_winner,
            })
          }}
        </span>
      </template>
      <template #cell-created_at="{ row }">
        {{ formatDateTime(String(row.created_at)) }}
      </template>
    </UiTable>

    <UiDialog
      v-model:open="createOpen"
      :title="t('experiment.createTitle')"
    >
      <div class="space-y-4">
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-text">{{ t('common.name') }}</label>
          <UiInput
            v-model="formName"
            :placeholder="t('experiment.namePlaceholder')"
            class="w-full"
          />
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-text">{{ t('experiment.hypothesis') }}</label>
          <UiTextarea
            v-model="formHypothesis"
            :rows="2"
            :placeholder="t('experiment.hypothesisPlaceholder')"
            class="w-full"
          />
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-text">{{ t('common.notes') }}</label>
          <UiTextarea
            v-model="formNotes"
            :rows="2"
            :placeholder="t('experiment.notesPlaceholder')"
            class="w-full"
          />
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-text">{{ t('experiment.tags') }}</label>
          <UiInput v-model="formTags" :placeholder="t('experiment.tagsPlaceholder')" class="w-full" />
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-text">{{ t('experiment.collectMode') }}</label>
          <div class="flex flex-wrap gap-2">
            <UiButton
              size="sm"
              :variant="formCollectMode === 'free' ? 'primary' : 'secondary'"
              type="button"
              @click="formCollectMode = 'free'"
            >
              {{ t('experiment.collectModeFree') }}
            </UiButton>
            <UiButton
              size="sm"
              :variant="formCollectMode === 'benchmark' ? 'primary' : 'secondary'"
              type="button"
              @click="formCollectMode = 'benchmark'"
            >
              {{ t('experiment.collectModeBenchmark') }}
            </UiButton>
          </div>
          <p v-if="formCollectMode === 'benchmark'" class="mt-1.5 text-xs text-ink-text-secondary">
            {{ t('experiment.collectModeBenchmarkHint') }}
          </p>
        </div>
        <div>
          <div class="mb-1.5 flex items-center justify-between">
            <label class="text-sm font-medium text-ink-text">
              {{ t('experiment.pickPlayers', { n: slotsLabel }) }}
            </label>
            <span class="text-xs text-ink-text-muted">{{ selectedConfigIds.length }}/{{ maxPlayers }}</span>
          </div>
          <div
            v-if="configs.length === 0"
            class="rounded-ink border border-dashed border-ink-border p-3 text-sm text-ink-text-muted"
          >
            {{ t('experiment.noConfigs') }}
          </div>
          <div v-else class="max-h-48 space-y-2 overflow-y-auto">
            <div
              v-for="cfg in configs"
              :key="cfg.id"
              class="flex items-start gap-2 rounded-ink border border-ink-border px-3 py-2 hover:bg-ink-surface-muted"
            >
              <UiCheckbox
                :model-value="selectedConfigIds.includes(cfg.id)"
                class="mt-0.5"
                :label="cfg.name"
                @update:model-value="(v) => toggleConfig(cfg.id, Boolean(v))"
              />
              <span class="min-w-0 flex-1 pt-0.5 text-xs text-ink-text-muted">
                {{ cfg.model_config.provider }} / {{ cfg.model_config.model_name }}
              </span>
            </div>
          </div>
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-text">
            {{ t('experiment.targetGames') }}
          </label>
          <UiInputNumber v-model="formTarget" :min="1" :max="50" />
        </div>
      </div>
      <template #footer>
        <UiButton variant="secondary" @click="createOpen = false">{{ t('common.cancel') }}</UiButton>
        <UiButton :disabled="!canSubmit" :loading="creating" @click="submitCreate">
          {{ t('experiment.createAndOpen') }}
        </UiButton>
      </template>
    </UiDialog>
  </div>
</template>
