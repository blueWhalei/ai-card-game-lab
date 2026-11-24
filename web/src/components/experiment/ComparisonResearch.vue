<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute } from 'vue-router'
import {
  researchApi,
  type EvidenceCandidate,
  type ResearchVersion,
  type ResearchVersionSummary,
} from '@/api/researchApi'
import ComparisonReplay from '@/components/experiment/ComparisonReplay.vue'
import ComparisonDecision from '@/components/experiment/ComparisonDecision.vue'
import ComparisonPuzzleEvidence from './ComparisonPuzzleEvidence.vue'
import EvidenceCiteButton from './EvidenceCiteButton.vue'
import DecisionEvidenceReview from './DecisionEvidenceReview.vue'
import PuzzleEvidenceReview from './PuzzleEvidenceReview.vue'
import TraceEvidenceReview from './TraceEvidenceReview.vue'
import type { PuzzleEvidenceReference, TraceEvidenceReference } from '@/api/researchApi'
import UiButton from '@/components/ui/Button.vue'
import UiTextarea from '@/components/ui/Textarea.vue'
import UiDialog from '@/components/ui/Dialog.vue'
import { downloadJson } from '@/utils/jsonFile'
import { getErrorMessage } from '@/utils/error'
import { usePersistentDraft } from '@/composables/usePersistentDraft'
import DraftStatus from '@/components/common/DraftStatus.vue'
const route = useRoute()
const props = withDefaults(
  defineProps<{ comparisonId: string; paired: boolean; playerNames?: Record<string, string> }>(),
  { playerNames: () => ({}) },
)
const { t } = useI18n()
const versions = ref<ResearchVersionSummary[]>([])
const selected = ref<ResearchVersion | null>(null)
const candidates = ref<EvidenceCandidate[]>([])
const total = ref(0)
const offset = ref(0)
const busy = ref(false)
const error = ref('')
const panel = ref<'editor' | 'history' | null>(null)
const selectedCandidateId = ref('')
const candidate = computed(
  () =>
    candidates.value.find((item) => item.id === selectedCandidateId.value) ?? candidates.value[0],
)
const { session, flush } = usePersistentDraft('comparison', props.comparisonId)
const draft = computed(() => (session.content?.kind === 'comparison' ? session.content : null))
function textField(field: 'observations' | 'interpretation' | 'limitations') {
  return computed({
    get: () => draft.value?.[field] ?? '',
    set: (value: string) => {
      if (draft.value) draft.value[field] = value
    },
  })
}
const observations = textField('observations')
const interpretation = textField('interpretation')
const limitations = textField('limitations')
const evidence = computed({
  get: () => draft.value?.evidence ?? [],
  set: (value) => {
    if (draft.value) draft.value.evidence = value
  },
})
const puzzleEvidence = computed<PuzzleEvidenceReference[]>({
  get: () => draft.value?.puzzle_evidence ?? [],
  set: (value) => {
    if (draft.value) draft.value.puzzle_evidence = value
  },
})
const traceEvidence = computed<TraceEvidenceReference[]>({
  get: () => draft.value?.trace_evidence ?? [],
  set: (value) => {
    if (draft.value) draft.value.trace_evidence = value
  },
})
function citeTrace(reference: TraceEvidenceReference): void {
  if (!draft.value || session.loading || session.error || busy.value) return
  const old = traceEvidence.value.find((item) => item.trace_id === reference.trace_id)
  if (!old && traceEvidence.value.length >= 5) {
    error.value = t('traceCitation.limit')
    return
  }
  traceEvidence.value = old
    ? traceEvidence.value.map((item) => (item === old ? { ...reference, note: old.note } : item))
    : [...traceEvidence.value, reference]
  panel.value = 'editor'
}
const latest = ref(0)
const moreVersions = ref(false)
function fail(e: unknown): void {
  error.value = getErrorMessage(e)
}
async function run(action: () => Promise<void>): Promise<void> {
  busy.value = true
  error.value = ''
  try {
    await action()
  } catch (e) {
    fail(e)
  } finally {
    busy.value = false
  }
}
async function loadCandidates(next: number): Promise<void> {
  const response = await researchApi.candidates(props.comparisonId, next)
  candidates.value = response.data.items
  total.value = response.data.total
  offset.value = next
  selectedCandidateId.value = candidates.value[0]?.id ?? ''
}
async function loadVersions(): Promise<void> {
  const response = await researchApi.versions(props.comparisonId)
  versions.value = response.data
  moreVersions.value = response.data.length === 20
  latest.value = response.data[0]?.revision ?? 0
}
async function read(id: string): Promise<void> {
  selected.value = (await researchApi.get(id)).data
}
function toggle(id: string, enabled: boolean): void {
  if (
    enabled &&
    evidence.value.length < 30 &&
    !evidence.value.some((item) => item.decision_id === id)
  )
    evidence.value.push({ decision_id: id, note: '' })
  else if (!enabled) evidence.value = evidence.value.filter((e) => e.decision_id !== id)
}
function citeDecisions(ids: string[]): void {
  if (!draft.value || session.loading || session.error || busy.value) return
  const additions = [...new Set(ids)].filter(
    (id) => !evidence.value.some((item) => item.decision_id === id),
  )
  if (evidence.value.length + additions.length > 30) {
    error.value = t('paired.citationLimit')
    return
  }
  error.value = ''
  evidence.value.push(...additions.map((decision_id) => ({ decision_id, note: '' })))
  panel.value = 'editor'
}
function citePuzzle(reference: PuzzleEvidenceReference): void {
  if (!draft.value || session.loading || session.error || busy.value) return
  if (
    puzzleEvidence.value.some(
      (item) => item.pack_id === reference.pack_id && item.run_id === reference.run_id,
    )
  )
    return
  if (puzzleEvidence.value.length >= 5) {
    error.value = t('puzzleCitation.limit')
    return
  }
  puzzleEvidence.value = [...puzzleEvidence.value, reference]
  panel.value = 'editor'
}
function revise(): void {
  if (!selected.value || !draft.value) return
  if (
    (observations.value ||
      interpretation.value ||
      limitations.value ||
      evidence.value.length ||
      puzzleEvidence.value.length ||
      traceEvidence.value.length) &&
    !window.confirm(t('researchReport.replaceDraftConfirm'))
  )
    return
  const record = selected.value.record
  observations.value = record.observations
  interpretation.value = record.interpretation
  limitations.value = record.limitations
  evidence.value = record.evidence.map((e) => ({ decision_id: e.decision.id, note: e.note }))
  puzzleEvidence.value = (record.puzzle_evidence ?? []).map((item) => ({
    pack_id: item.result.report.pack_id,
    run_id: item.result.report.run_id,
    expected_report_hash: item.result.report_hash,
    note: item.note,
  }))
  traceEvidence.value = (record.trace_evidence ?? []).map((item) => ({
    trace_id: item.trace.id,
    expected_source_hash: item.source_hash,
    note: item.note,
  }))
  draft.value.expected_revision = latest.value
  panel.value = 'editor'
}
function adoptLatest(): void {
  if (draft.value && window.confirm(t('researchReport.adoptLatestConfirm')))
    draft.value.expected_revision = latest.value
}
async function save(): Promise<void> {
  if (!draft.value || !(await flush())) return
  const response = await researchApi.save(props.comparisonId, {
    expected_revision: draft.value.expected_revision,
    observations: observations.value,
    interpretation: interpretation.value,
    limitations: limitations.value,
    evidence: evidence.value,
    puzzle_evidence: puzzleEvidence.value,
    trace_evidence: traceEvidence.value,
  })
  selected.value = response.data
  draft.value.expected_revision = response.data.record.revision
  await flush()
  await loadVersions()
}
function decisionLink(e: EvidenceCandidate) {
  return {
    path: '/pipeline/decisions',
    query: {
      game_id: e.game_id,
      decision_id: e.id,
      comparison_id: props.comparisonId,
      report_id: route.query.report_id,
      evidence: route.query.evidence,
    },
  }
}
onMounted(() =>
  run(async () => {
    await Promise.all([loadVersions(), props.paired ? Promise.resolve() : loadCandidates(0)])
    if (versions.value[0]) await read(versions.value[0].id)
  }),
)
</script>
<template>
  <section
    class="space-y-ink-4 border-t border-ink-border pt-ink-6"
    :aria-label="t(paired ? 'paired.title' : 'focus.evidenceTitle')"
  >
    <header class="flex flex-wrap items-center justify-between gap-ink-3">
      <h2 class="text-lead font-semibold">
        {{ t(paired ? 'paired.title' : 'focus.evidenceTitle') }}
      </h2>
      <div class="flex flex-wrap gap-ink-2">
        <RouterLink
          v-if="selected"
          :to="{ name: 'research-report', params: { id: selected.record.id } }"
          class="self-center text-body text-ink-primary hover:underline"
          >{{ t('report.open') }} · v{{ selected.record.revision }}</RouterLink
        >
        <UiButton variant="ghost" :disabled="busy" @click="panel = 'history'"
          >{{ t('focus.history') }} · {{ versions.length }}</UiButton
        >
        <UiButton
          variant="secondary"
          :disabled="!draft || session.loading"
          @click="panel = 'editor'"
          >{{ t('focus.record') }}</UiButton
        >
      </div>
    </header>
    <DraftStatus v-if="session.error" :session="session" />
    <p v-if="error" role="alert" class="text-ink-error">{{ error }}</p>
    <p v-if="!paired" class="max-w-3xl text-caption text-ink-text-secondary">
      {{ t('focus.evidenceScope') }}
    </p>
    <ComparisonReplay
      v-if="paired"
      :comparison-id="comparisonId"
      :player-names="playerNames"
      :citation-disabled="busy || !draft || session.loading || Boolean(session.error)"
      :included="evidence.map((e) => e.decision_id)"
      @cite="citeDecisions"
    />
    <DecisionEvidenceReview
      :comparison-id="comparisonId"
      :included="evidence.map((e) => e.decision_id)"
      :disabled="busy || !draft || session.loading || Boolean(session.error)"
      @cite="citeDecisions"
    />
    <TraceEvidenceReview
      :comparison-id="comparisonId"
      :included="traceEvidence"
      :disabled="busy || !draft || session.loading || Boolean(session.error)"
      @cite="citeTrace"
    />
    <PuzzleEvidenceReview
      :comparison-id="comparisonId"
      :included="puzzleEvidence"
      :disabled="busy || !draft || session.loading || Boolean(session.error)"
      @cite="citePuzzle"
    />
    <p v-if="!paired && !candidate && !busy" class="py-ink-6 text-body text-ink-text-secondary">
      {{ t('focus.evidenceEmpty') }}
    </p>
    <div
      v-if="!paired && candidate"
      class="grid items-start gap-ink-6 lg:grid-cols-[minmax(12rem,1fr)_minmax(0,2fr)]"
    >
      <div class="min-w-0 space-y-ink-3">
        <div
          class="max-h-80 space-y-ink-1 overflow-y-auto"
          :aria-label="t('researchReport.evidence')"
        >
          <button
            v-for="(item, index) in candidates"
            :key="item.id"
            type="button"
            class="w-full border-l-2 px-ink-3 py-ink-3 text-left text-body"
            :class="
              candidate.id === item.id
                ? 'border-ink-primary bg-ink-primary-muted text-ink-text'
                : 'border-transparent text-ink-text-secondary hover:bg-ink-surface-muted'
            "
            :aria-pressed="candidate.id === item.id"
            @click="selectedCandidateId = item.id"
          >
            <span class="block break-words">{{
              t('focus.decision', {
                round: item.round_number,
                player: playerNames[item.player_id] ?? item.player_id,
              })
            }}</span>
            <span class="mt-ink-1 block truncate text-caption text-ink-text-muted">{{
              t('focus.candidateN', { n: offset + index + 1 })
            }}</span>
          </button>
        </div>
        <div class="flex flex-wrap items-center gap-ink-2">
          <UiButton
            variant="ghost"
            size="sm"
            :disabled="busy || offset === 0"
            @click="run(() => loadCandidates(offset - 20))"
            >{{ t('researchReport.previous') }}</UiButton
          >
          <span class="text-caption text-ink-text-muted">{{
            t('focus.evidencePage', { start: offset + 1, end: offset + candidates.length, total })
          }}</span>
          <UiButton
            variant="ghost"
            size="sm"
            :disabled="busy || offset + candidates.length >= total"
            @click="run(() => loadCandidates(offset + 20))"
            >{{ t('researchReport.next') }}</UiButton
          >
        </div>
      </div>
      <article
        class="min-w-0 space-y-ink-4 rounded-ink-md border border-ink-border bg-ink-surface p-ink-6"
        aria-live="polite"
      >
        <h3 class="text-lead font-semibold">
          {{
            t('focus.decision', {
              round: candidate.round_number,
              player: playerNames[candidate.player_id] ?? candidate.player_id,
            })
          }}
        </h3>
        <ComparisonDecision :candidate="candidate" />
        <details class="space-y-ink-2 text-caption text-ink-text-muted">
          <summary class="cursor-pointer">{{ t('focus.identifiers') }}</summary>
          <p class="break-all">{{ t('focus.gameId') }}: {{ candidate.game_id }}</p>
          <p class="break-all">{{ t('focus.decisionId') }}: {{ candidate.id }}</p>
        </details>

        <p
          v-if="candidate.annotation"
          class="whitespace-pre-wrap break-words text-body text-ink-text-secondary"
        >
          {{ candidate.annotation }}
        </p>
        <p class="text-caption text-ink-text-secondary">{{ t('focus.noAlignment') }}</p>
        <div class="flex flex-wrap items-center gap-ink-3 border-t border-ink-border pt-ink-4">
          <RouterLink
            :to="decisionLink(candidate)"
            target="_blank"
            rel="noopener"
            class="text-body text-ink-primary hover:underline"
            >{{ t('focus.inspectDecision') }}</RouterLink
          >
          <EvidenceCiteButton
            :ids="[candidate.id]"
            :included="evidence.map((e) => e.decision_id)"
            :disabled="busy || !draft || session.loading || Boolean(session.error)"
            @cite="citeDecisions"
          />
        </div>
      </article>
    </div>
    <UiDialog
      :open="panel === 'editor'"
      placement="side"
      :title="t('researchReport.draft')"
      @update:open="!$event && (panel = null)"
    >
      <DraftStatus :session="session" />
      <p v-if="error" role="alert" class="text-ink-error">{{ error }}</p>
      <div v-if="draft && latest !== draft.expected_revision" class="space-y-2 text-caption">
        <p>{{ t('researchReport.basisChanged', { base: draft.expected_revision, latest }) }}</p>
        <UiButton variant="secondary" :disabled="busy || session.loading" @click="adoptLatest">{{
          t('researchReport.adoptLatest')
        }}</UiButton>
      </div>
      <section v-if="draft" class="space-y-ink-3">
        <fieldset :disabled="busy || session.loading" class="space-y-3">
          <label
            v-for="field in ['observations', 'interpretation', 'limitations'] as const"
            :key="field"
            class="block text-caption"
          >
            {{ t(`researchReport.${field}`) }}{{ field !== 'interpretation' ? ' *' : '' }}
            <UiTextarea
              :model-value="
                field === 'observations'
                  ? observations
                  : field === 'interpretation'
                    ? interpretation
                    : limitations
              "
              :maxlength="10000"
              :disabled="busy"
              @update:model-value="
                (v) => {
                  if (field === 'observations') observations = v
                  else if (field === 'interpretation') interpretation = v
                  else limitations = v
                }
              "
            />
          </label>

          <div v-for="item in evidence" :key="item.decision_id" class="block text-caption">
            {{ item.decision_id }}
            <UiTextarea
              v-model="item.note"
              :aria-label="`${item.decision_id}: ${t('researchReport.note')}`"
              :maxlength="1000"
              :rows="2"
              :disabled="busy"
              :placeholder="t('researchReport.note')"
            />
            <UiButton variant="ghost" :disabled="busy" @click="toggle(item.decision_id, false)">{{
              t('researchReport.remove')
            }}</UiButton>
          </div>
          <section v-if="traceEvidence.length" class="space-y-ink-3">
            <h3 class="text-body font-semibold">{{ t('traceCitation.title') }}</h3>
            <p class="text-caption">{{ t('traceCitation.draftScope') }}</p>
            <div v-for="item in traceEvidence" :key="item.trace_id" class="space-y-ink-2">
              <RouterLink
                :to="{
                  path: '/pipeline/traces',
                  query: {
                    trace_id: item.trace_id,
                    comparison_id: comparisonId,
                    report_id: route.query.report_id,
                    trace_evidence: route.query.trace_evidence,
                  },
                }"
                class="break-all text-ink-primary underline"
                >{{ item.trace_id }} · {{ t('traceCitation.current') }}</RouterLink
              >
              <UiTextarea
                v-model="item.note"
                :aria-label="`${item.trace_id}: ${t('researchReport.note')}`"
                :maxlength="1000"
                :rows="2"
                :disabled="busy"
                :placeholder="t('researchReport.note')"
              />
              <UiButton
                variant="ghost"
                :disabled="busy"
                @click="
                  traceEvidence = traceEvidence.filter((row) => row.trace_id !== item.trace_id)
                "
                >{{ t('researchReport.remove') }}</UiButton
              >
            </div>
          </section>
          <ComparisonPuzzleEvidence
            v-model="puzzleEvidence"
            :comparison-id="comparisonId"
            :disabled="busy || session.loading"
          />
          <UiButton
            :disabled="
              busy ||
              Boolean(session.error) ||
              !observations.trim() ||
              !limitations.trim() ||
              latest !== draft.expected_revision
            "
            @click="run(save)"
            >{{ t('researchReport.save') }}</UiButton
          >
        </fieldset>
      </section>
    </UiDialog>
    <UiDialog
      :open="panel === 'history'"
      placement="side"
      :title="t('focus.history')"
      @update:open="!$event && (panel = null)"
    >
      <p v-if="error" role="alert" class="text-ink-error">{{ error }}</p>
      <p class="mb-ink-4 text-caption text-ink-text-secondary">{{ t('researchReport.scope') }}</p>
      <div class="flex flex-wrap gap-2">
        <UiButton variant="secondary" :disabled="busy" @click="run(loadVersions)">{{
          t('researchReport.refresh')
        }}</UiButton>
        <UiButton
          v-for="version in versions"
          :key="version.id"
          variant="secondary"
          :disabled="busy"
          @click="run(() => read(version.id))"
          >v{{ version.revision }}</UiButton
        >
        <UiButton
          v-if="moreVersions"
          variant="secondary"
          :disabled="busy"
          @click="
            run(async () => {
              const response = await researchApi.versions(comparisonId, versions.length)
              versions.push(...response.data)
              moreVersions = response.data.length === 20
            })
          "
          >{{ t('researchReport.more') }}</UiButton
        >
      </div>
      <article v-if="selected" class="space-y-3 rounded-ink-md bg-ink-surface-muted p-3">
        <h3 class="font-semibold">
          {{ t('researchReport.saved') }} · v{{ selected.record.revision }}
        </h3>
        <template
          v-for="field in ['observations', 'interpretation', 'limitations'] as const"
          :key="field"
        >
          <h4 class="text-caption font-semibold">{{ t(`researchReport.${field}`) }}</h4>
          <p class="whitespace-pre-wrap break-words">{{ selected.record[field] || '—' }}</p>
        </template>
        <p
          v-if="
            !selected.record.evidence.length &&
            !selected.record.puzzle_evidence?.length &&
            !selected.record.trace_evidence?.length
          "
          class="text-caption"
        >
          {{ t('researchReport.noEvidence') }}
        </p>
        <p v-if="selected.record.trace_evidence?.length" class="text-caption">
          {{ t('traceCitation.savedCount', { n: selected.record.trace_evidence.length }) }}
        </p>
        <p v-if="selected.record.puzzle_evidence?.length" class="text-caption">
          {{ t('puzzleCitation.savedCount', { n: selected.record.puzzle_evidence.length }) }}
        </p>
        <div
          v-for="item in selected.record.evidence"
          :key="item.decision.id"
          class="space-y-1 border-t border-ink-border pt-2"
        >
          <RouterLink
            v-if="
              ['available', 'changed'].includes(selected.evidence_status[item.decision.id] ?? '')
            "
            :to="decisionLink(item.decision)"
            target="_blank"
            rel="noopener"
            class="text-ink-primary"
            >{{ item.decision.id }}</RouterLink
          >
          <span v-else>{{ item.decision.id }}</span>
          <p class="text-caption">
            {{ t(`researchReport.status.${selected.evidence_status[item.decision.id]}`) }}
          </p>
          <p class="whitespace-pre-wrap">{{ item.note }}</p>
          <details>
            <summary class="cursor-pointer text-caption">{{ t('researchReport.frozen') }}</summary>
            <pre class="max-h-64 overflow-auto whitespace-pre-wrap break-all text-caption">{{
              JSON.stringify(item.decision, null, 2)
            }}</pre>
          </details>
        </div>
        <div class="flex gap-2">
          <RouterLink
            :to="{ name: 'research-report', params: { id: selected.record.id } }"
            class="self-center text-body text-ink-primary hover:underline"
            >{{ t('report.open') }}</RouterLink
          >
          <UiButton
            variant="secondary"
            :disabled="busy || !draft || session.loading"
            @click="revise"
            >{{ t('researchReport.revise') }}</UiButton
          >
          <UiButton
            variant="secondary"
            :disabled="busy"
            @click="
              run(async () => {
                if (selected)
                  await downloadJson(
                    `research-${selected.record.id}.json`,
                    (await researchApi.export(selected.record.id)).data,
                  )
              })
            "
            >{{ t('researchReport.export') }}</UiButton
          >
        </div>
      </article>
    </UiDialog>
  </section>
</template>
