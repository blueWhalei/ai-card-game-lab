<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import {
  onBeforeRouteLeave,
  onBeforeRouteUpdate,
  RouterLink,
  useRoute,
  useRouter,
} from 'vue-router'
import { useI18n } from 'vue-i18n'
import { metricLabel, seatLabel } from '@/utils/researchOutcome'
import { studyApi, type StudyDetail } from '@/api/studyApi'
import {
  promptDesignApi,
  type PrimaryMetric,
  type PromptDesignPreview,
} from '@/api/promptDesignApi'
import { systemApi, type PreflightResult } from '@/api/systemApi'
import { preflightCheckMessage } from '@/utils/systemLabels'
import { showApiError } from '@/utils/error'
import UiButton from '@/components/ui/Button.vue'
import UiInput from '@/components/ui/Input.vue'
import UiTextarea from '@/components/ui/Textarea.vue'
import { confirmDialog } from '@/components/ui/confirm'
import { useDesktopLifecycle } from '@/stores/useDesktopLifecycle'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const studyId = computed(() => String(route.params.id))
const sourceRevision = computed(() =>
  typeof route.query.source_revision === 'string' ? route.query.source_revision : undefined,
)
const invalidSource = computed(
  () =>
    Object.hasOwn(route.query, 'source_revision') &&
    (!sourceRevision.value || typeof route.query.baseline !== 'string' || !route.query.baseline),
)
const study = ref<StudyDetail | null>(null)
const baselineId = ref('')
const preview = ref<PromptDesignPreview | null>(null)
const preflight = ref<PreflightResult | null>(null)
const step = ref(1)
const studyLoading = ref(false)
const baselineLoading = ref(false)
const loading = computed(() => studyLoading.value || baselineLoading.value)
const failed = ref(false)
const saving = ref(false)
const name = ref('')
const hypothesis = ref('')
const templateKey = ref('')
const version = ref('')
const primaryMetric = ref<PrimaryMetric | null>(null)
const affectedSeats = computed(() => preview.value?.affected_player_ids ?? [])
const affectedNames = computed(() =>
  affectedSeats.value.map((id) => seatLabel(id, protocol.value?.solver.players)).join(', '),
)
const edited = ref(false)
const removeCloseBlocker = useDesktopLifecycle().registerBlocker(() => edited.value || saving.value)
onBeforeUnmount(removeCloseBlocker)
let request = 0
let studyRequest = 0
const protocol = computed(() => preview.value?.baseline.protocol)
const options = computed(
  () => preview.value?.options.filter((o) => o.template_key === templateKey.value) ?? [],
)
const chosen = computed(() => options.value.find((o) => o.version === version.value))
const original = computed(() => protocol.value?.solver.prompts?.[templateKey.value])
const eligible = computed(
  () =>
    preview.value &&
    preview.value.baseline.study_id === studyId.value &&
    !preview.value.issues.length,
)
const canReview = computed(
  () =>
    eligible.value &&
    primaryMetric.value &&
    name.value.trim() &&
    hypothesis.value.trim() &&
    chosen.value &&
    chosen.value.content !== original.value?.content,
)
const keys = computed(() => [...new Set(Object.values(protocol.value?.engine.prompt_keys ?? {}))])
function phaseLabel(key: string): string {
  const phase = Object.entries(protocol.value?.engine.prompt_keys ?? {}).find(
    ([, value]) => value === key,
  )?.[0]
  return phase && ['playing', 'bidding'].includes(phase) ? t(`promptDesign.phases.${phase}`) : key
}

