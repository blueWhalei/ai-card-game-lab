<script setup lang="ts">
import { onBeforeUnmount, ref, computed, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { studyApi, type OperationFilter, type StudyOperations } from '@/api/studyApi'
import { operationPosition } from '@/utils/studyOperations'
import { formatDateTime } from '@/utils/format'
import UiButton from '@/components/ui/Button.vue'
import UiPagination from '@/components/ui/Pagination.vue'

const props = defineProps<{ studyId: string }>()
const { t } = useI18n()
const route = useRoute(),
  router = useRouter()
const position = computed(() => operationPosition(route.query))
const data = ref<StudyOperations | null>(null)
const loading = ref(false),
  failed = ref(false)
let request = 0
const filters: OperationFilter[] = ['all', 'active', 'attention']
const fields = ['prompt_tokens', 'completion_tokens', 'total_tokens'] as const
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
    const result = (await studyApi.operations(id, selected.state, selected.page)).data
    if (token !== request) return
    if (result.study_id !== id || result.state !== selected.state || result.page !== selected.page)
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
    <p class="text-ink-text-secondary">{{ t('operations.scope') }}</p>
    <div class="flex flex-wrap gap-ink-2" :aria-label="t('operations.filter')">
      <UiButton
        v-for="filter in filters"
        :key="filter"
        :variant="position?.state === filter ? 'primary' : 'secondary'"
        :aria-pressed="position?.state === filter"
        @click="select(filter)"
        >{{ t(`operations.filters.${filter}`) }}</UiButton
      >
      <UiButton variant="ghost" :disabled="loading || !position" @click="load">{{
        t('study.refresh')
      }}</UiButton>
    </div>
    <p v-if="!position" role="alert">{{ t('operations.invalidPosition') }}</p>
    <p v-if="loading" role="status">{{ t('common.loading') }}</p>
    <div v-if="failed" role="alert" class="space-y-ink-2">
      <p>{{ t('operations.failed') }}</p>
      <UiButton @click="load">{{ t('common.retry') }}</UiButton>
    </div>
    <template v-if="data">
      <p class="text-caption text-ink-text-secondary">
        {{ t('operations.readAt', { time: formatDateTime(data.read_at), n: data.total }) }}
      </p>
      <p v-if="!data.items.length">
        {{ t(data.total ? 'operations.pageEmpty' : 'operations.empty') }}
      </p>
      <article
        v-for="run in data.items"
        :key="run.id"
        class="space-y-ink-3 border-t border-ink-border py-ink-4"
      >
        <h3 class="break-words text-lead font-medium">{{ run.name }}</h3>
        <p class="text-caption text-ink-text-secondary">
          {{ t('operations.gameCount', { n: run.game_count, target: run.target_games }) }}
        </p>
        <dl class="grid grid-cols-2 gap-ink-2">
          <template v-for="(count, key) in run.states" :key="key">
            <div v-if="count" class="flex flex-wrap justify-between gap-ink-2">
              <dt>{{ t(`operations.states.${key}`) }}</dt>
              <dd>{{ count }}</dd>
            </div>
          </template>
        </dl>
        <p v-if="run.no_bid_count" class="text-caption">
          {{ t('operations.noBid', { n: run.no_bid_count }) }}
        </p>
        <p
          v-if="run.states.failed || run.states.interrupted || run.states.unknown"
          class="text-ink-text-secondary"
        >
          {{ t('operations.recovery') }}
        </p>
        <details class="space-y-ink-3">
          <summary class="cursor-pointer text-ink-primary">
            {{ t('operations.usage', { n: run.trace_count }) }}
          </summary>
          <p class="text-caption text-ink-text-secondary">{{ t('operations.usageScope') }}</p>
          <dl class="space-y-ink-3">
            <div v-for="field in fields" :key="field">
              <dt class="font-medium">{{ t(`operations.fields.${field}`) }}</dt>
              <dd class="tabular-nums">
                {{
                  run.usage[field].overflow
                    ? t('operations.overflow')
                    : (run.usage[field].value ?? t('operations.missing'))
                }}
              </dd>
              <dd class="text-caption text-ink-text-secondary">
                {{
                  t('operations.coverage', {
                    n: run.trace_count,
                    valid: run.usage[field].recorded_count,
                    missing: run.usage[field].missing_count,
                    invalid: run.usage[field].invalid_count,
                  })
                }}
              </dd>
            </div>
          </dl>
        </details>
        <RouterLink
          :to="{
            path: `/experiments/${encodeURIComponent(run.id)}`,
            query: { task_study: studyId, task_state: data.state, task_page: String(data.page) },
          }"
          class="inline-block text-ink-primary underline"
          >{{ t('operations.openRun') }}</RouterLink
        >
      </article>
      <UiPagination
        :page="data.page"
        :page-size="data.page_size"
        :total="data.total"
        fixed-page-size
        @update:page="select(data.state, $event)"
      />
    </template>
  </section>
</template>
