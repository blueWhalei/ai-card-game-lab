<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { researchApi, type DecisionEvidencePreview } from '@/api/researchApi'
import { getErrorMessage } from '@/utils/error'
import UiDialog from '@/components/ui/Dialog.vue'
import UiButton from '@/components/ui/Button.vue'
import DecisionPreview from './DecisionPreview.vue'
import EvidenceCiteButton from './EvidenceCiteButton.vue'

const props = defineProps<{ comparisonId: string; included: string[]; disabled: boolean }>()
const emit = defineEmits<{ cite: [ids: string[]] }>()
const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const open = computed(
  () => typeof route.query.review_decision === 'string' && Boolean(route.query.review_decision),
)
const preview = ref<DecisionEvidencePreview | null>(null)
const busy = ref(false)
const error = ref('')
const full = computed(
  () =>
    preview.value &&
    props.included.length >= 30 &&
    !props.included.includes(preview.value.decision.id),
)
let request = 0
async function load() {
  const version = ++request
  preview.value = null
  error.value = ''
  busy.value = false
  const id = route.query.review_decision
  if (typeof id !== 'string' || !id) return
  busy.value = true
  try {
    const { data } = await researchApi.decision(props.comparisonId, id)
    if (version !== request) return
    if (data.comparison_id !== props.comparisonId || data.decision.id !== id)
      throw new Error(t('researchReport.status.identity_mismatch'))
    preview.value = data
  } catch (cause) {
    if (version === request) error.value = getErrorMessage(cause)
  } finally {
    if (version === request) busy.value = false
  }
}
function close() {
  void router.replace({ query: { ...route.query, review_decision: undefined } })
}
function cite(ids: string[]) {
  if (props.disabled || full.value || busy.value || !preview.value) return
  emit('cite', ids)
  close()
}
watch([() => props.comparisonId, () => route.query.review_decision], load, { immediate: true })
onBeforeUnmount(() => {
  request++
})
</script>
<template>
  <UiDialog :open="open" :title="t('evidenceEntry.review')" @update:open="!$event && close()">
    <div class="space-y-ink-4">
      <p>{{ t('evidenceEntry.previewScope') }}</p>
      <p v-if="busy" role="status">{{ t('common.loading') }}</p>
      <div v-if="error">
        <p role="alert">{{ error }}</p>
        <UiButton @click="load">{{ t('common.retry') }}</UiButton>
      </div>
      <template v-if="preview">
        <p>
          {{
            t('focus.decision', {
              player: preview.decision.player_id,
              round: preview.decision.round_number,
            })
          }}
        </p>
        <DecisionPreview :point="preview.decision" :action-id="preview.decision.action_id" />
        <p v-if="full" role="alert">{{ t('paired.citationLimit') }}</p>
        <EvidenceCiteButton
          :ids="[preview.decision.id]"
          :included="included"
          :disabled="disabled || busy || Boolean(full)"
          @cite="cite"
        />
      </template>
    </div>
  </UiDialog>
</template>
