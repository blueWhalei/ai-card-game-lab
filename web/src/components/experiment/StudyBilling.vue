<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { studyBillingApi, type BillingOverview, type BillingEvidence } from '@/api/studyBillingApi'
import { confirmDialog } from '@/components/ui/confirm'
import { useDesktopLifecycle } from '@/stores/useDesktopLifecycle'
import { getErrorMessage } from '@/utils/error'
import { formatDateTime } from '@/utils/format'
import UiButton from '@/components/ui/Button.vue'
import UiInput from '@/components/ui/Input.vue'
import UiTextarea from '@/components/ui/Textarea.vue'
import UiCheckbox from '@/components/ui/Checkbox.vue'
import UiPagination from '@/components/ui/Pagination.vue'
import StudyBillingSchedule from './StudyBillingSchedule.vue'
import StudyBillingReconciliation from './StudyBillingReconciliation.vue'
import type { ReconciliationSnapshot } from '@/api/billingReconciliationApi'

const props = defineProps<{ studyId: string }>()
const { t, te } = useI18n()
const data = ref<BillingOverview | null>(null),
  loading = ref(false),
  failed = ref(false)
const editing = ref(false),
  scheduleEditing = ref(false),
  reconciliationEditing = ref(false),
  busy = ref(false),
  error = ref(''),
  message = ref('')
const project = ref(''),
  start = ref(''),
  limit = ref(''),
  hours = ref('6'),
  enabled = ref(false),
  reason = ref(''),
  revision = ref(0)
const evidence = ref<BillingEvidence | null>(null),
  evidenceSection = ref<HTMLElement | null>(null),
  evidenceId = ref(''),
  evidencePage = ref(1),
  evidenceLoading = ref(false),
  evidenceFailed = ref(false)
let generation = 0,
  evidenceGeneration = 0,
  disposed = false
let evidenceReturnFocus: HTMLElement | null = null
const unregister = useDesktopLifecycle().registerBlocker(() => editing.value || busy.value)
const reconciliationSnapshots = computed<ReconciliationSnapshot[]>(() => {
  const value = data.value
  if (!value) return []
  const snapshots: ReconciliationSnapshot[] = value.history.filter(
    (item) => item.status === 'succeeded',
  )
  if (value.snapshot && value.config && !snapshots.some((item) => item.id === value.snapshot!.id)) {
    snapshots.unshift({
      ...value.snapshot,
      revision: value.config.revision,
      organization_id: value.config.organization_id,
      project_id: value.config.project_id,
    })
  }
  return snapshots
})
const utc = (seconds: number) =>
  new Date(seconds * 1000).toISOString().replace('T', ' ').replace('.000Z', '')
const syncError = (code: string | null) =>
  code && te(`billing.errors.${code}`) ? t(`billing.errors.${code}`) : t('billing.syncFailed')

