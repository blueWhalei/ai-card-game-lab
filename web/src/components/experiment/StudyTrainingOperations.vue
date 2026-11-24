<script setup lang="ts">
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { trainingApi, type TrainingTaskPage } from '@/api/trainingApi'
import type { OperationFilter } from '@/api/studyApi'
import { operationPosition } from '@/utils/studyOperations'
import { recordedProgress, trainingError } from '@/utils/trainingRecords'
import { formatDateTime } from '@/utils/format'
import UiButton from '@/components/ui/Button.vue'
import UiPagination from '@/components/ui/Pagination.vue'

const props = defineProps<{ studyId: string }>()
const { t } = useI18n()
const route = useRoute(),
  router = useRouter()
const position = computed(() => operationPosition(route.query))
const data = ref<TrainingTaskPage | null>(null),
  loading = ref(false),
  failed = ref(false)
const filters: OperationFilter[] = ['all', 'active', 'attention']
const knownStates = ['pending', 'exporting', 'training', 'completed', 'failed', 'cancelled']
let request = 0
async function load() {
  const token = ++request,
    selected = position.value,
    id = props.studyId
  data.value = null
  failed.value = false
  loading.value = false
  if (!selected) return
  loading.value = true
  try {
    const result = (
      await trainingApi.listTasks({
        study_id: id,
        state: selected.state,
        page: selected.page,
        page_size: 20,
      })
    ).data
    if (token !== request) return
    if (
      result.filters.study_id !== id ||
      result.filters.state !== selected.state ||
      result.page !== selected.page
    )
      throw new Error('Task scope mismatch')
    data.value = result
  } catch {
    if (token === request) failed.value = true
  } finally {
    if (token === request) loading.value = false
  }
}
function select(state: OperationFilter, page = 1) {
  void router.replace({ query: { ...route.query, task_state: state, task_page: String(page) } })
}
watch(() => [props.studyId, route.query.task_state, route.query.task_page], load, {
  immediate: true,
})
onBeforeUnmount(() => request++)
</script>

<template>
  <section class="space-y-ink-4 text-body" :aria-busy="loading">
    <p class="text-ink-text-secondary">{{ t('operations.trainingScope') }}</p>
    <div class="flex flex-wrap gap-ink-2" :aria-label="t('operations.trainingFilter')">
      <UiButton
        v-for="filter in filters"
        :key="filter"
        :variant="position?.state === filter ? 'primary' : 'secondary'"
        :aria-pressed="position?.state === filter"
        @click="select(filter)"
        >{{ t(`operations.trainingFilters.${filter}`) }}</UiButton
      >
      <UiButton variant="ghost" :disabled="loading || !position" @click="load">{{
        t('study.refresh')
      }}</UiButton>
    </div>
    <p v-if="!position" role="alert">{{ t('operations.invalidPosition') }}</p>
    <p v-if="loading" role="status">{{ t('common.loading') }}</p>
    <div v-if="failed" role="alert" class="space-y-ink-2">
      <p>{{ t('operations.trainingFailed') }}</p>
      <UiButton @click="load">{{ t('common.retry') }}</UiButton>
    </div>
    <template v-if="data">
      <p class="text-caption text-ink-text-secondary">
        {{ t('operations.trainingReadAt', { n: data.total, time: formatDateTime(data.read_at) }) }}
      </p>
      <p v-if="!data.items.length">
        {{ t(data.total ? 'operations.pageEmpty' : 'operations.trainingEmpty') }}
      </p>
      <article
        v-for="task in data.items"
        :key="task.id"
        class="space-y-ink-3 border-t border-ink-border py-ink-4"
      >
        <h3 class="break-words text-lead font-medium">{{ task.name }}</h3>
        <p class="break-words">{{ t('operations.trainingRun', { name: task.run_name }) }}</p>
        <dl class="grid gap-ink-2 sm:grid-cols-2">
          <div>
            <dt>{{ t('common.status') }}</dt>
            <dd>
              {{
                knownStates.includes(task.status)
                  ? t(`training.status.${task.status}`)
                  : t('operations.states.unknown')
              }}
            </dd>
          </div>
          <div>
            <dt>{{ t('operations.trainingProgress') }}</dt>
            <dd>
              {{
                recordedProgress(task.progress) === null
                  ? t(
                      task.progress_state === 'invalid'
                        ? 'operations.invalidProgress'
                        : 'operations.missing',
                    )
                  : `${recordedProgress(task.progress)}%`
              }}
            </dd>
          </div>
          <div class="min-w-0">
            <dt>{{ t('training.colBase') }}</dt>
            <dd class="break-words">{{ task.base_model }}</dd>
          </div>
          <div>
            <dt>{{ t('operations.trainingType') }}</dt>
            <dd>{{ task.training_type }}</dd>
          </div>
        </dl>
        <details class="space-y-ink-2">
          <summary class="cursor-pointer text-ink-primary">
            {{ t('operations.trainingDetails') }}
          </summary>
          <p class="break-all">
            {{ t('operations.trainingSource', { task: task.id, dataset: task.dataset_id }) }}
          </p>
          <p>{{ t('common.createdAt') }}：{{ formatDateTime(task.created_at) }}</p>
          <p>{{ t('operations.trainingLimit') }}</p>
          <p v-if="task.result_state === 'invalid'">{{ t('operations.invalidResult') }}</p>
          <p v-if="task.config_state === 'invalid'">{{ t('operations.invalidConfig') }}</p>
          <p v-if="trainingError(task.result)" class="whitespace-pre-wrap break-words">
            {{ t('operations.recordedError') }}：{{ trainingError(task.result) }}
          </p>
          <p v-else-if="task.status === 'failed'">{{ t('operations.noRecordedError') }}</p>
        </details>
        <RouterLink
          :to="{
            path: '/pipeline/training',
            query: {
              study_id: studyId,
              experiment_id: task.experiment_id,
              task_id: task.id,
              task_study: studyId,
              task_kind: 'training',
              task_state: data.filters.state,
              task_page: String(data.page),
            },
          }"
          class="inline-block text-ink-primary underline"
          >{{ t('operations.openTraining') }}</RouterLink
        >
      </article>
      <UiPagination
        :page="data.page"
        :page-size="data.page_size"
        :total="data.total"
        fixed-page-size
        @update:page="select(position!.state, $event)"
      />
    </template>
  </section>
</template>
