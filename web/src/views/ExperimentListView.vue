<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Icon } from '@iconify/vue'
import {
  experimentApi,
  type CollectMode,
  type Experiment,
} from '@/api/experimentApi'
import { experimentConfigApi, type ExperimentConfig } from '@/api/experimentConfigApi'
import {
  defaultEngineId,
  engineById,
  isValidPlayerSelection,
  maxSelectable,
  playerCountLabel,
  supportsBenchmark,
  type EngineInfo,
} from '@/utils/engineSlots'
import { firstIncompleteStep, firstRunSteps } from '@/utils/firstRun'
import { systemApi, type PreflightResult } from '@/api/systemApi'
import { toast } from '@/components/ui/toast'
import { showApiError } from '@/utils/error'
import { pickJsonFile } from '@/utils/jsonFile'
import EmptyState from '@/components/common/EmptyState.vue'
import FirstRunStepper from '@/components/common/FirstRunStepper.vue'
import ExperimentListRow from '@/components/experiment/ExperimentListRow.vue'
import UiButton from '@/components/ui/Button.vue'
import UiCheckbox from '@/components/ui/Checkbox.vue'
import UiDialog from '@/components/ui/Dialog.vue'
import UiDropdownMenu, { type DropdownMenuItemDef } from '@/components/ui/DropdownMenu.vue'
import UiInput from '@/components/ui/Input.vue'
import UiInputNumber from '@/components/ui/InputNumber.vue'
import UiSkeletonList from '@/components/ui/SkeletonList.vue'
import UiTextarea from '@/components/ui/Textarea.vue'

const { t } = useI18n()
const router = useRouter()
const loading = ref(true)
const seedingDemo = ref(false)
const creating = ref(false)
const importing = ref(false)
const createOpen = ref(false)
const createMoreOpen = ref(false)
const experiments = ref<Experiment[]>([])
const configs = ref<ExperimentConfig[]>([])
const engines = ref<EngineInfo[]>([])
const preflight = ref<PreflightResult | null>(null)
const formGameType = ref('')

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
const canUseBenchmark = computed(() => supportsBenchmark(currentEngine.value))

const requiredPlayers = computed(() => currentEngine.value?.min_players ?? 3)
const hasConfiguredProvider = computed(
  () =>
    (preflight.value?.providers ?? []).some((p) => p.configured) ||
    preflight.value?.can_collect === true,
)
const setupSteps = computed(() =>
  firstRunSteps({
    hasConfiguredProvider: hasConfiguredProvider.value,
    playerCount: configs.value.length,
    requiredPlayers: requiredPlayers.value,
    experimentCount: experiments.value.length,
  }),
)
const setupIncomplete = computed(() => firstIncompleteStep(setupSteps.value) != null)

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

const moreMenuItems = computed((): DropdownMenuItemDef[] => [
  { id: 'compare', label: t('experiment.compareMany') },
  { id: 'import', label: t('experiment.importPack') },
])

function configName(id: string): string {
  return configs.value.find((c) => c.id === id)?.name ?? id
}

function playerNames(exp: Experiment): string[] {
  return exp.player_ids.map((id) => configName(id))
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const [expRes, cfgRes, engineRes, preflightRes] = await Promise.all([
      experimentApi.list(),
      experimentConfigApi.list(),
      systemApi.listEngines().catch(() => null),
      systemApi.preflight({ scope: 'all' }).catch(() => null),
    ])
    experiments.value = expRes.data ?? []
    configs.value = cfgRes.data ?? []
    engines.value = engineRes?.data ?? []
    preflight.value = preflightRes?.data ?? null
    if (!engines.value.some((e) => e.id === formGameType.value)) {
      formGameType.value = defaultEngineId(engines.value)
    }
  } catch (e: unknown) {
    showApiError(e, t('experiment.loadFailed'))
  } finally {
    loading.value = false
  }
}

function setCollectMode(mode: CollectMode): void {
  formCollectMode.value = mode
  if (mode === 'benchmark') {
    const n = currentEngine.value?.benchmark_seed_count ?? 50
    formTarget.value = Math.min(50, Math.max(1, n))
  }
}

