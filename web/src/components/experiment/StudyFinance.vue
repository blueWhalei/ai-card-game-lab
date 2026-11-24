<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  studyFinanceApi,
  type StudyFinance,
  type Currency,
  type ExpenseSource,
} from '@/api/studyFinanceApi'
import { operationPosition } from '@/utils/studyOperations'
import { formatDateTime } from '@/utils/format'
import { getErrorMessage } from '@/utils/error'
import { confirmDialog } from '@/components/ui/confirm'
import { useDesktopLifecycle } from '@/stores/useDesktopLifecycle'
import UiButton from '@/components/ui/Button.vue'
import UiInput from '@/components/ui/Input.vue'
import UiTextarea from '@/components/ui/Textarea.vue'
import UiCheckbox from '@/components/ui/Checkbox.vue'
import UiPagination from '@/components/ui/Pagination.vue'
import StudyBilling from './StudyBilling.vue'

const props = defineProps<{ studyId: string }>()
const { t } = useI18n(),
  route = useRoute(),
  router = useRouter()
const position = computed(() => operationPosition(route.query))
const data = ref<StudyFinance | null>(null),
  loading = ref(false),
  failed = ref(false)
const saving = ref(false),
  error = ref(''),
  saved = ref(false)
const form = ref<'budget' | 'expense' | 'void' | null>(null)
const currency = ref<Currency>('CNY'),
  limit = ref(''),
  enabled = ref(false),
  reason = ref('')
const revision = ref(0),
  amount = ref(''),
  incurredOn = ref('')
const source = ref<ExpenseSource>('provider_statement'),
  reference = ref(''),
  scope = ref('')
const entryId = ref(''),
  entryReference = ref('')
const sources: ExpenseSource[] = ['provider_statement', 'payment_receipt', 'manual_allocation']
const validAmount = (value: string) => /^(0|[1-9]\d{0,8})(\.\d{1,6})?$/.test(value)
let request = 0,
  disposed = false
let submission: { value: string; key: string } | null = null
const unregister = useDesktopLifecycle().registerBlocker(() => form.value !== null || saving.value)

async function load() {
  const token = ++request,
    id = props.studyId,
    page = position.value?.page
  data.value = null
  failed.value = false
  loading.value = false
  if (!page) return
  loading.value = true
  try {
    const result = (await studyFinanceApi.get(id, page)).data
    if (token !== request) return
    if (result.study_id !== id || result.page !== page) throw new Error('Finance scope mismatch')
    data.value = result
  } catch {
    if (token === request) failed.value = true
  } finally {
    if (token === request) loading.value = false
  }
}
function editBudget() {
  const budget = data.value?.budget
  currency.value = budget?.currency ?? 'CNY'
  limit.value = budget?.limit ?? ''
  enabled.value = budget?.enforcement_enabled ?? false
  revision.value = budget?.revision ?? 0
  reason.value = ''
  error.value = ''
  saved.value = false
  form.value = 'budget'
}
async function reloadBudget() {
  if (!(await confirmDialog(t('finance.replaceInput')))) return
  await load()
  if (data.value) editBudget()
}
function newExpense() {
  if (!data.value?.budget) return
  currency.value = data.value.budget.currency
  amount.value = incurredOn.value = reference.value = scope.value = ''
  source.value = 'provider_statement'
  submission = null
  error.value = ''
  saved.value = false
  form.value = 'expense'
}
function voidExpense(id: string, label: string) {
  entryId.value = id
  entryReference.value = label
  reason.value = ''
  error.value = ''
  saved.value = false
  form.value = 'void'
}
function discard() {
  form.value = null
  error.value = ''
}
async function submit() {
  if (saving.value || !form.value) return
  const kind = form.value,
    id = props.studyId
  if (
    (kind === 'budget' &&
      ((limit.value !== '' && !validAmount(limit.value)) || (enabled.value && !limit.value))) ||
    (kind === 'expense' && !validAmount(amount.value))
  ) {
    error.value = t('finance.invalidAmount')
    return
  }
  if (
    (kind !== 'expense' && !reason.value.trim()) ||
    (kind === 'expense' && (!incurredOn.value || !reference.value.trim() || !scope.value.trim()))
  ) {
    error.value = t('finance.required')
    return
  }
  saving.value = true
  error.value = ''
  try {
    if (kind === 'budget') {
      await studyFinanceApi.setBudget(id, {
        expected_revision: revision.value,
        currency: currency.value,
        limit: limit.value || null,
        enforcement_enabled: enabled.value,
        reason: reason.value.trim(),
      })
    } else if (kind === 'expense') {
      const body = {
        currency: currency.value,
        amount: amount.value,
        incurred_on: incurredOn.value,
        source_type: source.value,
        source_reference: reference.value.trim(),
        scope_description: scope.value.trim(),
      }
      const value = JSON.stringify(body)
      if (submission?.value !== value) submission = { value, key: crypto.randomUUID() }
      await studyFinanceApi.addExpense(id, { ...body, request_id: submission.key })
    } else {
      await studyFinanceApi.voidExpense(id, entryId.value, reason.value.trim())
    }
    if (disposed || id !== props.studyId) return
    form.value = null
    saved.value = true
    await load()
  } catch (err) {
    if (!disposed && id === props.studyId)
      error.value = getErrorMessage(err, t('finance.saveFailed'))
  } finally {
    if (!disposed && id === props.studyId) saving.value = false
  }
}
async function canLeave() {
  return !saving.value && (!form.value || (await confirmDialog(t('finance.leave'))))
}
function protect(event: BeforeUnloadEvent) {
  if (!form.value && !saving.value) return
  event.preventDefault()
  event.returnValue = ''
}
onBeforeRouteLeave(canLeave)
onBeforeRouteUpdate(canLeave)
window.addEventListener('beforeunload', protect)
watch(
  () => props.studyId,
  () => {
    form.value = null
    saved.value = false
    error.value = ''
    saving.value = false
  },
)
watch(() => [props.studyId, route.query.task_page], load, { immediate: true })
onBeforeUnmount(() => {
  disposed = true
  request++
  unregister()
  window.removeEventListener('beforeunload', protect)
})
</script>

