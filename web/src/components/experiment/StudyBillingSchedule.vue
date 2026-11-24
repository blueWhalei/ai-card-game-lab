<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { studyBillingApi, type BillingScheduleOverview } from '@/api/studyBillingApi'
import { useDesktopLifecycle } from '@/stores/useDesktopLifecycle'
import { confirmDialog } from '@/components/ui/confirm'
import { getErrorMessage } from '@/utils/error'
import { formatDateTime } from '@/utils/format'
import UiButton from '@/components/ui/Button.vue'
import UiInput from '@/components/ui/Input.vue'
import UiTextarea from '@/components/ui/Textarea.vue'
import UiCheckbox from '@/components/ui/Checkbox.vue'

const props = defineProps<{ studyId: string; configRevision: number | null; disabled: boolean }>()
const emit = defineEmits<{ editing: [value: boolean]; saved: [] }>()
const { t } = useI18n()
const data = ref<BillingScheduleOverview | null>(null),
  loading = ref(false),
  failed = ref(false)
const editing = ref(false),
  saving = ref(false),
  error = ref(''),
  saved = ref(false)
const enabled = ref(false),
  interval = ref('60'),
  reason = ref(''),
  revision = ref(0),
  capturedConfigRevision = ref(0)
let generation = 0,
  disposed = false
const unregister = useDesktopLifecycle().registerBlocker(() => editing.value || saving.value)