function openCreate(): void {
  formName.value = ''
  formNotes.value = ''
  formHypothesis.value = ''
  formTags.value = ''
  formCollectMode.value = 'free'
  formTarget.value = 10
  formGameType.value = defaultEngineId(engines.value)
  selectedConfigIds.value = configs.value.slice(0, maxPlayers.value).map((c) => c.id)
  createMoreOpen.value = false
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
      game_type: formGameType.value,
      player_ids: selectedConfigIds.value,
      target_games: Number(formTarget.value) || 10,
      collect_mode: canUseBenchmark.value ? formCollectMode.value : 'free',
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

function watchLatest(exp: Experiment): void {
  const id = exp.summary.latest_game_id
  if (!id) {
    goDetail(exp.id)
    return
  }
  void router.push(`/game/${id}`)
}

async function importPack(): Promise<void> {
  importing.value = true
  try {
    const raw = await pickJsonFile()
    if (raw == null) return
    const res = await experimentApi.importPack(raw)
    const result = res.data
    const missing = result.unconfigured_providers ?? []
    const ollama = result.requirements?.ollama_tags ?? []
    toast.success(
      t('experiment.importedPack', {
        created: result.players_created.length,
        reused: result.players_reused.length,
      }),
    )
    if (missing.length > 0) {
      toast.warning(t('experiment.importMissingProviders', { ids: missing.join(', ') }))
    } else if (ollama.length > 0) {
      toast.info(t('experiment.importOllamaTags', { tags: ollama.join(', ') }))
    }
    if (result.experiment?.id) {
      await router.push(`/experiments/${result.experiment.id}`)
      return
    }
    await load()
  } catch (e: unknown) {
    if (e instanceof Error && e.message === 'invalid json') {
      toast.error(t('experiment.importInvalidJson'))
    } else {
      showApiError(e, t('experiment.importFailed'))
    }
  } finally {
    importing.value = false
  }
}

function onMoreSelect(id: string): void {
  if (id === 'compare') {
    void router.push('/experiments/compare')
    return
  }
  if (id === 'import') void importPack()
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="page-container space-y-ink-6">
    <div class="flex flex-wrap items-center justify-end gap-ink-2">
      <UiDropdownMenu :items="moreMenuItems" @select="onMoreSelect">
        <UiButton variant="ghost" size="icon" :aria-label="t('common.more')" :loading="importing">
          <Icon icon="lucide:ellipsis" class="h-4 w-4" />
        </UiButton>
      </UiDropdownMenu>
      <UiButton @click="openCreate">
        <Icon icon="lucide:plus" class="mr-1.5 h-4 w-4" />
        {{ t('experiment.create') }}
      </UiButton>
    </div>

    <FirstRunStepper
      v-if="!loading && setupIncomplete"
      :steps="setupSteps"
      :required-players="requiredPlayers"
      :demo-loading="seedingDemo"
      @settings="router.push('/settings')"
      @players="router.push('/experiment-configs')"
      @create="openCreate"
      @demo="loadDemo"
    />

    <div v-if="loading" class="py-2">
      <UiSkeletonList :rows="6" />
    </div>

    <EmptyState
      v-else-if="experiments.length === 0 && !setupIncomplete"
      :title="t('experiment.emptyTitle')"
    >
      <template #action>
        <div class="flex flex-wrap justify-center gap-ink-2">
          <UiButton @click="openCreate">{{ t('experiment.create') }}</UiButton>
          <UiButton variant="secondary" :loading="importing" @click="importPack">
            {{ t('experiment.importPack') }}
          </UiButton>
          <UiButton variant="secondary" :loading="seedingDemo" @click="loadDemo">
            {{ t('experiment.loadDemo') }}
          </UiButton>
        </div>
      </template>
    </EmptyState>

    <div v-else-if="experiments.length > 0" class="space-y-ink-3">
      <ExperimentListRow
        v-for="exp in experiments"
        :key="exp.id"
        :experiment="exp"
        :player-names="playerNames(exp)"
        @open="goDetail(exp.id)"
        @watch="watchLatest(exp)"
      />
    </div>

    <UiDialog
      v-model:open="createOpen"
      size="lg"
      :title="t('experiment.createTitle')"
    >
      <div class="grid gap-ink-4 sm:grid-cols-2">
        <div>
          <label class="mb-1.5 block text-body font-medium text-ink-text">{{ t('common.name') }}</label>
          <UiInput
            v-model="formName"
            :placeholder="t('experiment.namePlaceholder')"
            class="w-full"
          />
        </div>
        <div>
          <label class="mb-1.5 block text-body font-medium text-ink-text">
            {{ t('experiment.targetGames') }}
          </label>
          <UiInputNumber v-model="formTarget" :min="1" :max="50" />
        </div>
        <div>
          <label class="mb-1.5 block text-body font-medium text-ink-text">{{ t('experiment.collectMode') }}</label>
          <div class="flex flex-wrap gap-ink-2">
            <UiButton
              size="sm"
              :variant="formCollectMode === 'free' ? 'primary' : 'secondary'"
              type="button"
              @click="setCollectMode('free')"
            >
              {{ t('experiment.collectModeFree') }}
            </UiButton>
            <UiButton
              size="sm"
              :variant="formCollectMode === 'benchmark' ? 'primary' : 'secondary'"
              type="button"
              :disabled="!canUseBenchmark"
              @click="setCollectMode('benchmark')"
            >
              {{ t('experiment.collectModeBenchmark') }}
            </UiButton>
          </div>
          <p v-if="formCollectMode === 'benchmark'" class="mt-1.5 text-caption text-ink-text-secondary">
            {{ t('experiment.collectModeBenchmarkHint') }}
          </p>
        </div>
        <div class="sm:col-span-2">
          <div class="mb-1.5 flex items-center justify-between">
            <label class="text-body font-medium text-ink-text">
              {{ t('experiment.pickPlayers', { n: slotsLabel }) }}
            </label>
            <span class="text-caption tabular-nums text-ink-text-muted">
              {{ selectedConfigIds.length }}/{{ maxPlayers }}
            </span>
          </div>
          <div
            v-if="configs.length === 0"
            class="rounded-ink border border-dashed border-ink-border p-ink-3 text-body text-ink-text-muted"
          >
            {{ t('experiment.noConfigs') }}
          </div>
          <div v-else class="grid max-h-56 gap-ink-2 overflow-y-auto sm:grid-cols-2">
            <div
              v-for="cfg in configs"
              :key="cfg.id"
              class="flex items-start gap-ink-2 rounded-ink border border-ink-border px-ink-3 py-ink-2 hover:bg-ink-surface-muted"
            >
              <UiCheckbox
                :model-value="selectedConfigIds.includes(cfg.id)"
                class="mt-0.5"
                :label="cfg.name"
                @update:model-value="(v) => toggleConfig(cfg.id, Boolean(v))"
              />
              <span class="min-w-0 flex-1 pt-0.5 text-caption text-ink-text-muted">
                {{ cfg.model_config.provider }} / {{ cfg.model_config.model_name }}
              </span>
            </div>
          </div>
        </div>
        <div class="sm:col-span-2">
          <button
            type="button"
            class="text-caption text-ink-text-secondary hover:text-ink-text"
            @click="createMoreOpen = !createMoreOpen"
          >
            {{ createMoreOpen ? t('common.collapse') : t('experiment.createMoreFields') }}
          </button>
          <div v-if="createMoreOpen" class="mt-ink-3 grid gap-ink-4 sm:grid-cols-2">
            <div>
              <label class="mb-1.5 block text-body font-medium text-ink-text">{{ t('experiment.hypothesis') }}</label>
              <UiTextarea
                v-model="formHypothesis"
                :rows="3"
                :placeholder="t('experiment.hypothesisPlaceholder')"
                class="w-full"
              />
            </div>
            <div>
              <label class="mb-1.5 block text-body font-medium text-ink-text">{{ t('common.notes') }}</label>
              <UiTextarea
                v-model="formNotes"
                :rows="3"
                :placeholder="t('experiment.notesPlaceholder')"
                class="w-full"
              />
            </div>
            <div class="sm:col-span-2">
              <label class="mb-1.5 block text-body font-medium text-ink-text">{{ t('experiment.tags') }}</label>
              <UiInput v-model="formTags" :placeholder="t('experiment.tagsPlaceholder')" class="w-full" />
            </div>
          </div>
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