async function loadStudy(): Promise<void> {
  if (invalidSource.value) {
    failed.value = true
    return
  }
  const current = ++studyRequest
  studyLoading.value = true
  failed.value = false
  try {
    const { data } = await studyApi.get(studyId.value)
    if (current !== studyRequest) return
    if (data.id !== studyId.value) throw new Error('Research identity mismatch')
    study.value = data
    hypothesis.value = sourceRevision.value ? '' : data.question
    if (typeof route.query.baseline === 'string') baselineId.value = route.query.baseline
  } catch {
    if (current === studyRequest) failed.value = true
  } finally {
    if (current === studyRequest) studyLoading.value = false
  }
}
async function loadBaseline(): Promise<void> {
  const current = ++request
  const id = baselineId.value
  const source = sourceRevision.value
  preview.value = null
  primaryMetric.value = null
  preflight.value = null
  step.value = 1
  failed.value = invalidSource.value
  baselineLoading.value = false
  if (!id || invalidSource.value) return
  baselineLoading.value = true
  try {
    const [design, checks] = await Promise.all([
      promptDesignApi.preview(id, source),
      systemApi.preflight({ scope: 'collect', experiment_id: id }),
    ])
    if (current !== request) return
    if (design.data.baseline.id !== id || (source && design.data.source_conclusion?.id !== source))
      throw new Error('Design source mismatch')
    preview.value = design.data
    preflight.value = checks.data
    if (!name.value) name.value = `${design.data.baseline.name.slice(0, 116)} · B`
    templateKey.value = keys.value[0] ?? ''
    version.value = ''
  } catch {
    if (current === request) failed.value = true
  } finally {
    if (current === request) baselineLoading.value = false
  }
}
async function create(): Promise<void> {
  if (
    !primaryMetric.value ||
    !canReview.value ||
    !preview.value ||
    !chosen.value ||
    saving.value ||
    step.value !== 3
  )
    return
  saving.value = true
  try {
    const { data } = await promptDesignApi.create(baselineId.value, {
      study_id: studyId.value,
      primary_metric: primaryMetric.value,
      baseline_fingerprint: preview.value.fingerprint,
      template_key: chosen.value.template_key,
      version: chosen.value.version,
      content_hash: chosen.value.content_hash,
      name: name.value.trim(),
      hypothesis: hypothesis.value.trim(),
      ...(sourceRevision.value ? { source_revision_id: sourceRevision.value } : {}),
    })
    edited.value = false
    saving.value = false
    await router.push(`/experiments/${data.id}`)
  } catch (error) {
    showApiError(error, t('promptDesign.createFailed'))
    // Keep text, but invalidate the review; reloading must be an explicit action.
    preview.value = null
    failed.value = true
    step.value = 1
  } finally {
    saving.value = false
  }
}
function protect(event: BeforeUnloadEvent): void {
  if (!edited.value) return
  event.preventDefault()
  event.returnValue = ''
}
window.addEventListener('beforeunload', protect)
onBeforeUnmount(() => {
  request++
  studyRequest++
  window.removeEventListener('beforeunload', protect)
})
async function canLeave(): Promise<boolean> {
  return !saving.value && (!edited.value || (await confirmDialog(t('promptDesign.leave'))))
}
onBeforeRouteLeave(canLeave)
onBeforeRouteUpdate(canLeave)
watch(
  [studyId, () => route.query.source_revision, () => route.query.baseline],
  () => {
    request++
    studyRequest++
    studyLoading.value = false
    baselineLoading.value = false
    study.value = null
    baselineId.value = ''
    preview.value = null
    preflight.value = null
    name.value = ''
    hypothesis.value = ''
    primaryMetric.value = null
    edited.value = false
    step.value = 1
    failed.value = invalidSource.value
    if (!invalidSource.value) void loadStudy()
  },
  { immediate: true },
)
watch(baselineId, () => {
  name.value = ''
  void loadBaseline()
})
watch(templateKey, () => {
  version.value = ''
})
</script>

