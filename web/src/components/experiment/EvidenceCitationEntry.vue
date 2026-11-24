<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute } from 'vue-router'
import { researchApi, type CitationSource } from '@/api/researchApi'
import type { ComparisonSnapshotSummary } from '@/api/experimentApi'
import { getErrorMessage } from '@/utils/error'
import { formatDateTime } from '@/utils/format'
import UiButton from '@/components/ui/Button.vue'
import UiDialog from '@/components/ui/Dialog.vue'

const props = defineProps<{ source: CitationSource }>()
const { t } = useI18n()
const route = useRoute()
const open = ref(false)
const busy = ref(false)
const error = ref('')
const traceHash = ref('')
const targets = ref<{
  items: (ComparisonSnapshotSummary & { seed?: number })[]
  next_offset: number | null
} | null>(null)
let request = 0
async function load(offset = 0) {
  const version = ++request
  const source = props.source
  busy.value = true
  error.value = ''
  try {
    const { data } =
      source.kind === 'decision'
        ? await researchApi.decisionTargets(source.id, offset)
        : source.kind === 'trace'
          ? await researchApi.traceTargets(source.id, offset)
          : await researchApi.puzzleTargets(source.packId, source.runId, offset)
    if (version !== request) return
    if (source.kind === 'decision') {
      if (!('decision_id' in data) || data.decision_id !== source.id)
        throw { code: 'EVIDENCE_PREVIEW', message: t('researchReport.status.identity_mismatch') }
    } else if (source.kind === 'trace') {
      if (
        !('trace_id' in data) ||
        data.trace_id !== source.id ||
        !/^[a-f0-9]{64}$/.test(data.source_hash)
      )
        throw { code: 'EVIDENCE_PREVIEW', message: t('traceCitation.invalid') }
      if (offset && traceHash.value !== data.source_hash) {
        targets.value = null
        throw { code: 'EVIDENCE_PREVIEW', message: t('traceCitation.changed') }
      }
      traceHash.value = data.source_hash
    } else if (
      !('pack_id' in data) ||
      data.pack_id !== source.packId ||
      data.run_id !== source.runId
    ) {
      throw { code: 'EVIDENCE_PREVIEW', message: t('puzzleCitation.invalid') }
    } else if (data.report_hash !== source.reportHash) {
      throw { code: 'EVIDENCE_PREVIEW', message: t('puzzleCitation.changedPreview') }
    }
    targets.value = {
      ...data,
      items: offset ? [...(targets.value?.items ?? []), ...data.items] : data.items,
    }
  } catch (cause) {
    if (version === request) {
      targets.value = null
      error.value = getErrorMessage(cause)
    }
  } finally {
    if (version === request) busy.value = false
  }
}
function inspect() {
  open.value = true
  targets.value = null
  void load()
}
function destination(item: ComparisonSnapshotSummary & { seed?: number }) {
  const source = props.source
  if (source.kind === 'trace')
    return {
      path: '/experiments/compare',
      query: {
        snapshot: item.id,
        review_trace: source.id,
        review_trace_hash: traceHash.value,
        report_id: route.query.report_id,
        trace_evidence: route.query.trace_evidence,
      },
    }
  if (source.kind === 'puzzle')
    return {
      path: '/experiments/compare',
      query: {
        snapshot: item.id,
        review_pack: source.packId,
        review_result: source.runId,
        review_hash: source.reportHash,
        review_page: String(source.page),
        report_id: route.query.report_id,
        puzzle_evidence: route.query.puzzle_evidence,
      },
    }
  const same = item.id === route.query.comparison_id
  return {
    path: '/experiments/compare',
    query: {
      snapshot: item.id,
      review_decision: source.id,
      seed: String(item.seed),
      turn: String(source.turn),
      scenario: same ? route.query.compare_scenario : undefined,
      report_id: same ? route.query.report_id : undefined,
      evidence: same ? route.query.evidence : undefined,
    },
  }
}
watch(
  () => JSON.stringify(props.source),
  () => {
    request++
    targets.value = null
    open.value = false
    busy.value = false
  },
)
onBeforeUnmount(() => {
  request++
})
</script>

<template>
  <UiButton variant="secondary" size="sm" @click="inspect">{{ t('evidenceEntry.open') }}</UiButton>
  <UiDialog :open="open" :title="t('evidenceEntry.title')" @update:open="open = $event">
    <div class="space-y-ink-4">
      <p>
        {{
          t(
            source.kind === 'trace'
              ? 'traceCitation.targetScope'
              : source.kind === 'puzzle'
                ? 'puzzleCitation.targetScope'
                : 'evidenceEntry.scope',
          )
        }}
      </p>
      <p v-if="busy" role="status">{{ t('common.loading') }}</p>
      <div v-if="error">
        <p role="alert">{{ error }}</p>
        <UiButton @click="load(targets?.next_offset ?? 0)">{{ t('common.retry') }}</UiButton>
      </div>
      <p v-if="targets && !targets.items.length && !busy && !error">
        {{
          t(
            source.kind === 'trace'
              ? 'traceCitation.noTargets'
              : source.kind === 'puzzle'
                ? 'puzzleCitation.noTargets'
                : 'evidenceEntry.empty',
          )
        }}
      </p>
      <ul v-if="targets" class="space-y-ink-3">
        <li v-for="item in targets.items" :key="item.id">
          <RouterLink :to="destination(item)" class="text-ink-primary hover:underline"
            >{{ item.title }} · {{ formatDateTime(item.created_at) }}</RouterLink
          >
        </li>
      </ul>
      <UiButton
        v-if="targets?.next_offset != null"
        :disabled="busy"
        @click="load(targets.next_offset)"
        >{{ t('evidenceEntry.more') }}</UiButton
      >
    </div>
  </UiDialog>
</template>