async function load(quiet = false) {
  const token = ++generation,
    id = props.studyId
  if (!quiet) data.value = null
  loading.value = true
  failed.value = false
  try {
    const result = (await studyBillingApi.get(id)).data
    if (token !== generation || disposed) return
    if (result.study_id !== id) throw new Error('Billing scope mismatch')
    data.value = result
  } catch {
    if (token === generation && !disposed) {
      data.value = null
      failed.value = true
    }
  } finally {
    if (token === generation && !disposed) loading.value = false
  }
}
function edit() {
  const config = data.value?.config
  project.value = config?.project_id ?? ''
  start.value = config?.start_date ?? new Date().toISOString().slice(0, 10)
  limit.value = config?.limit_amount ?? ''
  hours.value = String(config?.max_age_hours ?? 6)
  enabled.value = !!config?.enforcement_enabled
  revision.value = config?.revision ?? 0
  reason.value = error.value = message.value = ''
  editing.value = true
}
async function reloadConfig() {
  if (!(await confirmDialog(t('finance.replaceInput')))) return
  const id = props.studyId
  await load()
  if (!disposed && id === props.studyId && data.value) edit()
}
function discard() {
  editing.value = false
  error.value = ''
}
async function save() {
  if (busy.value) return
  if (
    !/^proj_[a-zA-Z0-9_-]{1,120}$/.test(project.value.trim()) ||
    !start.value ||
    !/^(?:[1-9]|1\d|2[0-4])$/.test(hours.value) ||
    !reason.value.trim() ||
    (limit.value && !/^(0|[1-9]\d{0,8})(\.\d{1,6})?$/.test(limit.value)) ||
    (enabled.value && !limit.value)
  ) {
    error.value = t('billing.invalid')
    return
  }
  const id = props.studyId
  busy.value = true
  error.value = ''
  try {
    await studyBillingApi.configure(id, {
      expected_revision: revision.value,
      project_id: project.value.trim(),
      start_date: start.value,
      limit: limit.value || null,
      enforcement_enabled: enabled.value,
      max_age_hours: Number(hours.value),
      reason: reason.value.trim(),
    })
    if (disposed || id !== props.studyId) return
    editing.value = false
    message.value = t('finance.saved')
    closeEvidence()
    await load()
  } catch (err) {
    if (!disposed && id === props.studyId)
      error.value = getErrorMessage(err, t('finance.saveFailed'))
  } finally {
    if (!disposed && id === props.studyId) busy.value = false
  }
}
async function sync() {
  if (busy.value || editing.value || !data.value?.can_sync || !data.value.config) return
  const id = props.studyId,
    version = data.value.config.revision
  busy.value = true
  error.value = message.value = ''
  try {
    await studyBillingApi.sync(id, version)
    if (disposed || id !== props.studyId) return
    message.value = t('billing.synced')
  } catch (err) {
    if (!disposed && id === props.studyId)
      error.value = getErrorMessage(err, t('billing.syncFailed'))
  } finally {
    if (!disposed && id === props.studyId) {
      await load()
      if (!disposed && id === props.studyId) busy.value = false
    }
  }
}
async function showEvidence(id: string, page = 1) {
  const token = ++evidenceGeneration,
    study = props.studyId
  if (evidenceId.value !== id) {
    evidenceReturnFocus =
      document.activeElement instanceof HTMLElement ? document.activeElement : null
  }
  evidenceId.value = id
  evidencePage.value = page
  evidence.value = null
  evidenceLoading.value = true
  evidenceFailed.value = false
  try {
    const result = (await studyBillingApi.evidence(study, id, page)).data
    if (token !== evidenceGeneration || disposed) return
    if (result.study_id !== study || result.id !== id || result.page !== page)
      throw new Error('Evidence scope mismatch')
    evidence.value = result
  } catch {
    if (token === evidenceGeneration && !disposed) evidenceFailed.value = true
  } finally {
    if (token === evidenceGeneration && !disposed) {
      evidenceLoading.value = false
      await nextTick()
      if (token === evidenceGeneration && !disposed) {
        evidenceSection.value?.focus({ preventScroll: true })
        evidenceSection.value?.scrollIntoView({ block: 'start' })
      }
    }
  }
}
function closeEvidence() {
  evidenceGeneration++
  evidenceId.value = ''
  evidence.value = null
  evidenceFailed.value = evidenceLoading.value = false
  if (evidenceReturnFocus?.isConnected) evidenceReturnFocus.focus()
  evidenceReturnFocus = null
}
async function canLeave() {
  return !busy.value && (!editing.value || (await confirmDialog(t('finance.leave'))))
}
function protect(event: BeforeUnloadEvent) {
  if (!editing.value && !busy.value) return
  event.preventDefault()
  event.returnValue = ''
}
function refresh() {
  if (
    !editing.value &&
    !scheduleEditing.value &&
    !reconciliationEditing.value &&
    !busy.value &&
    !loading.value &&
    !document.hidden
  )
    void load(true)
}
const poll = window.setInterval(refresh, 30_000)
document.addEventListener('visibilitychange', refresh)
onBeforeRouteLeave(canLeave)
onBeforeRouteUpdate(canLeave)
window.addEventListener('beforeunload', protect)
watch(
  () => props.studyId,
  () => {
    editing.value = busy.value = false
    error.value = message.value = ''
    closeEvidence()
    void load()
  },
  { immediate: true },
)
onBeforeUnmount(() => {
  disposed = true
  generation++
  evidenceGeneration++
  unregister()
  window.removeEventListener('beforeunload', protect)
  window.clearInterval(poll)
  document.removeEventListener('visibilitychange', refresh)
})
</script>

