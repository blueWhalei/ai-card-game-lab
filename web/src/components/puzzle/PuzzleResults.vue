<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import {
  puzzleApi,
  type PuzzleResult,
  type PuzzleResultList,
  type PuzzleRunReport,
  type PuzzleProbeReport,
} from '@/api/puzzleApi'
import { formatDateTime } from '@/utils/format'
import { downloadJson } from '@/utils/jsonFile'
import { downloadText } from '@/utils/exportFile'
import { reportHtml } from '@/utils/researchReport'
import UiButton from '@/components/ui/Button.vue'
import UiPagination from '@/components/ui/Pagination.vue'
import PuzzleResultDocument from './PuzzleResultDocument.vue'
import EvidenceCitationEntry from '@/components/experiment/EvidenceCitationEntry.vue'

const props = defineProps<{ packId: string; latest?: PuzzleRunReport | PuzzleProbeReport | null }>()
const route = useRoute()
const router = useRouter()
const { t, locale } = useI18n()
const list = ref<PuzzleResultList | null>(null)
const result = ref<PuzzleResult | null>(null)
const listError = ref(false)
const resultError = ref('')
const listLoading = ref(false)
const resultLoading = ref(false)
const exporting = ref(false)
const container = ref<HTMLElement | null>(null)
let listRequest = 0
let resultRequest = 0
onBeforeUnmount(() => {
  listRequest++
  resultRequest++
})
const page = computed(() => {
  const value = route.query.result_page
  if (value === undefined) return 1
  return typeof value === 'string' && /^[1-9]\d*$/.test(value) && Number(value) <= 100000
    ? Number(value)
    : null
})
const id = computed(() => route.query.result_id)
const validId = computed(
  () => typeof id.value === 'string' && /^(run|probe)_[a-f0-9]{8,32}$/.test(id.value),
)

async function loadList() {
  const token = ++listRequest
  list.value = null
  listError.value = false
  listLoading.value = false
  if (page.value === null) return
  listLoading.value = true
  try {
    const response = await puzzleApi.results(props.packId, page.value)
    if (token === listRequest) list.value = response.data
  } catch {
    if (token === listRequest) listError.value = true
  } finally {
    if (token === listRequest) listLoading.value = false
  }
}
async function loadResult() {
  const token = ++resultRequest
  result.value = null
  resultError.value = ''
  resultLoading.value = false
  if (id.value === undefined) return
  if (!validId.value) {
    resultError.value = t('puzzleHistory.invalidPosition')
    return
  }
  resultLoading.value = true
  const wanted = String(id.value)
  const pack = props.packId
  try {
    const response = await puzzleApi.result(pack, wanted)
    if (token !== resultRequest) return
    if (response.data.report.run_id !== wanted || response.data.report.pack_id !== pack)
      throw new Error('identity')
    result.value = response.data
  } catch {
    if (token === resultRequest) resultError.value = t('puzzleHistory.resultFailed')
  } finally {
    if (token === resultRequest) resultLoading.value = false
  }
}
async function select(runId: string) {
  await router.replace({ query: { ...route.query, result_id: runId } })
}
async function reset() {
  await router.replace({ query: { ...route.query, result_id: undefined, result_page: undefined } })
}
async function exportResult(kind: 'html' | 'json') {
  if (!result.value || exporting.value) return
  exporting.value = true
  try {
    const filename = `position-test-${result.value.report.run_id}`
    if (kind === 'json') await downloadJson(`${filename}.json`, result.value)
    else {
      const article = container.value?.querySelector<HTMLElement>('.research-report')
      if (article)
        await downloadText(
          `${filename}.html`,
          reportHtml(article, t('puzzleHistory.record'), locale.value),
          'html',
        )
    }
  } finally {
    exporting.value = false
  }
}
watch(() => [props.packId, page.value], loadList, { immediate: true })
watch(() => [props.packId, id.value], loadResult, { immediate: true })
watch(
  () => props.latest?.run_id,
  async (value) => {
    if (!value || props.latest?.pack_id !== props.packId) return
    await router.replace({ query: { ...route.query, result_id: value, result_page: undefined } })
    await loadList()
  },
)
</script>

