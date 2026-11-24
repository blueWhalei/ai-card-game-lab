<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  researchApi,
  type TraceEvidenceReference,
  type ResearchTracePreview,
} from '@/api/researchApi'
import { getErrorMessage } from '@/utils/error'
import UiDialog from '@/components/ui/Dialog.vue'
import UiButton from '@/components/ui/Button.vue'
import TraceRecordDocument from '@/components/trace/TraceRecordDocument.vue'
const props = defineProps<{
  comparisonId: string
  included: TraceEvidenceReference[]
  disabled: boolean
}>()
const emit = defineEmits<{ cite: [reference: TraceEvidenceReference] }>()
const { t } = useI18n()
const route = useRoute(),
  router = useRouter()
const open = computed(
  () => route.query.review_trace !== undefined || route.query.review_trace_hash !== undefined,
)
const preview = ref<ResearchTracePreview | null>(null)
const busy = ref(false),
  error = ref('')
let request = 0
const existing = computed(() =>
  props.included.find((item) => item.trace_id === preview.value?.trace.id),
)
const already = computed(() =>
  Boolean(preview.value && existing.value?.expected_source_hash === preview.value.source_hash),
)
const sourceLink = computed(() => ({
  path: '/pipeline/traces',
  query: {
    trace_id: route.query.review_trace,
    game_id: preview.value?.trace.game_id,
    experiment_id: preview.value?.source.experiment_id,
    comparison_id: props.comparisonId,
    report_id: route.query.report_id,
    trace_evidence: route.query.trace_evidence,
  },
}))
async function load() {
  const token = ++request
  preview.value = null
  error.value = ''
  busy.value = false
  if (!open.value) return
  const id = route.query.review_trace,
    hash = route.query.review_trace_hash
  if (typeof id !== 'string' || !id || typeof hash !== 'string' || !/^[a-f0-9]{64}$/.test(hash)) {
    error.value = t('traceCitation.invalid')
    return
  }
  busy.value = true
  try {
    const { data } = await researchApi.tracePreview(props.comparisonId, id)
    if (token !== request) return
    if (data.trace.id !== id || data.comparison_id !== props.comparisonId)
      throw { code: 'EVIDENCE_PREVIEW', message: t('traceCitation.invalid') }
    if (data.source_hash !== hash)
      throw { code: 'EVIDENCE_PREVIEW', message: t('traceCitation.changed') }
    preview.value = data
  } catch (cause) {
    if (token === request) error.value = getErrorMessage(cause)
  } finally {
    if (token === request) busy.value = false
  }
}
function close() {
  void router.replace({
    query: { ...route.query, review_trace: undefined, review_trace_hash: undefined },
  })
}
function cite() {
  if (
    !preview.value ||
    props.disabled ||
    busy.value ||
    already.value ||
    (!existing.value && props.included.length >= 5)
  )
    return
  emit('cite', {
    trace_id: preview.value.trace.id,
    expected_source_hash: preview.value.source_hash,
    note: existing.value?.note ?? '',
  })
  close()
}
watch(() => [props.comparisonId, route.query.review_trace, route.query.review_trace_hash], load, {
  immediate: true,
})
onBeforeUnmount(() => {
  request++
})
</script>
<template>
  <UiDialog :open="open" :title="t('traceCitation.review')" @update:open="!$event && close()">
    <div class="space-y-ink-4">
      <p>{{ t('traceCitation.previewScope') }}</p>
      <RouterLink
        v-if="typeof route.query.review_trace === 'string'"
        :to="sourceLink"
        class="text-ink-primary underline"
        >{{ t('traceCitation.current') }}</RouterLink
      >
      <p v-if="busy" role="status">{{ t('common.loading') }}</p>
      <div v-if="error">
        <p role="alert">{{ error }}</p>
        <UiButton @click="load">{{ t('common.retry') }}</UiButton>
      </div>
      <template v-if="preview">
        <TraceRecordDocument :preview="preview" />
        <p v-if="!existing && included.length >= 5">{{ t('traceCitation.limit') }}</p>
        <UiButton
          :disabled="disabled || busy || already || (!existing && included.length >= 5)"
          @click="cite"
          >{{
            t(
              already
                ? 'focus.included'
                : existing
                  ? 'traceCitation.update'
                  : 'traceCitation.include',
            )
          }}</UiButton
        >
      </template>
    </div>
  </UiDialog>
</template>
