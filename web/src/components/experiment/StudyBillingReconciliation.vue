<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, shallowRef, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  billingReconciliationApi as api,
  type CsvColumnRole,
  type ReconciliationCsv,
  type ReconciliationInput,
  type ReconciliationOverview,
  type ReconciliationRecord,
  type ReconciliationResult,
  type ReconciliationReview,
  type ReconciliationSnapshot,
  type ReviewAction,
} from '@/api/billingReconciliationApi'
import { useDesktopLifecycle } from '@/stores/useDesktopLifecycle'
import { confirmDialog } from '@/components/ui/confirm'
import { getErrorMessage } from '@/utils/error'
import { formatDateTime } from '@/utils/format'
import UiButton from '@/components/ui/Button.vue'
import UiInput from '@/components/ui/Input.vue'
import UiTextarea from '@/components/ui/Textarea.vue'
import UiCheckbox from '@/components/ui/Checkbox.vue'
import UiSelect from '@/components/ui/Select.vue'
import UiPagination from '@/components/ui/Pagination.vue'
import BillingReconciliationResult from './BillingReconciliationResult.vue'

const props = defineProps<{
  studyId: string
  snapshots: ReconciliationSnapshot[]
  readAt: string
  disabled: boolean
}>()
const emit = defineEmits<{ editing: [value: boolean]; saved: []; evidence: [attemptId: string] }>()
const { t } = useI18n()
const data = ref<ReconciliationOverview | null>(null),
  page = ref(1),
  loading = ref(false),
  failed = ref(false)
const mode = ref<'entry' | 'csv' | 'policy' | 'review' | null>(null),
  busy = ref(false),
  error = ref(''),
  saved = ref(false)
const preview = ref<ReconciliationResult | null>(null),
  requestId = ref('')
const csvFile = shallowRef<{ filename: string; content_base64: string; headers: string[] } | null>(
  null,
)
const previewCsv = shallowRef<ReconciliationCsv | null>(null)
const selectedColumns = reactive<Record<CsvColumnRole, string>>({
  amount: '',
  date: '',
  organization: '',
  project: '',
  currency: '',
})
const csvRoles = Object.keys(selectedColumns) as CsvColumnRole[]
const policyEnabled = ref(false),
  policyRevision = ref(0),
  reason = ref('')
const reviewTarget = ref<ReconciliationRecord | null>(null),
  action = ref<ReviewAction>('resolve')
const reviews = ref<Record<string, ReconciliationReview[]>>({}),
  detailLoading = ref('')
const form = reactive<ReconciliationInput>({
  attempt_id: '',
  source_type: 'cost_export',
  source_reference: '',
  organization_id: '',
  project_id: null,
  currency: 'USD',
  source_amount: '',
  period_start: '',
  period_end: '',
  scope_note: '',
})
const active = computed(() => mode.value !== null || busy.value)
const entryMode = computed(() => mode.value === 'entry' || mode.value === 'csv')
const unregister = useDesktopLifecycle().registerBlocker(() => active.value)
let generation = 0,
  disposed = false,
  previewGeneration = 0
const utcDate = (value: number) => new Date(value * 1000).toISOString().slice(0, 10)
const snapshotOptions = computed(() =>
  props.snapshots.map((s) => ({
    value: s.id,
    label: t('billing.reconciliation.snapshotChoice', {
      revision: s.revision,
      project: s.project_id,
      time: new Date(s.end_time * 1000).toISOString().replace('T', ' ').replace('.000Z', ''),
    }),
  })),
)
const sourceOptions = computed(() =>
  (['cost_export', 'invoice_project_subtotal', 'invoice_total', 'payment_receipt'] as const).map(
    (value) => ({ value, label: t(`billing.reconciliation.types.${value}`) }),
  ),
)
const currencies = ['USD', 'CNY', 'EUR'].map((value) => ({ value, label: value }))

