<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { PuzzleEvidenceReference, ResearchPuzzlePreview } from '@/api/researchApi'
import UiButton from '@/components/ui/Button.vue'
import PuzzleResultDocument from '@/components/puzzle/PuzzleResultDocument.vue'

const props = defineProps<{
  preview: ResearchPuzzlePreview
  included: PuzzleEvidenceReference[]
  disabled?: boolean
  page?: number
}>()
const emit = defineEmits<{ cite: [reference: PuzzleEvidenceReference] }>()
const { t } = useI18n()
const alreadyIncluded = computed(() =>
  props.included.some(
    (item) =>
      item.pack_id === props.preview.result.report.pack_id &&
      item.run_id === props.preview.result.report.run_id,
  ),
)
const full = computed(() => !alreadyIncluded.value && props.included.length >= 5)
function cite() {
  if (props.disabled || alreadyIncluded.value || full.value) return
  const { report, report_hash } = props.preview.result
  emit('cite', {
    pack_id: report.pack_id,
    run_id: report.run_id,
    expected_report_hash: report_hash,
    note: '',
  })
}
</script>

<template>
  <div class="space-y-ink-3">
    <p class="text-caption">{{ t('puzzleCitation.verified') }}</p>
    <p class="text-caption text-ink-text-secondary">{{ t('puzzleCitation.reportScope') }}</p>
    <p v-if="full" role="alert">{{ t('puzzleCitation.limit') }}</p>
    <UiButton :disabled="disabled || alreadyIncluded || full" @click="cite">{{
      t(alreadyIncluded ? 'focus.included' : 'puzzleCitation.add')
    }}</UiButton>
    <details>
      <summary>{{ t('puzzleCitation.preview') }}</summary>
      <PuzzleResultDocument
        :result="preview.result"
        :page="page ?? 1"
        :local-links="false"
        embedded
      />
    </details>
  </div>
</template>