<template>
  <section class="space-y-ink-4" :aria-label="t('puzzleHistory.title')">
    <RouterLink
      v-if="
        typeof route.query.report_id === 'string' && typeof route.query.puzzle_evidence === 'string'
      "
      :to="{
        name: 'research-report',
        params: { id: route.query.report_id },
        query: { puzzle_evidence: route.query.puzzle_evidence },
      }"
      class="text-body text-ink-primary"
      >{{ t('report.back') }}</RouterLink
    >
    <div class="flex flex-wrap items-center justify-between gap-ink-2">
      <h3 class="text-lead font-semibold">{{ t('puzzleHistory.title') }}</h3>
      <UiButton variant="secondary" :loading="listLoading" @click="loadList">{{
        t('puzzle.refresh')
      }}</UiButton>
    </div>
    <p class="text-caption text-ink-text-secondary">{{ t('puzzleHistory.readOnly') }}</p>
    <p v-if="listError" role="alert">{{ t('puzzleHistory.listFailed') }}</p>
    <div v-if="page === null" class="space-y-ink-2">
      <p role="alert">{{ t('puzzleHistory.invalidPosition') }}</p>
      <UiButton variant="secondary" @click="reset">{{ t('puzzleHistory.reset') }}</UiButton>
    </div>
    <template v-if="list">
      <p v-if="!list.items.length" class="text-caption">
        {{ t(list.total ? 'puzzleHistory.emptyPage' : 'puzzleHistory.empty') }}
      </p>
      <ul class="divide-y divide-ink-border">
        <li v-for="item in list.items" :key="item.run_id">
          <button
            type="button"
            class="flex w-full flex-wrap gap-ink-2 py-ink-3 text-left text-body"
            :aria-pressed="id === item.run_id"
            @click="select(item.run_id)"
          >
            <span
              >{{ t(`puzzleHistory.${item.kind}`) }} ·
              {{ item.created_at ? formatDateTime(item.created_at) : '—' }}</span
            >
            <span class="text-caption text-ink-text-secondary"
              >{{ item.run_id }} · {{ t('puzzleHistory.status.' + item.status) }}</span
            >
          </button>
        </li>
      </ul>
      <UiPagination
        :page="page ?? 1"
        :page-size="20"
        :total="list.total"
        fixed-page-size
        @update:page="router.replace({ query: { ...route.query, result_page: String($event) } })"
      />
    </template>
    <p v-if="resultLoading" role="status">{{ t('common.loading') }}</p>
    <div v-if="resultError" class="space-y-ink-2">
      <p role="alert">{{ resultError }}</p>
      <UiButton variant="secondary" @click="loadResult">{{ t('common.retry') }}</UiButton
      ><UiButton variant="ghost" @click="reset">{{ t('puzzleHistory.reset') }}</UiButton>
    </div>
    <template v-if="result">
      <div class="flex flex-wrap gap-ink-2">
        <EvidenceCitationEntry
          :source="{
            kind: 'puzzle',
            packId: result.report.pack_id,
            runId: result.report.run_id,
            reportHash: result.report_hash,
            page: page ?? 1,
          }"
        />
        <UiButton :disabled="exporting" @click="exportResult('html')">{{
          t('report.html')
        }}</UiButton
        ><UiButton variant="secondary" :disabled="exporting" @click="exportResult('json')">{{
          t('report.json')
        }}</UiButton>
      </div>
      <div ref="container">
        <PuzzleResultDocument
          :result="result"
          :page="page ?? 1"
          :report-id="typeof route.query.report_id === 'string' ? route.query.report_id : undefined"
          :citation="
            typeof route.query.puzzle_evidence === 'string'
              ? route.query.puzzle_evidence
              : undefined
          "
        />
      </div>
    </template>
  </section>
</template>