async function load(quiet = false) {
  const token = ++generation,
    id = props.studyId,
    requestedPage = page.value
  if (!quiet) data.value = null
  loading.value = true
  failed.value = false
  try {
    const result = (await api.get(id, requestedPage)).data
    if (disposed || token !== generation) return
    if (result.study_id !== id || result.page !== requestedPage)
      throw new Error('Reconciliation scope mismatch')
    data.value = result
  } catch {
    if (!disposed && token === generation) {
      failed.value = true
      data.value = null
    }
  } finally {
    if (!disposed && token === generation) loading.value = false
  }
}
function chooseSnapshot(id: string) {
  const source = props.snapshots.find((item) => item.id === id)
  if (!source) return
  form.attempt_id = id
  if (mode.value === 'csv') return
  form.organization_id = source.organization_id
  form.project_id = source.project_id
  form.period_start = utcDate(source.start_time)
  form.period_end = utcDate(source.end_time)
}
function create(next: 'entry' | 'csv') {
  if (!props.snapshots.length) return
  mode.value = next
  Object.assign(form, {
    source_type: 'cost_export',
    source_reference: '',
    source_amount: '',
    scope_note: '',
    currency: 'USD',
    organization_id: '',
    project_id: null,
    period_start: '',
    period_end: '',
  })
  chooseSnapshot(props.snapshots[0]!.id)
  error.value = ''
  saved.value = false
  preview.value = null
  requestId.value = crypto.randomUUID()
}
async function readCsv(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file || busy.value || props.disabled) return
  target.value = ''
  const previous = csvFile.value?.filename
  clearCsv()
  if (form.source_reference === previous) form.source_reference = ''
  error.value = ''
  if (!/\.csv$/i.test(file.name) || file.size === 0 || file.size > 512 * 1024) {
    error.value = t('billing.reconciliation.csv.invalidFile')
    return
  }
  const id = props.studyId
  const token = generation
  busy.value = true
  try {
    const bytes = new Uint8Array(await file.arrayBuffer())
    let binary = ''
    for (let start = 0; start < bytes.length; start += 8192) {
      binary += String.fromCharCode(...bytes.subarray(start, start + 8192))
    }
    if (disposed || token !== generation) return
    const content_base64 = btoa(binary)
    const { data: headers } = await api.csvColumns(id, content_base64)
    if (disposed || token !== generation) return
    csvFile.value = { filename: file.name, content_base64, headers }
    form.source_reference ||= file.name
  } catch (err) {
    if (!disposed && token === generation)
      error.value = getErrorMessage(err, t('billing.reconciliation.csv.invalidFile'))
  } finally {
    if (!disposed && token === generation) busy.value = false
  }
}
function clearCsv() {
  csvFile.value = null
  previewCsv.value = null
  for (const role of csvRoles) selectedColumns[role] = ''
}
function csvRequest(): ReconciliationCsv | null {
  if (!csvFile.value || !selectedColumns.amount || !selectedColumns.date) return null
  return {
    filename: csvFile.value.filename,
    content_base64: csvFile.value.content_base64,
    amount_column: selectedColumns.amount,
    date_column: selectedColumns.date,
    organization_column: selectedColumns.organization || null,
    project_column: selectedColumns.project || null,
    currency_column: selectedColumns.currency || null,
  }
}
function editPolicy() {
  policyEnabled.value = !!data.value?.policy?.enabled
  policyRevision.value = data.value?.policy?.revision ?? 0
  reason.value = error.value = ''
  saved.value = false
  mode.value = 'policy'
}
function editReview(record: ReconciliationRecord, next: ReviewAction) {
  reviewTarget.value = record
  action.value = next
  reason.value = error.value = ''
  saved.value = false
  mode.value = 'review'
}
function discard() {
  clearCsv()
  mode.value = null
  preview.value = null
  error.value = ''
  previewGeneration++
}
async function reload() {
  if (!(await confirmDialog(t('billing.reconciliation.leave')))) return
  discard()
  await load()
}
async function makePreview() {
  if (busy.value || props.disabled) return
  const csv = mode.value === 'csv' ? csvRequest() : null
  if (mode.value === 'csv' && (!csv || !form.project_id?.trim())) {
    error.value = t('billing.reconciliation.csv.required')
    return
  }
  if (
    !form.source_reference.trim() ||
    !form.organization_id.trim() ||
    !form.scope_note.trim() ||
    !form.period_start ||
    !form.period_end ||
    (!csv && !/^-?(0|[1-9]\d{0,11})(\.\d{1,18})?$/.test(form.source_amount))
  ) {
    error.value = t(csv ? 'billing.reconciliation.csv.required' : 'billing.reconciliation.invalid')
    return
  }
  const id = props.studyId,
    token = ++previewGeneration
  const input: ReconciliationInput = { ...form, project_id: form.project_id?.trim() || null }
  busy.value = true
  error.value = ''
  preview.value = null
  try {
    const result = (await api.preview(id, csv ? { ...input, source_amount: null, csv } : input))
      .data
    if (!disposed && id === props.studyId && token === previewGeneration) {
      preview.value = result
      previewCsv.value = csv
    }
  } catch (err) {
    if (!disposed && id === props.studyId && token === previewGeneration)
      error.value = getErrorMessage(err, t('finance.saveFailed'))
  } finally {
    if (!disposed && id === props.studyId) busy.value = false
  }
}
async function persist() {
  if (busy.value || props.disabled) return
  const id = props.studyId
  if (entryMode.value && !preview.value) return
  if (!entryMode.value && !reason.value.trim()) return
  busy.value = true
  error.value = ''
  try {
    if (entryMode.value && preview.value) {
      const input = {
        ...preview.value.input,
        request_id: requestId.value,
        expected_preview_hash: preview.value.preview_hash,
      }
      await api.save(
        id,
        previewCsv.value ? { ...input, source_amount: null, csv: previewCsv.value } : input,
      )
    } else if (mode.value === 'policy') {
      await api.policy(id, {
        expected_revision: policyRevision.value,
        enabled: policyEnabled.value,
        reason: reason.value.trim(),
      })
    } else if (mode.value === 'review' && reviewTarget.value) {
      await api.review(id, reviewTarget.value.id, {
        expected_revision: reviewTarget.value.review_revision,
        action: action.value,
        reason: reason.value.trim(),
      })
    } else return
    if (disposed || id !== props.studyId) return
    clearCsv()
    mode.value = null
    preview.value = null
    saved.value = true
    reviews.value = {}
    page.value = 1
    await load(true)
    if (!disposed && id === props.studyId) emit('saved')
  } catch (err) {
    if (!disposed && id === props.studyId)
      error.value = getErrorMessage(err, t('finance.saveFailed'))
  } finally {
    if (!disposed && id === props.studyId) busy.value = false
  }
}
async function readReviews(recordId: string) {
  const id = props.studyId
  detailLoading.value = recordId
  error.value = ''
  try {
    const result = (await api.detail(id, recordId)).data
    if (disposed || id !== props.studyId) return
    if (result.study_id !== id || result.id !== recordId) throw new Error('Review scope mismatch')
    reviews.value[recordId] = result.reviews
  } catch (err) {
    if (!disposed && id === props.studyId)
      error.value = getErrorMessage(err, t('billing.reconciliation.loadFailed'))
  } finally {
    if (!disposed && id === props.studyId) detailLoading.value = ''
  }
}
async function changePage(value: number) {
  if (active.value || loading.value) return
  page.value = value
  await load()
}
async function canLeave() {
  return !busy.value && (!mode.value || (await confirmDialog(t('billing.reconciliation.leave'))))
}
function protect(event: BeforeUnloadEvent) {
  if (active.value) {
    event.preventDefault()
    event.returnValue = ''
  }
}
onBeforeRouteLeave(canLeave)
onBeforeRouteUpdate(canLeave)
window.addEventListener('beforeunload', protect)
watch(active, (value) => emit('editing', value))
watch([form, selectedColumns, csvFile], () => {
  previewGeneration++
  preview.value = null
  previewCsv.value = null
  requestId.value = crypto.randomUUID()
})
watch(
  () => props.readAt,
  () => {
    if (!active.value && !props.disabled) void load(true)
  },
)
watch(
  () => props.studyId,
  () => {
    discard()
    busy.value = false
    saved.value = false
    page.value = 1
    reviews.value = {}
    void load()
  },
  { immediate: true },
)
onBeforeUnmount(() => {
  disposed = true
  generation++
  previewGeneration++
  unregister()
  window.removeEventListener('beforeunload', protect)
  emit('editing', false)
})
</script>

