<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { decisionApi, type DecisionPoint } from '@/api/decision'
import type { EvidenceCandidate } from '@/api/researchApi'
import { getErrorMessage } from '@/utils/error'
import DecisionPreview from '@/components/experiment/DecisionPreview.vue'
import UiButton from '@/components/ui/Button.vue'

const props = defineProps<{ candidate: EvidenceCandidate }>()
const { t } = useI18n()
const point = ref<DecisionPoint | null>(null)
const loading = ref(false)
const error = ref('')
let request = 0
async function load() {
  const version = ++request
  const expected = props.candidate
  point.value = null
  error.value = ''
  loading.value = true
  try {
    const { data } = await decisionApi.get(expected.id)
    if (version !== request) return
    if (
      data.id !== expected.id ||
      data.game_id !== expected.game_id ||
      data.player_id !== expected.player_id ||
      data.round_number !== expected.round_number
    )
      throw new Error(t('researchReport.status.identity_mismatch'))
    point.value = data
  } catch (cause) {
    if (version === request) error.value = getErrorMessage(cause)
  } finally {
    if (version === request) loading.value = false
  }
}
watch(() => props.candidate.id, load, { immediate: true })
onBeforeUnmount(() => {
  request++
})
</script>

<template>
  <div class="space-y-ink-4" aria-live="polite" :aria-busy="loading">
    <p v-if="loading" class="text-caption text-ink-text-muted">{{ t('common.loading') }}</p>
    <div v-else-if="error" class="space-y-ink-2">
      <p role="alert" class="text-body text-ink-danger">{{ error }}</p>
      <UiButton variant="secondary" @click="load">{{ t('common.retry') }}</UiButton>
    </div>
    <DecisionPreview v-else-if="point" :point="point" :action-id="candidate.action_id" />
  </div>
</template>
