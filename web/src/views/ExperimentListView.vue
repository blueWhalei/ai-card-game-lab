<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Icon } from '@iconify/vue'
import { experimentApi, type Experiment } from '@/api/experimentApi'
import { experimentConfigApi, type ExperimentConfig } from '@/api/experimentConfigApi'
import { studyApi, type Study } from '@/api/studyApi'
import { systemApi, type EngineInfo } from '@/api/systemApi'
import CreateExperimentDialog from '@/components/experiment/CreateExperimentDialog.vue'
import { toast } from '@/components/ui/toast'
import { showApiError } from '@/utils/error'
import { pickJsonFile } from '@/utils/jsonFile'
import EmptyState from '@/components/common/EmptyState.vue'
import ExperimentListRow from '@/components/experiment/ExperimentListRow.vue'
import UiButton from '@/components/ui/Button.vue'
import UiDropdownMenu, { type DropdownMenuItemDef } from '@/components/ui/DropdownMenu.vue'
import UiSkeletonList from '@/components/ui/SkeletonList.vue'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const study = ref<Study | null>(null)
const studyId = computed(() =>
  typeof route.query.study === 'string' ? route.query.study : undefined,
)
const loadFailed = ref(false)
const loading = ref(true)
const seedingDemo = ref(false)
const importing = ref(false)
const createOpen = ref(false)
const experiments = ref<Experiment[]>([])
const configs = ref<ExperimentConfig[]>([])
const engines = ref<EngineInfo[]>([])
const initialLineup = computed(() => {
  if (route.query.preset === 'prompt-baseline') return 'prompt-baseline'
  return experiments.value.length === 0 || configs.value.length === 0 ? 'offline' : 'custom'
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

let loadVersion = 0
async function load(): Promise<void> {
  const version = ++loadVersion
  loading.value = true
  loadFailed.value = false
  try {
    const [expRes, cfgRes, engineRes, studyRes] = await Promise.all([
      experimentApi.list(),
      experimentConfigApi.list(),
      systemApi.listEngines(),
      studyId.value ? studyApi.get(studyId.value) : Promise.resolve(null),
    ])
    if (version !== loadVersion) return
    study.value = studyRes?.data ?? null
    experiments.value = studyRes ? studyRes.data.runs : expRes.data
    configs.value = cfgRes.data ?? []
    engines.value = engineRes.data
  } catch (e: unknown) {
    if (version !== loadVersion) return
    loadFailed.value = true
    showApiError(e, t('experiment.loadFailed'))
  } finally {
    if (version === loadVersion) loading.value = false
  }
}

function openCreate() {
  if (!loading.value && !loadFailed.value) createOpen.value = true
}

function updateConfig(config: ExperimentConfig) {
  configs.value = [...configs.value.filter((c) => c.id !== config.id), config]
}

async function loadDemo(): Promise<void> {
  seedingDemo.value = true
  try {
    const res = await systemApi.seedDemo()
    const experimentId = res.data.experiment_id
    toast.success(res.data.created ? t('experiment.demoLoaded') : t('experiment.demoReady'))
    await router.push(`/experiments/${experimentId}`)
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

watch(
  () => [route.query.study, route.query.create, route.query.preset],
  async () => {
    createOpen.value = false
    study.value = null
    experiments.value = []
    const version = loadVersion + 1
    await load()
    if (version === loadVersion && route.query.create === '1') openCreate()
  },
  { immediate: true },
)
</script>

<template>
  <div class="page-container research-page space-y-ink-6">
    <RouterLink
      v-if="study"
      :to="`/research/${study.id}`"
      class="block text-body text-ink-primary hover:underline"
      >← {{ t('study.inStudy', { name: study.title }) }}</RouterLink
    >
    <div v-if="loadFailed" role="alert" class="space-y-3">
      <p>{{ t('study.loadFailed') }}</p>
      <UiButton variant="secondary" @click="load">{{ t('common.retry') }}</UiButton>
    </div>
    <div class="flex flex-wrap items-center justify-between gap-ink-4">
      <p class="text-body text-ink-text-muted">
        {{ t('experiment.libraryCount', { n: experiments.length }) }}
      </p>
      <div class="flex flex-wrap items-center gap-ink-2">
        <UiButton
          variant="ghost"
          data-testid="load-demo-experiment"
          :loading="seedingDemo"
          @click="loadDemo"
        >
          {{ t('experiment.loadDemo') }}
        </UiButton>
        <UiDropdownMenu :items="moreMenuItems" @select="onMoreSelect">
          <UiButton variant="ghost" size="icon" :aria-label="t('common.more')" :loading="importing">
            <Icon icon="lucide:ellipsis" class="h-4 w-4" />
          </UiButton>
        </UiDropdownMenu>
        <UiButton :disabled="loading || loadFailed" @click="openCreate">
          <Icon icon="lucide:plus" class="mr-1.5 h-4 w-4" />
          {{ t('experiment.create') }}
        </UiButton>
      </div>
    </div>

    <div v-if="loading" class="py-2">
      <UiSkeletonList :rows="6" />
    </div>

    <EmptyState
      v-else-if="!loadFailed && experiments.length === 0"
      :title="t('experiment.emptyTitle')"
      :description="t('experiment.emptyHint')"
    >
      <template #action>
        <div class="flex flex-wrap justify-center gap-ink-2">
          <UiButton @click="openCreate">{{ t('experiment.create') }}</UiButton>
          <UiButton variant="secondary" :loading="importing" @click="importPack">
            {{ t('experiment.importPack') }}
          </UiButton>
          <UiButton
            variant="secondary"
            data-testid="load-demo-experiment"
            :loading="seedingDemo"
            @click="loadDemo"
          >
            {{ t('experiment.loadDemo') }}
          </UiButton>
        </div>
      </template>
    </EmptyState>

    <div
      v-else-if="experiments.length > 0"
      class="overflow-hidden rounded-ink-md border border-ink-border bg-ink-surface divide-y divide-ink-border"
    >
      <ExperimentListRow
        v-for="exp in experiments"
        :key="exp.id"
        :experiment="exp"
        :player-names="playerNames(exp)"
        @open="goDetail(exp.id)"
        @watch="watchLatest(exp)"
      />
    </div>

    <CreateExperimentDialog
      v-if="createOpen"
      :study="study"
      :configs="configs"
      :engines="engines"
      :initial-lineup="initialLineup"
      @close="createOpen = false"
      @created="
        (id) => {
          createOpen = false
          goDetail(id)
        }
      "
      @player-saved="updateConfig"
    />
  </div>
</template>