<template>
  <div class="page-container space-y-6">
    <RouterLink :to="`/research/${studyId}`" class="text-body text-ink-primary hover:underline"
      >← {{ t('study.back') }}</RouterLink
    >
    <header class="max-w-3xl border-l-2 border-ink-primary pl-5">
      <p class="text-caption text-ink-text-muted">{{ study?.title }}</p>
      <h1 class="mt-2 text-headline font-semibold">{{ t('promptDesign.title') }}</h1>
      <p class="mt-3 text-body text-ink-text-secondary">{{ t('promptDesign.intro') }}</p>
    </header>
    <section
      v-if="sourceRevision"
      class="max-w-3xl space-y-ink-3 border-l-2 border-ink-border pl-5"
    >
      <RouterLink
        :to="{ name: 'research-report', params: { id: sourceRevision } }"
        class="text-body text-ink-primary hover:underline"
      >
        {{ t('promptDesign.sourceConclusion')
        }}<template v-if="preview?.source_conclusion">
          · v{{ preview.source_conclusion.revision }}</template
        >
      </RouterLink>
      <p class="text-body text-ink-text-secondary">{{ t('promptDesign.followupScope') }}</p>
      <details v-if="preview?.source_conclusion" class="space-y-ink-3">
        <summary class="cursor-pointer text-ink-primary">
          {{ t('promptDesign.sourceText') }}
        </summary>
        <template
          v-for="field in ['observations', 'interpretation', 'limitations'] as const"
          :key="field"
        >
          <h2 class="text-body font-semibold">{{ t(`researchReport.${field}`) }}</h2>
          <p class="whitespace-pre-wrap break-words text-body">
            {{ preview.source_conclusion[field] || t('report.missing') }}
          </p>
        </template>
      </details>
    </section>
    <ol
      class="flex flex-wrap gap-x-8 gap-y-2 border-b border-ink-border pb-4"
      :aria-label="t('promptDesign.steps')"
    >
      <li
        v-for="n in 3"
        :key="n"
        :aria-current="step === n ? 'step' : undefined"
        :class="step === n ? 'font-semibold text-ink-primary' : 'text-ink-text-muted'"
      >
        {{ n }} · {{ t(`promptDesign.step${n}`) }}
      </li>
    </ol>
    <div v-if="failed" role="alert" class="space-y-3">
      <p>{{ t('promptDesign.loadFailed') }}</p>
      <UiButton variant="secondary" @click="study && baselineId ? loadBaseline() : loadStudy()">{{
        t('common.retry')
      }}</UiButton>
    </div>
    <p v-if="loading" role="status">{{ t('common.loading') }}</p>
    <form v-if="study" class="space-y-6" @submit.prevent="create">
      <section v-if="step === 1" class="max-w-3xl space-y-4">
        <label for="baseline" class="block text-title">{{ t('promptDesign.baseline') }}</label>
        <select
          id="baseline"
          v-model="baselineId"
          class="ink-input w-full"
          :disabled="loading || saving || !!sourceRevision"
        >
          <option value="">{{ t('promptDesign.choose') }}</option>
          <option v-for="run in study.runs" :key="run.id" :value="run.id">{{ run.name }}</option>
        </select>
        <p class="text-body text-ink-text-secondary">{{ t('promptDesign.baselineHint') }}</p>
        <p v-if="sourceRevision" class="text-caption text-ink-text-secondary">
          {{ t('promptDesign.sourceBaseline') }}
        </p>
        <ul v-if="preview?.issues.length" class="list-disc space-y-2 pl-5 text-body" role="status">
          <li v-for="issue in preview.issues" :key="issue">
            {{ t(`promptDesign.issues.${issue}`) }}
          </li>
        </ul>
        <RouterLink
          v-if="!sourceRevision"
          :to="{
            path: '/experiments',
            query: { study: studyId, create: '1', preset: 'prompt-baseline' },
          }"
          class="inline-block text-ink-primary hover:underline"
          >{{ t('promptDesign.newBaseline') }} →</RouterLink
        >
      </section>
      <section v-if="step === 2" class="space-y-5" @input="edited = true" @change="edited = true">
        <div class="max-w-3xl space-y-3">
          <label for="hypothesis" class="block text-title">{{
            t('promptDesign.hypothesis')
          }}</label>
          <UiTextarea id="hypothesis" v-model="hypothesis" :maxlength="10000" :rows="3" />
          <label for="variant-name" class="block text-body">{{ t('promptDesign.name') }}</label>
          <UiInput id="variant-name" v-model="name" :maxlength="120" />
          <div class="grid gap-4 sm:grid-cols-2">
            <div>
              <label for="phase" class="mb-2 block">{{ t('promptDesign.phase') }}</label>
              <select id="phase" v-model="templateKey" class="ink-input w-full">
                <option v-for="key in keys" :key="key" :value="key">{{ phaseLabel(key) }}</option>
              </select>
            </div>
            <div>
              <label for="version" class="mb-2 block">{{ t('promptDesign.version') }}</label>
              <select id="version" v-model="version" class="ink-input w-full">
                <option value="">{{ t('promptDesign.choose') }}</option>
                <option
                  v-for="option in options"
                  :key="option.version"
                  :value="option.version"
                  :disabled="option.content === original?.content"
                >
                  {{ option.version }}
                </option>
              </select>
            </div>
          </div>
          <p class="text-caption text-ink-text-muted">
            {{ t('promptDesign.affected', { seats: affectedNames }) }}
          </p>
          <label for="primary-metric" class="block text-body">{{
            t('promptDesign.observe')
          }}</label>
          <select id="primary-metric" v-model="primaryMetric" class="ink-input w-full">
            <option :value="null" disabled>{{ t('promptDesign.choose') }}</option>
            <option
              v-for="id in affectedSeats"
              :key="id"
              :value="{ kind: 'seat_team_win_rate', player_id: id }"
            >
              {{
                metricLabel(
                  t,
                  { kind: 'seat_team_win_rate', player_id: id },
                  protocol?.solver.players,
                )
              }}
            </option>
            <option :value="{ kind: 'landlord_win_rate' }">
              {{ t('promptDesign.tableMetric') }}
            </option>
          </select>
          <p
            v-if="primaryMetric?.kind === 'seat_team_win_rate' && affectedSeats.length > 1"
            class="text-caption text-ink-text-secondary"
          >
            {{ t('promptDesign.sharedChange') }}
          </p>
          <RouterLink to="/prompt" class="inline-block text-ink-primary hover:underline"
            >{{ t('promptDesign.managePrompts') }} →</RouterLink
          >
        </div>
        <div class="grid min-w-0 gap-4 lg:grid-cols-2">
          <article
            v-for="(entry, index) in [original, chosen]"
            :key="index"
            class="min-w-0 rounded-ink-md border border-ink-border bg-ink-surface p-5"
          >
            <h2 class="text-title">
              {{ index === 0 ? 'A' : 'B' }} · {{ entry?.version ?? t('promptDesign.choose') }}
            </h2>
            <p class="my-2 break-all font-mono text-caption text-ink-text-muted">
              {{ entry?.content_hash }}
            </p>
            <pre
              class="max-h-80 overflow-auto whitespace-pre-wrap break-words font-sans text-body"
              >{{ entry?.content }}</pre
            >
          </article>
        </div>
      </section>
      <section
        v-if="step === 3 && preview"
        class="grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(260px,2fr)]"
      >
        <div class="min-w-0 space-y-4">
          <h2 class="text-title">{{ t('promptDesign.review') }}</h2>
          <p class="whitespace-pre-wrap break-words text-lead">{{ hypothesis }}</p>
          <dl
            class="space-y-3 rounded-ink-md border border-ink-border bg-ink-surface p-5 text-body"
          >
            <div>
              <dt class="text-ink-text-muted">{{ t('promptDesign.change') }}</dt>
              <dd class="break-words">
                {{ phaseLabel(templateKey) }} · {{ original?.version }} → {{ chosen?.version }}
              </dd>
            </div>
            <div>
              <dt class="text-ink-text-muted">{{ t('promptDesign.plan') }}</dt>
              <dd>{{ t('promptDesign.planValue', { n: preview.baseline.target_games }) }}</dd>
            </div>
            <div>
              <dt class="text-ink-text-muted">{{ t('promptDesign.metric') }}</dt>
              <dd v-if="primaryMetric">
                {{ metricLabel(t, primaryMetric, protocol?.solver.players) }} ·
                {{ t('promptDesign.contrast') }}
              </dd>
              <dd>{{ t('promptDesign.affected', { seats: affectedNames }) }}</dd>
            </div>
            <div>
              <dt class="text-ink-text-muted">{{ t('promptDesign.fixed') }}</dt>
              <dd>{{ t('promptDesign.fixedValue') }}</dd>
            </div>
          </dl>
          <ul class="space-y-2 text-body">
            <li
              v-for="(player, index) in protocol?.solver.players"
              :key="player.id"
              class="break-words"
            >
              {{ index + 1 }} · {{ player.name }} · {{ player.policy_kind }} ·
              {{ player.model_config.model_name }}
            </li>
          </ul>
          <details class="text-body">
            <summary class="cursor-pointer text-ink-primary">
              {{ t('promptDesign.protocol') }}
            </summary>
            <pre class="mt-3 max-h-80 overflow-auto whitespace-pre-wrap break-all text-caption">{{
              JSON.stringify(protocol, null, 2)
            }}</pre>
          </details>
        </div>
        <aside class="space-y-4 border-l-2 border-ink-border pl-5">
          <h2 class="text-title">{{ t('promptDesign.readiness') }}</h2>
          <p class="text-body text-ink-text-secondary">{{ t('promptDesign.preflightHint') }}</p>
          <ul class="space-y-2 text-body">
            <li v-for="check in preflight?.checks" :key="check.id">
              {{ check.ok ? '✓' : '—' }} {{ preflightCheckMessage(check) }}
            </li>
          </ul>
          <RouterLink to="/settings" class="inline-block text-ink-primary hover:underline"
            >{{ t('promptDesign.settings') }} →</RouterLink
          >
          <p class="text-body">{{ t('promptDesign.noCall') }}</p>
          <p class="text-caption text-ink-text-muted">{{ t('promptDesign.limitations') }}</p>
        </aside>
      </section>
      <footer class="flex flex-wrap gap-3 border-t border-ink-border pt-5">
        <UiButton
          v-if="step > 1"
          type="button"
          variant="ghost"
          :disabled="saving"
          @click="step--"
          >{{ t('promptDesign.previous') }}</UiButton
        >
        <UiButton
          v-if="step < 3"
          type="button"
          :disabled="loading || failed || (step === 1 ? !eligible : !canReview)"
          @click="step++"
          >{{ t('promptDesign.next') }}</UiButton
        >
        <UiButton v-else type="submit" :disabled="!canReview" :loading="saving">{{
          t('promptDesign.create')
        }}</UiButton>
      </footer>
    </form>
  </div>
</template>