<template>
  <section class="space-y-ink-4 text-body" :aria-busy="loading || saving">
    <StudyBilling v-if="position" :study-id="studyId" />
    <h3 class="font-medium">{{ t('billing.manualTitle') }}</h3>
    <p class="text-ink-text-secondary">{{ t('finance.scope') }}</p>
    <details class="space-y-ink-2">
      <summary class="cursor-pointer text-ink-accent">{{ t('finance.method') }}</summary>
      <p>{{ t('finance.accounting') }}</p>
      <p>{{ t('finance.limits') }}</p>
    </details>
    <p v-if="!position" role="alert">{{ t('operations.invalidPosition') }}</p>
    <p v-if="loading" role="status">{{ t('common.loading') }}</p>
    <div v-if="failed" role="alert" class="space-y-ink-2">
      <p>{{ t('finance.loadFailed') }}</p>
      <UiButton :disabled="saving" @click="load">{{ t('common.retry') }}</UiButton>
    </div>
    <p v-if="saved" role="status">{{ t('finance.saved') }}</p>
    <template v-if="data">
      <p class="text-caption text-ink-text-secondary">
        {{ t('finance.readAt', { time: formatDateTime(data.read_at) }) }}
      </p>
      <dl class="grid gap-ink-3 sm:grid-cols-2">
        <div>
          <dt>{{ t('finance.budget') }}</dt>
          <dd class="break-all">
            {{ data.budget?.limit ?? t('finance.notSet') }} {{ data.budget?.currency }}
          </dd>
        </div>
        <div>
          <dt>{{ t('finance.recorded') }}</dt>
          <dd class="break-all">
            {{ data.recorded_amount ?? t('finance.noAmount') }} {{ data.budget?.currency }}
          </dd>
        </div>
        <div>
          <dt>{{ t('finance.difference') }}</dt>
          <dd class="break-all">
            {{ data.budget_difference ?? t('finance.unavailable') }} {{ data.budget?.currency }}
          </dd>
        </div>
        <div>
          <dt>{{ t('finance.countsTitle') }}</dt>
          <dd>
            {{ t('finance.counts', { active: data.active_count, voided: data.voided_count }) }}
          </dd>
        </div>
      </dl>
      <p :role="data.admission_blocked ? 'alert' : 'status'">
        {{
          t(
            data.admission_blocked
              ? 'finance.blocked'
              : data.budget?.enforcement_enabled
                ? 'finance.below'
                : 'finance.disabled',
          )
        }}
      </p>
      <p class="text-caption text-ink-text-secondary">{{ t('finance.gateScope') }}</p>
      <div v-if="!form" class="flex flex-wrap gap-ink-2">
        <UiButton @click="editBudget">{{ t('finance.editBudget') }}</UiButton>
        <UiButton :disabled="!data.budget" @click="newExpense">{{
          t('finance.addExpense')
        }}</UiButton>
        <UiButton variant="ghost" @click="load">{{ t('study.refresh') }}</UiButton>
      </div>
      <p v-if="!data.budget" class="text-caption">{{ t('finance.setCurrencyFirst') }}</p>
    </template>
    <form
      v-if="form"
      class="space-y-ink-3 border-t border-ink-border pt-ink-4"
      @submit.prevent="submit"
    >
      <h3 class="font-medium">{{ t(`finance.forms.${form}`) }}</h3>
      <p>{{ t('finance.explicitSave') }}</p>
      <fieldset :disabled="saving" class="space-y-ink-3">
        <template v-if="form === 'budget'">
          <label class="block space-y-ink-1"
            >{{ t('finance.currency') }}
            <select v-model="currency" class="ink-input block w-full" :disabled="!!data?.budget">
              <option>CNY</option>
              <option>USD</option>
              <option>EUR</option>
            </select>
          </label>
          <label class="block space-y-ink-1"
            >{{ t('finance.limitInput')
            }}<UiInput v-model="limit" class="w-full" inputmode="decimal" maxlength="16"
          /></label>
          <UiCheckbox v-model="enabled" :label="t('finance.enforce')" />
          <p class="text-caption">{{ t('finance.limits') }}</p>
        </template>
        <template v-else-if="form === 'expense'">
          <p>{{ t('finance.currency') }}：{{ currency }}</p>
          <label class="block space-y-ink-1"
            >{{ t('finance.amount')
            }}<UiInput v-model="amount" class="w-full" inputmode="decimal" maxlength="16" required
          /></label>
          <label class="block space-y-ink-1"
            >{{ t('finance.incurredOn')
            }}<UiInput v-model="incurredOn" type="date" class="w-full" required
          /></label>
          <label class="block space-y-ink-1"
            >{{ t('finance.sourceType')
            }}<select v-model="source" class="ink-input block w-full">
              <option v-for="value in sources" :key="value" :value="value">
                {{ t(`finance.sources.${value}`) }}
              </option>
            </select></label
          >
          <label class="block space-y-ink-1"
            >{{ t('finance.sourceReference')
            }}<UiInput v-model="reference" class="w-full" maxlength="200" required
          /></label>
          <p class="text-caption">{{ t('finance.referenceHint') }}</p>
          <label class="block space-y-ink-1"
            >{{ t('finance.scopeDescription')
            }}<UiTextarea v-model="scope" class="w-full" maxlength="2000" required
          /></label>
        </template>
        <p v-else class="break-words">{{ entryReference }} · {{ t('finance.voidHint') }}</p>
        <label v-if="form !== 'expense'" class="block space-y-ink-1"
          >{{ t(form === 'void' ? 'finance.voidReason' : 'finance.changeReason')
          }}<UiTextarea v-model="reason" class="w-full" maxlength="1000" required
        /></label>
      </fieldset>
      <p v-if="error" role="alert">{{ error }}</p>
      <div class="flex flex-wrap gap-ink-2">
        <UiButton type="submit" :disabled="saving">{{
          t(
            saving
              ? 'finance.saving'
              : form === 'void'
                ? 'finance.confirmVoid'
                : 'finance.confirmSave',
          )
        }}</UiButton>
        <UiButton variant="secondary" :disabled="saving" @click="discard">{{
          t('finance.discard')
        }}</UiButton>
        <UiButton
          v-if="form === 'budget' && error"
          variant="ghost"
          :disabled="saving || loading"
          @click="reloadBudget"
          >{{ t('finance.reloadBudget') }}</UiButton
        >
      </div>
    </form>
    <template v-if="data">
      <details v-if="data.budget_history.length" class="space-y-ink-2">
        <summary class="cursor-pointer text-ink-accent">
          {{ t('finance.history', { n: data.budget?.revision }) }}
        </summary>
        <p>{{ t('finance.historyLimit') }}</p>
        <div
          v-for="version in data.budget_history"
          :key="version.revision"
          class="border-t border-ink-border py-ink-2"
        >
          <p>
            {{ t('finance.version', { n: version.revision }) }} ·
            {{ version.limit ?? t('finance.notSet') }} {{ version.currency }} ·
            {{ t(version.enforcement_enabled ? 'finance.enforced' : 'finance.disabled') }}
          </p>
          <p class="whitespace-pre-wrap break-words">{{ version.reason }}</p>
          <p>{{ formatDateTime(version.created_at) }}</p>
        </div>
      </details>
      <h3 class="font-medium">{{ t('finance.records') }}</h3>
      <p v-if="!data.items.length">
        {{ t(data.total ? 'operations.pageEmpty' : 'finance.empty') }}
      </p>
      <article
        v-for="item in data.items"
        :key="item.id"
        class="space-y-ink-2 border-t border-ink-border py-ink-3"
      >
        <h4 class="break-words font-medium">
          {{ item.source_reference }} · {{ item.amount }} {{ item.currency }}
        </h4>
        <p>
          {{ t(`finance.sources.${item.source_type}`) }} · {{ t('finance.incurredOn') }}：{{
            item.incurred_on
          }}
        </p>
        <p class="whitespace-pre-wrap break-words">{{ item.scope_description }}</p>
        <p class="text-caption break-all">
          {{ t('finance.registeredAt', { time: formatDateTime(item.created_at), id: item.id }) }}
        </p>
        <p v-if="item.voided_at" class="whitespace-pre-wrap break-words">
          {{
            t('finance.voided', { time: formatDateTime(item.voided_at), reason: item.void_reason })
          }}
        </p>
        <UiButton
          v-else
          :disabled="!!form || saving"
          size="sm"
          variant="secondary"
          @click="voidExpense(item.id, item.source_reference)"
          >{{ t('finance.void') }}</UiButton
        >
      </article>
      <UiPagination
        v-if="!form"
        :page="data.page"
        :page-size="20"
        :total="data.total"
        fixed-page-size
        @update:page="
          (page) => router.replace({ query: { ...route.query, task_page: String(page) } })
        "
      />
    </template>
  </section>
</template>