<template>
  <section
    class="space-y-ink-3 border-b border-ink-border pb-ink-4 text-body"
    :aria-busy="loading || busy"
  >
    <h3 class="font-medium">{{ t('billing.title') }}</h3>
    <p>{{ t('billing.scope') }}</p>
    <details class="space-y-ink-2">
      <summary class="cursor-pointer text-ink-accent">{{ t('finance.method') }}</summary>
      <p>{{ t('billing.coverage') }}</p>
      <p>{{ t('billing.accounting') }}</p>
      <p>{{ t('billing.limits') }}</p>
      <p>{{ t('finance.gateScope') }}</p>
      <p class="break-words">{{ t('billing.setup') }}</p>
    </details>
    <p v-if="loading" role="status">{{ t('common.loading') }}</p>
    <div v-if="failed" role="alert">
      <p>{{ t('billing.loadFailed') }}</p>
      <UiButton :disabled="busy || scheduleEditing" @click="load()">{{
        t('common.retry')
      }}</UiButton>
    </div>
    <template v-if="data">
      <p
        v-if="!data.credential_configured || (data.config && !data.can_sync)"
        class="text-ink-text-secondary"
      >
        {{ t('billing.notReady') }}
      </p>
      <p class="break-all">
        {{ t('billing.organization') }}：{{
          data.config?.organization_id || data.organization_id || t('finance.notSet')
        }}
      </p>
      <template v-if="data.config">
        <p class="break-all">{{ t('billing.project') }}：{{ data.config.project_id }}</p>
        <p>
          {{ t('billing.start') }}：{{ data.config.start_date }} ·
          {{ t('finance.version', { n: data.config.revision }) }}
        </p>
        <p>{{ t('billing.limit') }}：{{ data.config.limit_amount ?? t('finance.notSet') }}</p>
        <p>{{ t('billing.freshness') }}：{{ data.config.max_age_hours }}</p>
        <p>{{ t(data.config.enforcement_enabled ? 'finance.enforced' : 'finance.disabled') }}</p>
      </template>
      <dl>
        <dt>{{ t('billing.amount') }}</dt>
        <dd class="break-all">{{ data.snapshot?.amount ?? t('billing.unknown') }}</dd>
      </dl>
      <p role="status">{{ t(`billing.states.${data.state}`) }}</p>
      <p v-if="data.snapshot_valid_until" class="text-caption">
        {{ t('billing.validUntil', { time: formatDateTime(data.snapshot_valid_until) }) }}
      </p>
      <p :role="data.admission_blocked ? 'alert' : 'status'">
        {{
          t(
            data.reconciliation_blocked && !data.cost_admission_blocked
              ? 'billing.reconciliation.blocked'
              : data.admission_blocked
                ? 'billing.gateBlocked'
                : 'billing.gateOpen',
          )
        }}
      </p>
      <template v-if="data.snapshot">
        <p class="break-words">
          {{
            t('billing.window', {
              start: utc(data.snapshot.start_time),
              end: utc(data.snapshot.end_time),
            })
          }}
        </p>
        <p>
          {{ t('billing.timestamp', { time: formatDateTime(data.snapshot.finished_at ?? '') }) }}
        </p>
        <UiButton
          variant="secondary"
          :disabled="evidenceLoading"
          @click="showEvidence(data.snapshot.id)"
          >{{ t('billing.evidence') }}</UiButton
        >
      </template>
      <p class="text-caption">{{ t('billing.readAt', { time: formatDateTime(data.read_at) }) }}</p>
      <div v-if="!editing" class="flex flex-wrap gap-ink-2">
        <UiButton
          :disabled="
            busy ||
            scheduleEditing ||
            reconciliationEditing ||
            (!data.organization_id && !data.config)
          "
          @click="edit"
          >{{ t('billing.configure') }}</UiButton
        >
        <UiButton
          :disabled="busy || scheduleEditing || reconciliationEditing || !data.can_sync"
          @click="sync"
          >{{ t(busy ? 'billing.syncing' : 'billing.sync') }}</UiButton
        >
        <UiButton
          variant="ghost"
          :disabled="busy || scheduleEditing || reconciliationEditing"
          @click="load()"
          >{{ t('study.refresh') }}</UiButton
        >
      </div>
      <p class="text-caption">{{ t('billing.syncHint') }}</p>
    </template>
    <StudyBillingSchedule
      :study-id="studyId"
      :config-revision="data?.config?.revision ?? null"
      :disabled="busy || editing || reconciliationEditing"
      @editing="scheduleEditing = $event"
      @saved="load(true)"
    />
    <StudyBillingReconciliation
      :study-id="studyId"
      :snapshots="reconciliationSnapshots"
      :read-at="data?.read_at ?? ''"
      :disabled="busy || editing || scheduleEditing"
      @editing="reconciliationEditing = $event"
      @saved="load(true)"
      @evidence="showEvidence($event)"
    />
    <form
      v-if="editing"
      class="space-y-ink-3 border-t border-ink-border pt-ink-3"
      @submit.prevent="save"
    >
      <h4 class="font-medium">{{ t('billing.configure') }}</h4>
      <p>{{ t('billing.periodHint') }}</p>
      <fieldset :disabled="busy" class="space-y-ink-3">
        <label class="block"
          >{{ t('billing.project')
          }}<UiInput v-model="project" class="w-full" maxlength="125" required
        /></label>
        <label class="block"
          >{{ t('billing.start') }}<UiInput v-model="start" class="w-full" type="date" required
        /></label>
        <label class="block"
          >{{ t('billing.limit')
          }}<UiInput v-model="limit" class="w-full" inputmode="decimal" maxlength="16"
        /></label>
        <label class="block"
          >{{ t('billing.freshness')
          }}<UiInput v-model="hours" class="w-full" inputmode="numeric" maxlength="2" required
        /></label>
        <UiCheckbox v-model="enabled" :label="t('billing.enforce')" />
        <p>{{ t('billing.limits') }}</p>
        <label class="block"
          >{{ t('finance.changeReason')
          }}<UiTextarea v-model="reason" class="w-full" maxlength="1000" required
        /></label>
      </fieldset>
      <div class="flex flex-wrap gap-ink-2">
        <UiButton type="submit" :disabled="busy">{{
          t(busy ? 'finance.saving' : 'finance.confirmSave')
        }}</UiButton>
        <UiButton variant="secondary" :disabled="busy" @click="discard">{{
          t('finance.discard')
        }}</UiButton>
        <UiButton v-if="error" variant="ghost" :disabled="busy || loading" @click="reloadConfig">{{
          t('billing.reload')
        }}</UiButton>
      </div>
    </form>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="message" role="status">{{ message }}</p>
    <details v-if="data" class="space-y-ink-2">
      <summary class="cursor-pointer text-ink-accent">{{ t('billing.configHistory') }}</summary>
      <p>{{ t('billing.historyScope') }}</p>
      <article
        v-for="version in data.config_history"
        :key="version.revision"
        class="space-y-ink-2 border-t border-ink-border py-ink-2"
      >
        <p>
          {{ t('finance.version', { n: version.revision }) }} ·
          {{ formatDateTime(version.created_at) }}
        </p>
        <p class="break-all">{{ version.organization_id }} / {{ version.project_id }}</p>
        <p>
          {{ t('billing.start') }}：{{ version.start_date }} ·
          {{ version.limit_amount ?? t('finance.notSet') }} USD
        </p>
        <p>
          {{ t(version.enforcement_enabled ? 'finance.enforced' : 'finance.disabled') }} ·
          {{ t('billing.freshness') }}：{{ version.max_age_hours }}
        </p>
        <p class="whitespace-pre-wrap break-words">{{ version.reason }}</p>
      </article>
    </details>
    <details v-if="data" class="space-y-ink-2">
      <summary class="cursor-pointer text-ink-accent">{{ t('billing.history') }}</summary>
      <p>{{ t('billing.historyScope') }}</p>
      <p v-if="!data.history.length">{{ t('billing.noHistory') }}</p>
      <article
        v-for="attempt in data.history"
        :key="attempt.id"
        class="space-y-ink-2 border-t border-ink-border py-ink-2"
      >
        <p>
          {{ formatDateTime(attempt.started_at) }} · {{ t(`billing.status.${attempt.status}`) }} ·
          {{ t('finance.version', { n: attempt.revision }) }}
        </p>
        <p>
          {{ t(`billing.triggers.${attempt.trigger}`)
          }}<span v-if="attempt.schedule_revision">
            · {{ t('billing.schedule.linkedRevision', { n: attempt.schedule_revision }) }}</span
          >
        </p>
        <p class="break-all">{{ attempt.organization_id }} / {{ attempt.project_id }}</p>
        <p>
          {{ t('billing.window', { start: utc(attempt.start_time), end: utc(attempt.end_time) }) }}
        </p>
        <p v-if="attempt.error_code">{{ syncError(attempt.error_code) }}</p>
        <UiButton variant="ghost" :disabled="evidenceLoading" @click="showEvidence(attempt.id)">{{
          t('billing.evidence')
        }}</UiButton>
      </article>
    </details>
    <section
      v-if="evidenceId"
      ref="evidenceSection"
      tabindex="-1"
      :aria-label="t('billing.evidenceTitle')"
      class="space-y-ink-3 border border-ink-border p-ink-3"
      :aria-busy="evidenceLoading"
    >
      <h4 class="font-medium">{{ t('billing.evidenceTitle') }}</h4>
      <UiButton variant="ghost" @click="closeEvidence">{{ t('billing.closeEvidence') }}</UiButton>
      <p v-if="evidenceLoading" role="status">{{ t('common.loading') }}</p>
      <div v-if="evidenceFailed" role="alert">
        <p>{{ t('billing.evidenceFailed') }}</p>
        <UiButton @click="showEvidence(evidenceId, evidencePage)">{{ t('common.retry') }}</UiButton>
      </div>
      <template v-if="evidence">
        <p class="break-all">
          {{ evidence.organization_id }} / {{ evidence.project_id }} · {{ evidence.id }}
        </p>
        <p class="break-all">{{ evidence.source_url }}</p>
        <p>
          {{
            t('billing.window', { start: utc(evidence.start_time), end: utc(evidence.end_time) })
          }}
        </p>
        <p>
          {{ t('finance.version', { n: evidence.revision }) }} ·
          {{ evidence.limit_amount ?? t('finance.notSet') }} USD ·
          {{ t(evidence.enforcement_enabled ? 'finance.enforced' : 'finance.disabled') }}
        </p>
        <p class="whitespace-pre-wrap break-words">{{ evidence.reason }}</p>
        <p>
          {{ t(`billing.status.${evidence.status}`) }} ·
          {{ evidence.amount ?? t('billing.unknown') }} USD
        </p>
        <p v-if="evidence.error_code">{{ syncError(evidence.error_code) }}</p>
        <p>
          {{ t(`billing.triggers.${evidence.trigger}`)
          }}<span v-if="evidence.schedule_revision">
            · {{ t('billing.schedule.linkedRevision', { n: evidence.schedule_revision }) }}</span
          >
        </p>
        <p v-if="evidence.status === 'succeeded'">
          {{ t('billing.recordCount', { n: evidence.total }) }}
        </p>
        <p v-if="!evidence.total && evidence.status === 'succeeded'">{{ t('billing.empty') }}</p>
        <p v-else-if="evidence.total && !evidence.items.length">{{ t('operations.pageEmpty') }}</p>
        <article
          v-for="(item, index) in evidence.items"
          :key="index"
          class="border-t border-ink-border py-ink-2"
        >
          <p class="break-words">
            {{ item.line_item ?? t('billing.lineItem') }} · {{ item.amount }} {{ item.currency }}
          </p>
          <p>{{ t('billing.window', { start: utc(item.start_time), end: utc(item.end_time) }) }}</p>
        </article>
        <UiPagination
          v-if="evidence.total"
          :page="evidence.page"
          :page-size="20"
          :total="evidence.total"
          fixed-page-size
          @update:page="(page) => showEvidence(evidenceId, page)"
        />
      </template>
    </section>
  </section>
</template>
