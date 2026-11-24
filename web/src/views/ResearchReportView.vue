<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { researchApi, type ResearchReport } from '@/api/researchApi'
import ResearchReportDocument from '@/components/experiment/ResearchReportDocument.vue'
import ReportFollowup from '@/components/experiment/ReportFollowup.vue'
import UiButton from '@/components/ui/Button.vue'
import { downloadJson } from '@/utils/jsonFile'
import { downloadText } from '@/utils/exportFile'
import { reportComparisonLink, reportHtml } from '@/utils/researchReport'

const route = useRoute()
const router = useRouter()
const { t, locale } = useI18n()
const report = ref<ResearchReport | null>(null)
const container = ref<HTMLElement | null>(null)
const loading = ref(false)
const failed = ref(false)
const exporting = ref(false)
let request = 0
async function focusEvidence() {
  await nextTick()
  const puzzleIndex =
    report.value?.record.puzzle_evidence?.findIndex(
      (item) =>
        `${item.result.report.pack_id}/${item.result.report.run_id}` ===
        route.query.puzzle_evidence,
    ) ?? -1
  const index =
    report.value?.record.evidence.findIndex((item) => item.decision.id === route.query.evidence) ??
    -1
  const traceIndex =
    report.value?.record.trace_evidence?.findIndex(
      (item) => item.trace.id === route.query.trace_evidence,
    ) ?? -1
  if (index < 0 && puzzleIndex < 0 && traceIndex < 0) return
  const element = container.value?.querySelector<HTMLElement>(
    traceIndex >= 0
      ? `#report-trace-${traceIndex + 1}`
      : puzzleIndex >= 0
        ? `#report-test-${puzzleIndex + 1}`
        : `#report-evidence-${index + 1}`,
  )
  element?.scrollIntoView({ block: 'start' })
  element?.focus({ preventScroll: true })
}
async function locateEvidence(key: 'evidence' | 'puzzle_evidence' | 'trace_evidence', id: string) {
  await router.replace({ query: { [key]: id } })
  // Repeated clicks must still navigate when the location is already in the URL.
  await focusEvidence()
}
async function load() {
  const version = ++request
  const id = String(route.params.id)
  report.value = null
  loading.value = true
  failed.value = false
  try {
    const { data } = await researchApi.export(id)
    if (version !== request) return
    if (
      data.kind !== 'cardlab.research_report' ||
      data.record.id !== id ||
      data.record.comparison_id !== data.comparison.id
    )
      throw new Error('Report identity mismatch')
    report.value = data
    await focusEvidence()
  } catch {
    if (version === request) failed.value = true
  } finally {
    if (version === request) loading.value = false
  }
}
async function exportReport(kind: 'html' | 'json') {
  if (!report.value || exporting.value) return
  exporting.value = true
  try {
    if (kind === 'json') await downloadJson(`research-${report.value.record.id}.json`, report.value)
    else {
      const article = container.value?.querySelector<HTMLElement>('.research-report')
      if (article)
        await downloadText(
          `research-${report.value.record.id}.html`,
          reportHtml(article, report.value.comparison.title, locale.value),
          'html',
        )
    }
  } finally {
    exporting.value = false
  }
}
watch(() => route.params.id, load, { immediate: true })
watch(() => route.query.evidence, focusEvidence)
watch(() => route.query.puzzle_evidence, focusEvidence)
watch(() => route.query.trace_evidence, focusEvidence)
onBeforeUnmount(() => {
  request++
})
</script>

<template>
  <div class="page-container space-y-ink-4" :aria-busy="loading">
    <p v-if="loading" role="status">{{ t('common.loading') }}</p>
    <div v-else-if="failed" class="space-y-ink-3">
      <p role="alert">{{ t('report.failed') }}</p>
      <UiButton variant="secondary" @click="load">{{ t('common.retry') }}</UiButton>
    </div>
    <template v-if="report">
      <div class="flex flex-wrap items-center justify-between gap-ink-3">
        <RouterLink
          :to="
            reportComparisonLink(
              report,
              report.record.evidence.find((item) => item.decision.id === route.query.evidence)
                ?.decision,
              typeof route.query.trace_evidence === 'string'
                ? route.query.trace_evidence
                : undefined,
            )
          "
          class="text-body text-ink-primary hover:underline"
          >{{ t('researchReport.back') }}</RouterLink
        >
        <div class="flex flex-wrap gap-ink-2">
          <UiButton :disabled="exporting" @click="exportReport('html')">{{
            t('report.html')
          }}</UiButton>
          <UiButton variant="secondary" :disabled="exporting" @click="exportReport('json')">{{
            t('report.json')
          }}</UiButton>
        </div>
      </div>
      <p class="text-caption text-ink-text-secondary">{{ t('report.printHint') }}</p>
      <ReportFollowup :report="report" />
      <div ref="container">
        <ResearchReportDocument
          :report="report"
          @locate="locateEvidence('evidence', $event)"
          @locate-trace="locateEvidence('trace_evidence', $event)"
          @locate-puzzle="locateEvidence('puzzle_evidence', $event)"
        />
      </div>
    </template>
  </div>
</template>