async function load(quiet = false) {
  const token = ++generation,
    id = props.studyId
  if (!quiet) data.value = null
  loading.value = true
  failed.value = false
  try {
    const result = (await studyBillingApi.schedule(id)).data
    if (token !== generation || disposed) return
    if (result.study_id !== id) throw new Error('Schedule scope mismatch')
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
  if (!data.value?.config) return
  const plan = data.value.plan
  revision.value = plan?.revision ?? 0
  capturedConfigRevision.value = data.value.config.revision
  interval.value = String(
    plan?.interval_minutes ?? Math.min(60, data.value.config.max_age_hours * 30),
  )
  enabled.value = !!plan?.enabled
  reason.value = error.value = ''
  saved.value = false
  editing.value = true
}
function discard() {
  editing.value = false
  error.value = ''
}
async function reload() {
  if (!(await confirmDialog(t('billing.schedule.replaceInput')))) return
  const id = props.studyId
  await load()
  if (!disposed && id === props.studyId && data.value) edit()
}
async function save() {
  if (saving.value || props.disabled) return
  const minutes = Number(interval.value)
  if (!/^\d{1,3}$/.test(interval.value) || minutes < 15 || minutes > 720 || !reason.value.trim()) {
    error.value = t('billing.schedule.invalid')
    return
  }
  const id = props.studyId
  saving.value = true
  error.value = ''
  try {
    await studyBillingApi.setSchedule(id, {
      expected_revision: revision.value,
      expected_config_revision: capturedConfigRevision.value,
      enabled: enabled.value,
      interval_minutes: minutes,
      reason: reason.value.trim(),
    })
    if (disposed || id !== props.studyId) return
    editing.value = false
    saved.value = true
    await load()
    if (!disposed && id === props.studyId) emit('saved')
  } catch (err) {
    if (!disposed && id === props.studyId)
      error.value = getErrorMessage(err, t('finance.saveFailed'))
  } finally {
    if (!disposed && id === props.studyId) saving.value = false
  }
}
function refresh() {
  if (!editing.value && !saving.value && !loading.value && !props.disabled && !document.hidden)
    void load(true)
}
const poll = window.setInterval(refresh, 30_000)
document.addEventListener('visibilitychange', refresh)
async function canLeave() {
  return !saving.value && (!editing.value || (await confirmDialog(t('finance.leave'))))
}
function protect(event: BeforeUnloadEvent) {
  if (!editing.value && !saving.value) return
  event.preventDefault()
  event.returnValue = ''
}
window.addEventListener('beforeunload', protect)
onBeforeRouteLeave(canLeave)
onBeforeRouteUpdate(canLeave)
watch([editing, saving], () => emit('editing', editing.value || saving.value))
watch(
  () => props.studyId,
  () => {
    editing.value = saving.value = false
    error.value = ''
    saved.value = false
    void load()
  },
  { immediate: true },
)
watch(
  () => props.configRevision,
  () => {
    if (!editing.value && !saving.value) void load(true)
  },
)
onBeforeUnmount(() => {
  disposed = true
  generation++
  unregister()
  window.clearInterval(poll)
  document.removeEventListener('visibilitychange', refresh)
  window.removeEventListener('beforeunload', protect)
  emit('editing', false)
})
</script>

<template>
  <section class="space-y-ink-3 border-t border-ink-border pt-ink-3" :aria-busy="loading || saving">
    <h4 class="font-medium">{{ t('billing.schedule.title') }}</h4>
    <p>{{ t('billing.schedule.scope') }}</p>
    <details class="space-y-ink-2">
      <summary class="cursor-pointer text-ink-accent">{{ t('billing.schedule.method') }}</summary>
      <p>{{ t('billing.schedule.behavior') }}</p>
      <p>{{ t('billing.schedule.retryPolicy') }}</p>
      <p>{{ t('billing.schedule.budget') }}</p>
    </details>
    <p v-if="failed" role="alert">{{ t('billing.schedule.loadFailed') }}</p>
    <UiButton v-if="failed" :disabled="saving || props.disabled" @click="load()">{{
      t('common.retry')
    }}</UiButton>
    <template v-if="data">
      <p role="status">{{ t(`billing.schedule.states.${data.state}`) }}</p>
      <p v-if="!data.worker_enabled" role="status">{{ t('billing.schedule.workerDisabled') }}</p>
      <p v-else-if="!data.worker_recent" role="status">{{ t('billing.schedule.workerUnknown') }}</p>
      <p>
        {{
          t('billing.schedule.lastCheck', {
            time: data.checked_at ? formatDateTime(data.checked_at) : t('finance.notSet'),
          })
        }}
      </p>
      <p v-if="data.plan">
        {{
          t('billing.schedule.planSummary', {
            revision: data.plan.revision,
            config: data.plan.config_revision,
            minutes: data.plan.interval_minutes,
          })
        }}
      </p>
      <p
        v-if="
          data.plan?.enabled &&
          !['scope_changed', 'running'].includes(data.state) &&
          data.plan.next_due_at
        "
      >
        {{ t('billing.schedule.next', { time: formatDateTime(data.plan.next_due_at) }) }}
      </p>
      <p v-if="data.plan?.consecutive_failures">
        {{ t('billing.schedule.failures', { n: data.plan.consecutive_failures }) }}
      </p>
      <p v-if="data.plan?.error_code">
        {{ getErrorMessage({ code: data.plan.error_code, message: t('billing.syncFailed') }) }}
      </p>
      <p v-if="!data.config">{{ t('billing.schedule.configFirst') }}</p>
      <div v-if="!editing" class="flex flex-wrap gap-ink-2">
        <UiButton :disabled="!data.config || props.disabled || saving" @click="edit">{{
          t('billing.schedule.edit')
        }}</UiButton>
        <UiButton variant="ghost" :disabled="props.disabled || saving" @click="load()">{{
          t('billing.schedule.refresh')
        }}</UiButton>
      </div>
      <p class="text-caption">
        {{ t('billing.schedule.readAt', { time: formatDateTime(data.read_at) }) }}
      </p>
    </template>
    <form v-if="editing" class="space-y-ink-3" @submit.prevent="save">
      <p>{{ t('billing.schedule.binding', { n: capturedConfigRevision }) }}</p>
      <fieldset class="space-y-ink-3" :disabled="saving || props.disabled">
        <UiCheckbox v-model="enabled" :label="t('billing.schedule.enable')" />
        <label class="block"
          >{{ t('billing.schedule.interval')
          }}<UiInput v-model="interval" class="w-full" inputmode="numeric" maxlength="3" required
        /></label>
        <p>{{ t('billing.schedule.intervalHint') }}</p>
        <p>{{ t('billing.schedule.budget') }}</p>
        <label class="block"
          >{{ t('billing.schedule.reason')
          }}<UiTextarea v-model="reason" class="w-full" maxlength="1000" required
        /></label>
      </fieldset>
      <div class="flex flex-wrap gap-ink-2">
        <UiButton type="submit" :disabled="saving || props.disabled">{{
          t(saving ? 'finance.saving' : 'finance.confirmSave')
        }}</UiButton>
        <UiButton variant="secondary" :disabled="saving" @click="discard">{{
          t('finance.discard')
        }}</UiButton>
        <UiButton v-if="error" variant="ghost" :disabled="saving || loading" @click="reload">{{
          t('billing.schedule.reload')
        }}</UiButton>
      </div>
    </form>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="saved" role="status">{{ t('billing.schedule.saved') }}</p>
    <details v-if="data?.history.length" class="space-y-ink-2">
      <summary class="cursor-pointer text-ink-accent">{{ t('billing.schedule.history') }}</summary>
      <p>{{ t('billing.historyScope') }}</p>
      <article
        v-for="version in data.history"
        :key="version.revision"
        class="space-y-ink-2 border-t border-ink-border py-ink-2"
      >
        <p>
          {{
            t('billing.schedule.planSummary', {
              revision: version.revision,
              config: version.config_revision,
              minutes: version.interval_minutes,
            })
          }}
        </p>
        <p>
          {{ t(version.enabled ? 'billing.schedule.enabled' : 'billing.schedule.paused') }} ·
          {{ formatDateTime(version.created_at) }}
        </p>
        <p class="break-all">
          {{ version.organization_id }} / {{ version.project_id }} · {{ version.start_date }} UTC
        </p>
        <p class="whitespace-pre-wrap break-words">{{ version.reason }}</p>
      </article>
    </details>
  </section>
</template>