<template>
  <section class="space-y-ink-3 border-t border-ink-border pt-ink-3" :aria-busy="loading || busy">
    <h4 class="font-medium">{{ t('billing.reconciliation.title') }}</h4>
    <p>{{ t('billing.reconciliation.scope') }}</p>
    <details class="space-y-ink-2">
      <summary class="cursor-pointer text-ink-accent">
        {{ t('billing.reconciliation.method') }}
      </summary>
      <p>{{ t('billing.reconciliation.methodText') }}</p>
      <p>{{ t('billing.reconciliation.limitation') }}</p>
    </details>
    <p v-if="failed" role="alert">{{ t('billing.reconciliation.loadFailed') }}</p>
    <template v-if="data">
      <p>{{ t('billing.reconciliation.pending', { n: data.pending_count }) }}</p>
      <p>
        {{ t(data.policy?.enabled ? 'finance.enforced' : 'finance.disabled') }} ·
        {{ t('billing.reconciliation.policyTitle') }}
      </p>
      <p role="status">
        {{
          t(
            data.admission_blocked
              ? 'billing.reconciliation.blocked'
              : 'billing.reconciliation.notBlocked',
          )
        }}
      </p>
      <p class="text-caption">
        {{ t('billing.reconciliation.readAt', { time: formatDateTime(data.read_at) }) }}
      </p>
    </template>
    <div v-if="!mode" class="flex flex-wrap gap-ink-2">
      <UiButton
        :disabled="disabled || busy || loading || !snapshots.length"
        @click="create('entry')"
        >{{ t('billing.reconciliation.create') }}</UiButton
      >
      <UiButton
        variant="secondary"
        :disabled="disabled || busy || loading || !snapshots.length"
        @click="create('csv')"
        >{{ t('billing.reconciliation.csv.create') }}</UiButton
      >
      <UiButton
        variant="secondary"
        :disabled="disabled || busy || loading || !data"
        @click="editPolicy"
        >{{ t('billing.reconciliation.policyEdit') }}</UiButton
      >
      <UiButton variant="ghost" :disabled="disabled || busy || loading" @click="load()">{{
        t('billing.reconciliation.refresh')
      }}</UiButton>
    </div>
    <p v-if="!snapshots.length">{{ t('billing.reconciliation.noSnapshot') }}</p>
    <form v-if="entryMode" class="space-y-ink-3" @submit.prevent="makePreview">
      <fieldset :disabled="busy || disabled" class="space-y-ink-3">
        <label class="block"
          >{{ t('billing.reconciliation.sourceSnapshot')
          }}<UiSelect
            :model-value="form.attempt_id"
            :options="snapshotOptions"
            class="w-full"
            :disabled="busy || disabled"
            @update:model-value="chooseSnapshot"
        /></label>
        <template v-if="mode === 'csv'">
          <p>{{ t('billing.reconciliation.csv.instructions') }}</p>
          <label class="block">
            {{ t('billing.reconciliation.csv.file') }}
            <input
              type="file"
              accept=".csv,text/csv"
              class="ink-input block w-full"
              @change="readCsv"
            />
          </label>
          <template v-if="csvFile">
            <p class="break-words" role="status">{{ csvFile.filename }}</p>
            <div class="grid gap-ink-3 sm:grid-cols-2">
              <label v-for="role in csvRoles" :key="role" class="min-w-0">
                {{ t(`billing.reconciliation.csv.columns.${role}`) }}
                <select
                  v-model="selectedColumns[role]"
                  class="ink-input block w-full"
                  :required="role === 'amount' || role === 'date'"
                >
                  <option value="">
                    {{
                      t(
                        role === 'amount' || role === 'date'
                          ? 'common.select'
                          : 'billing.reconciliation.csv.declared',
                      )
                    }}
                  </option>
                  <option v-for="header in csvFile.headers" :key="header" :value="header">
                    {{ header }}
                  </option>
                </select>
              </label>
            </div>
          </template>
        </template>
        <label v-else class="block"
          >{{ t('billing.reconciliation.sourceType')
          }}<UiSelect
            v-model="form.source_type"
            :options="sourceOptions"
            class="w-full"
            :disabled="busy || disabled"
        /></label>
        <label class="block"
          >{{ t('billing.reconciliation.reference')
          }}<UiInput v-model="form.source_reference" class="w-full" maxlength="300" required
        /></label>
        <label class="block"
          >{{ t('billing.reconciliation.organization')
          }}<UiInput v-model="form.organization_id" class="w-full" maxlength="128" required
        /></label>
        <label class="block"
          >{{
            t(
              mode === 'csv'
                ? 'billing.reconciliation.csv.project'
                : 'billing.reconciliation.project',
            )
          }}<UiInput
            :model-value="form.project_id ?? ''"
            class="w-full"
            maxlength="128"
            :required="mode === 'csv'"
            @update:model-value="form.project_id = String($event) || null"
        /></label>
        <label class="block"
          >{{ t('billing.reconciliation.currency')
          }}<UiSelect
            v-model="form.currency"
            :options="currencies"
            class="w-full"
            :disabled="busy || disabled"
        /></label>
        <label v-if="mode !== 'csv'" class="block"
          >{{ t('billing.reconciliation.amount')
          }}<UiInput
            v-model="form.source_amount"
            class="w-full"
            inputmode="decimal"
            maxlength="32"
            required
        /></label>
        <div class="grid gap-ink-3 sm:grid-cols-2">
          <label class="block"
            >{{ t('billing.reconciliation.start')
            }}<UiInput v-model="form.period_start" class="w-full" type="date" required /></label
          ><label class="block"
            >{{ t('billing.reconciliation.end')
            }}<UiInput v-model="form.period_end" class="w-full" type="date" required
          /></label>
        </div>
        <p>{{ t('billing.reconciliation.dates') }}</p>
        <label class="block"
          >{{ t('billing.reconciliation.note')
          }}<UiTextarea v-model="form.scope_note" class="w-full" maxlength="2000" required
        /></label>
        <p>{{ t('billing.reconciliation.noteHint') }}</p>
      </fieldset>
      <div class="flex flex-wrap gap-ink-2">
        <UiButton type="submit" :disabled="busy || disabled">{{
          t('billing.reconciliation.preview')
        }}</UiButton
        ><UiButton variant="secondary" :disabled="busy" @click="discard">{{
          t('finance.discard')
        }}</UiButton>
      </div>
      <template v-if="preview"
        ><p>{{ t('billing.reconciliation.previewOnly') }}</p>
        <BillingReconciliationResult
          :result="preview"
          :disabled="busy"
          @evidence="emit('evidence', $event)"
        /><UiButton :disabled="busy || disabled" @click="persist">{{
          t('billing.reconciliation.save')
        }}</UiButton></template
      >
    </form>
    <form v-else-if="mode" class="space-y-ink-3" @submit.prevent="persist">
      <template v-if="mode === 'policy'"
        ><h5 class="font-medium">{{ t('billing.reconciliation.policyTitle') }}</h5>
        <UiCheckbox
          v-model="policyEnabled"
          :disabled="busy || disabled"
          :label="t('billing.reconciliation.policyEnable')"
        />
        <p>{{ t('billing.reconciliation.policyHint') }}</p></template
      >
      <template v-else
        ><h5 class="font-medium">{{ t(`billing.reconciliation.actions.${action}`) }}</h5>
        <p>{{ reviewTarget?.comparison.input.source_reference }}</p>
        <p>{{ t('billing.reconciliation.reviewHint') }}</p></template
      >
      <label class="block"
        >{{ t(mode === 'policy' ? 'finance.changeReason' : 'billing.reconciliation.reviewReason')
        }}<UiTextarea
          v-model="reason"
          class="w-full"
          :maxlength="mode === 'policy' ? 1000 : 2000"
          :disabled="busy || disabled"
          required
      /></label>
      <div class="flex flex-wrap gap-ink-2">
        <UiButton type="submit" :disabled="busy || disabled">{{
          t('finance.confirmSave')
        }}</UiButton
        ><UiButton variant="secondary" :disabled="busy" @click="discard">{{
          t('finance.discard')
        }}</UiButton>
      </div>
    </form>
    <p v-if="error" role="alert">{{ error }}</p>
    <UiButton v-if="error && mode" variant="ghost" :disabled="busy" @click="reload">{{
      t('billing.reconciliation.reload')
    }}</UiButton>
    <p v-if="saved" role="status">{{ t('billing.reconciliation.saved') }}</p>
    <template v-if="data && !mode">
      <details class="space-y-ink-2">
        <summary class="cursor-pointer text-ink-accent">
          {{ t('billing.reconciliation.policyHistory') }}
        </summary>
        <article v-for="policy in data.policy_history" :key="policy.revision" class="space-y-ink-2">
          <p>
            {{ t('finance.version', { n: policy.revision }) }} ·
            {{ t(policy.enabled ? 'finance.enforced' : 'finance.disabled') }} ·
            {{ formatDateTime(policy.created_at) }}
          </p>
          <p class="whitespace-pre-wrap break-words">{{ policy.reason }}</p>
        </article>
      </details>
      <h5 class="font-medium">{{ t('billing.reconciliation.history') }}</h5>
      <p v-if="!data.records.length">{{ t('billing.reconciliation.noRecords') }}</p>
      <article
        v-for="record in data.records"
        :key="record.id"
        class="space-y-ink-2 border-t border-ink-border py-ink-2"
      >
        <p class="font-medium break-words">{{ record.comparison.input.source_reference }}</p>
        <p>
          {{ t(`billing.reconciliation.result.${record.comparison.result}`) }} ·
          {{
            t(
              `billing.reconciliation.review.${record.review_action ?? (record.pending ? 'pending' : 'matched')}`,
            )
          }}
        </p>
        <p class="break-words">
          {{
            t('billing.reconciliation.recordTime', {
              time: formatDateTime(record.created_at),
              id: record.id,
            })
          }}
        </p>
        <p v-if="record.review_reason" class="whitespace-pre-wrap break-words">
          {{ record.review_reason }}
        </p>
        <details class="space-y-ink-2">
          <summary class="cursor-pointer text-ink-accent">
            {{ t('billing.reconciliation.details') }}
          </summary>
          <BillingReconciliationResult
            :result="record.comparison"
            @evidence="emit('evidence', $event)"
          />
        </details>
        <div v-if="record.review_action !== 'void'" class="flex flex-wrap gap-ink-2">
          <UiButton
            v-if="record.pending"
            :disabled="disabled || loading"
            @click="editReview(record, 'resolve')"
            >{{ t('billing.reconciliation.actions.resolve') }}</UiButton
          ><UiButton
            v-else-if="record.comparison.result !== 'matched'"
            :disabled="disabled || loading"
            @click="editReview(record, 'reopen')"
            >{{ t('billing.reconciliation.actions.reopen') }}</UiButton
          ><UiButton
            variant="ghost"
            :disabled="disabled || loading"
            @click="editReview(record, 'void')"
            >{{ t('billing.reconciliation.actions.void') }}</UiButton
          >
        </div>
        <UiButton variant="ghost" :disabled="!!detailLoading" @click="readReviews(record.id)">{{
          t('billing.reconciliation.reviewHistory')
        }}</UiButton>
        <template v-if="reviews[record.id]"
          ><p v-if="!reviews[record.id]!.length">{{ t('billing.reconciliation.noReviews') }}</p>
          <div v-for="review in reviews[record.id]" :key="review.revision">
            <p>
              {{ t('finance.version', { n: review.revision }) }} ·
              {{ t(`billing.reconciliation.review.${review.action}`) }} ·
              {{ formatDateTime(review.created_at) }}
            </p>
            <p class="whitespace-pre-wrap break-words">{{ review.reason }}</p>
          </div></template
        >
      </article>
      <UiPagination
        :page="page"
        :page-size="10"
        :total="data.total"
        fixed-page-size
        @update:page="changePage"
      />
    </template>
  </section>
</template>
