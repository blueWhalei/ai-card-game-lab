<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { studyApi, type StudyDetail } from '@/api/studyApi'
import { experimentApi, type Experiment } from '@/api/experimentApi'
import { showApiError } from '@/utils/error'
import { formatDateTime } from '@/utils/format'
import ExperimentListRow from '@/components/experiment/ExperimentListRow.vue'
import UiButton from '@/components/ui/Button.vue'
import UiCheckbox from '@/components/ui/Checkbox.vue'
import UiDialog from '@/components/ui/Dialog.vue'
import UiSkeletonList from '@/components/ui/SkeletonList.vue'
import ResearchOperations from '@/components/experiment/ResearchOperations.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const studyId = computed(() => String(route.params.id))
const operationsOpen = computed(() => route.query.panel === 'operations')
function showOperations(open: boolean) {
  void router.replace({ query: { ...route.query, panel: open ? 'operations' : undefined } })
}
const study = ref<StudyDetail | null>(null)
const loading = ref(true)
const failed = ref(false)
const selected = ref<string[]>([])
const attachOpen = ref(false)
const attachLoading = ref(false)
const attachFailed = ref(false)
const attaching = ref('')
const unassigned = ref<Experiment[]>([])
let request = 0
async function load(): Promise<void> {
  const current = ++request
  loading.value = true
  failed.value = false
  try {
    const { data } = await studyApi.get(studyId.value)
    if (current !== request) return
    study.value = data
    selected.value = selected.value.filter((id) => data.runs.some((run) => run.id === id))
  } catch {
    if (current === request) failed.value = true
  } finally {
    if (current === request) loading.value = false
  }
}
function selectRun(id: string, checked: boolean): void {
  selected.value = checked
    ? [...new Set([...selected.value, id])].slice(0, 5)
    : selected.value.filter((item) => item !== id)
}
async function openAttach(): Promise<void> {
  attachOpen.value = true
  attachLoading.value = true
  attachFailed.value = false
  try {
    const { data } = await experimentApi.list()
    unassigned.value = data.filter((run) => run.study_id === null)
  } catch {
    attachFailed.value = true
  } finally {
    attachLoading.value = false
  }
}
async function attach(id: string): Promise<void> {
  if (attaching.value) return
  attaching.value = id
  try {
    await studyApi.attach(studyId.value, id)
    unassigned.value = unassigned.value.filter((run) => run.id !== id)
    await load()
  } catch (error) {
    showApiError(error, t('study.attachFailed'))
  } finally {
    attaching.value = ''
  }
}
watch(
  studyId,
  () => {
    study.value = null
    selected.value = []
    attachOpen.value = false
    void load()
  },
  { immediate: true },
)
</script>

