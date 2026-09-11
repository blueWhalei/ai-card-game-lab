<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'
import {
  researchApi,
  type EvidenceCandidate,
  type EvidenceReference,
  type ResearchVersion,
  type ResearchVersionSummary,
} from '@/api/researchApi'
import UiButton from '@/components/ui/Button.vue'
import UiTextarea from '@/components/ui/Textarea.vue'
import UiCheckbox from '@/components/ui/Checkbox.vue'
import { downloadJson } from '@/utils/jsonFile'
const props = defineProps<{ comparisonId: string }>()
const { t } = useI18n()
const versions = ref<ResearchVersionSummary[]>([])
const selected = ref<ResearchVersion | null>(null)
const candidates = ref<EvidenceCandidate[]>([])
const total = ref(0)
const offset = ref(0)
const busy = ref(false)
const error = ref('')
const observations = ref('')
const interpretation = ref('')
const limitations = ref('')
const evidence = ref<EvidenceReference[]>([])
const latest = ref(0)
const moreVersions = ref(false)
function fail(e: unknown) {
  error.value =
    e instanceof Error
      ? e.message
      : String(
          (typeof e === 'object' && e !== null && 'message' in e ? e.message : null) ??
            t('researchReport.error'),
        )
}
async function run(action: () => Promise<void>) {
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
async function loadCandidates(next: number) {
  const response = await researchApi.candidates(props.comparisonId, next)
  candidates.value = response.data.items
  total.value = response.data.total
  offset.value = next
}
async function loadVersions() {
  const response = await researchApi.versions(props.comparisonId)
  versions.value = response.data
  moreVersions.value = response.data.length === 20
  latest.value = response.data[0]?.revision ?? 0
}
async function read(id: string) {
  selected.value = (await researchApi.get(id)).data
}
function toggle(id: string, enabled: boolean) {
  if (enabled && evidence.value.length < 30) evidence.value.push({ decision_id: id, note: '' })
  else if (!enabled) evidence.value = evidence.value.filter((e) => e.decision_id !== id)
}
function revise() {
  if (!selected.value) return
  const record = selected.value.record
  observations.value = record.observations
  interpretation.value = record.interpretation
  limitations.value = record.limitations
  evidence.value = record.evidence.map((e) => ({ decision_id: e.decision.id, note: e.note }))
}
async function save() {
  const response = await researchApi.save(props.comparisonId, {
    expected_revision: latest.value,
    observations: observations.value,
    interpretation: interpretation.value,
    limitations: limitations.value,
    evidence: evidence.value,
  })
  selected.value = response.data
  await loadVersions()
}
function decisionLink(e: EvidenceCandidate) {
  return {
    path: '/pipeline/decisions',
    query: { game_id: e.game_id, decision_id: e.id, comparison_id: props.comparisonId },
  }
}
onMounted(() =>
  run(async () => {
    await Promise.all([loadVersions(), loadCandidates(0)])
    if (versions.value[0]) await read(versions.value[0].id)
  }),
)
</script>
<template>
  <section
    class="space-y-4 rounded-ink-md border border-ink-border bg-ink-surface p-4"
    :aria-label="t('researchReport.title')"
  >
    <h2 class="text-lead font-semibold">{{ t('researchReport.title') }}</h2>
    <p class="text-caption text-ink-text-secondary">{{ t('researchReport.scope') }}</p>
    <p v-if="error" role="alert" class="text-ink-error">{{ error }}</p>
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
      <p v-if="!selected.record.evidence.length" class="text-caption">
        {{ t('researchReport.noEvidence') }}
      </p>
      <div
        v-for="item in selected.record.evidence"
        :key="item.decision.id"
        class="space-y-1 border-t border-ink-border pt-2"
      >
        <RouterLink
          v-if="['available', 'changed'].includes(selected.evidence_status[item.decision.id] ?? '')"
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
        <UiButton variant="secondary" :disabled="busy" @click="revise">{{
          t('researchReport.revise')
        }}</UiButton>
        <UiButton
          variant="secondary"
          :disabled="busy"
          @click="
            run(async () => {
              if (selected)
                downloadJson(
                  `research-${selected.record.id}.json`,
                  (await researchApi.export(selected.record.id)).data,
                )
            })
          "
          >{{ t('researchReport.export') }}</UiButton
        >
      </div>
    </article>
    <details class="space-y-3" open>
      <summary class="cursor-pointer font-semibold">{{ t('researchReport.draft') }}</summary>
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
      <details class="space-y-2">
        <summary class="cursor-pointer">
          {{ t('researchReport.evidence') }} · {{ evidence.length }}/30
        </summary>
        <p class="text-caption">{{ t('researchReport.candidateHint') }}</p>
        <div
          v-for="candidate in candidates"
          :key="candidate.id"
          class="flex items-center gap-3 border-b border-ink-border py-2 text-caption"
        >
          <UiCheckbox
            :model-value="evidence.some((e) => e.decision_id === candidate.id)"
            :disabled="
              busy ||
              (evidence.length >= 30 && !evidence.some((e) => e.decision_id === candidate.id))
            "
            :label="candidate.id"
            @update:model-value="(v) => toggle(candidate.id, v)"
          />
          <RouterLink
            :to="decisionLink(candidate)"
            target="_blank"
            rel="noopener"
            class="break-all text-ink-primary"
            >{{ candidate.id }}</RouterLink
          >
          <span
            >{{ candidate.player_id }} · {{ candidate.round_number }} · {{ candidate.action_id }} ·
            EV {{ candidate.ev_loss ?? '—' }}</span
          >
        </div>
        <div class="flex gap-2">
          <UiButton
            variant="secondary"
            :disabled="busy || offset === 0"
            @click="run(() => loadCandidates(offset - 20))"
            >{{ t('researchReport.previous') }}</UiButton
          >
          <UiButton
            variant="secondary"
            :disabled="busy || offset + candidates.length >= total"
            @click="run(() => loadCandidates(offset + 20))"
            >{{ t('researchReport.next') }}</UiButton
          >
        </div>
      </details>
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
      <UiButton
        :disabled="busy || !observations.trim() || !limitations.trim()"
        @click="run(save)"
        >{{ t('researchReport.save') }}</UiButton
      >
    </details>
  </section>
</template>