<template>
  <div class="page-container space-y-ink-6">
    <div class="flex items-center justify-between gap-3">
      <RouterLink to="/" class="text-body text-ink-primary hover:underline"
        >← {{ t('study.allResearch') }}</RouterLink
      ><UiButton variant="ghost" :loading="loading" @click="load">{{
        t('study.refresh')
      }}</UiButton>
    </div>
    <div v-if="failed" role="alert" class="space-y-3 py-8">
      <p>{{ t('study.loadFailed') }}</p>
      <UiButton variant="secondary" @click="load">{{ t('common.retry') }}</UiButton>
    </div>
    <UiSkeletonList v-else-if="loading && !study" :rows="5" />
    <template v-else-if="study">
      <header class="max-w-4xl border-l-2 border-ink-primary pl-5">
        <p class="text-caption text-ink-text-muted">{{ t('study.question') }}</p>
        <h1 class="mt-2 break-words text-headline font-semibold">{{ study.title }}</h1>
        <p class="mt-3 whitespace-pre-wrap break-words text-lead text-ink-text-secondary">
          {{ study.question || t('study.noQuestion') }}
        </p>
      </header>
      <div class="flex flex-wrap gap-3">
        <UiButton variant="secondary" @click="showOperations(true)">{{
          t('operations.title')
        }}</UiButton>
        <UiButton variant="secondary" @click="router.push(`/research/${study.id}/prompt-ab`)">{{
          t('promptDesign.title')
        }}</UiButton>
        <UiButton
          @click="router.push({ path: '/experiments', query: { study: study.id, create: '1' } })"
          >{{ t('study.newRun') }}</UiButton
        >
        <UiButton
          v-if="study.runs[0]"
          variant="secondary"
          @click="router.push(`/experiments/${study.runs[0].id}`)"
          >{{ t('study.continueRun') }}</UiButton
        >
        <UiButton variant="ghost" @click="openAttach">{{ t('study.attach') }}</UiButton>
      </div>
      <UiDialog
        :open="operationsOpen"
        :title="t('operations.title')"
        placement="side"
        size="wide"
        @update:open="showOperations"
      >
        <ResearchOperations v-if="operationsOpen" :study-id="study.id" />
      </UiDialog>
      <div class="grid gap-8 xl:grid-cols-[minmax(0,3fr)_minmax(260px,1fr)]">
        <section class="min-w-0" :aria-label="t('study.runSection')">
          <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 class="text-title font-medium">{{ t('study.runSection') }}</h2>
              <p class="mt-1 text-caption text-ink-text-muted">{{ t('study.runHint') }}</p>
            </div>
            <UiButton
              variant="secondary"
              :disabled="selected.length < 2"
              @click="
                router.push({ path: '/experiments/compare', query: { ids: selected.join(',') } })
              "
              >{{ t('study.compare') }} · {{ selected.length }}</UiButton
            >
          </div>
          <p v-if="selected.length" class="mb-3 text-caption text-ink-text-secondary" role="status">
            {{ t('study.selected', { n: selected.length }) }}
          </p>
          <div v-if="!study.runs.length" class="border-t border-dashed border-ink-border py-8">
            <h3 class="text-lead">{{ t('study.noRuns') }}</h3>
            <p class="mt-2 text-body text-ink-text-muted">{{ t('study.noRunsHint') }}</p>
          </div>
          <div v-else class="divide-y divide-ink-border border-y border-ink-border">
            <div v-for="run in study.runs" :key="run.id" class="min-w-0 py-3">
              <UiCheckbox
                class="mb-2"
                :model-value="selected.includes(run.id)"
                :disabled="!selected.includes(run.id) && selected.length >= 5"
                :label="t('study.selectRun', { name: run.name })"
                @update:model-value="selectRun(run.id, $event)"
              />
              <ExperimentListRow
                :experiment="run"
                :player-names="
                  run.player_ids.map(
                    (id) => run.protocol?.solver.players.find((p) => p.id === id)?.name ?? id,
                  )
                "
                @open="router.push(`/experiments/${run.id}`)"
                @watch="
                  router.push(
                    run.summary.latest_game_id
                      ? `/game/${run.summary.latest_game_id}`
                      : `/experiments/${run.id}`,
                  )
                "
              />
            </div>
          </div>
        </section>
        <aside
          class="min-w-0 border-t border-ink-border pt-5 xl:border-t-0 xl:border-l xl:pt-0 xl:pl-6"
        >
          <h2 class="text-title font-medium">{{ t('study.records') }}</h2>
          <p
            v-if="!study.comparisons.length"
            class="mt-4 text-body leading-relaxed text-ink-text-muted"
          >
            {{ t('study.noRecords') }}
          </p>
          <RouterLink
            v-for="comparison in study.comparisons"
            :key="comparison.id"
            :to="{ path: '/experiments/compare', query: { snapshot: comparison.id } }"
            class="mt-4 block border-b border-ink-border pb-4 hover:text-ink-primary"
          >
            <span class="block break-words text-body font-medium">{{ comparison.title }}</span
            ><span class="mt-1 block text-caption text-ink-text-muted">{{
              comparison.revision_count
                ? t('study.versions', { n: comparison.revision_count })
                : t('study.snapshotOnly')
            }}</span
            ><time class="mt-1 block text-caption text-ink-text-muted">{{
              formatDateTime(comparison.created_at)
            }}</time>
          </RouterLink>
        </aside>
      </div>
    </template>
    <UiDialog
      v-model:open="attachOpen"
      :title="t('study.attach')"
      :description="t('study.attachHint')"
    >
      <UiSkeletonList v-if="attachLoading" :rows="3" />
      <div v-else-if="attachFailed" role="alert">
        <p>{{ t('study.loadFailed') }}</p>
        <UiButton variant="secondary" @click="openAttach">{{ t('common.retry') }}</UiButton>
      </div>
      <p v-else-if="!unassigned.length" class="text-body text-ink-text-muted">
        {{ t('study.noUnassigned') }}
      </p>
      <div v-else class="space-y-3">
        <div
          v-for="run in unassigned"
          :key="run.id"
          class="flex items-center justify-between gap-3"
        >
          <span class="min-w-0 break-words text-body">{{ run.name }}</span
          ><UiButton
            size="sm"
            variant="secondary"
            :loading="attaching === run.id"
            :disabled="!!attaching"
            @click="attach(run.id)"
            >{{ t('study.add') }}</UiButton
          >
        </div>
      </div>
    </UiDialog>
  </div>
</template>
