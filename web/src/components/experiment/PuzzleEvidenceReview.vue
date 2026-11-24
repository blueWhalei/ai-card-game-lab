<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  researchApi,
  type PuzzleEvidenceReference,
  type ResearchPuzzlePreview,
} from '@/api/researchApi'
import { getErrorMessage } from '@/utils/error'
import UiDialog from '@/components/ui/Dialog.vue'
import UiButton from '@/components/ui/Button.vue'
import PuzzleCitationPreview from './PuzzleCitationPreview.vue'

const props = defineProps<{
  comparisonId: string
  included: PuzzleEvidenceReference[]
  disabled: boolean
}>()
const emit = defineEmits<{ cite: [reference: PuzzleEvidenceReference] }>()
const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const open = computed(() =>
  [route.query.review_pack, route.query.review_result, route.query.review_hash].some(
    (v) => v !== undefined,
  ),
)
const preview = ref<ResearchPuzzlePreview | null>(null)
const busy = ref(false)
const error = ref('')
const page = computed(() =>
  typeof route.query.review_page === 'string' &&
  /^[1-9]\d*$/.test(route.query.review_page) &&
  Number(route.query.review_page) <= 100000
    ? Number(route.query.review_page)
    : 1,
)
const sourceLink = computed(() => ({
  path: '/pipeline/puzzles',
  query: {
    pack_id: route.query.review_pack,
    result_id: route.query.review_result,
    result_page: String(page.value),
    report_id: route.query.report_id,
    puzzle_evidence: route.query.puzzle_evidence,
  },
}))
let request = 0
async function load() {
  const token = ++request
  preview.value = null
  error.value = ''
  busy.value = false
  if (!open.value) return
  const pack = route.query.review_pack,
    run = route.query.review_result,
    hash = route.query.review_hash
  if (
    typeof pack !== 'string' ||
    !pack ||
    typeof run !== 'string' ||
    !run ||
    typeof hash !== 'string' ||
    !/^[a-f0-9]{64}$/.test(hash)
  ) {
    error.value = t('puzzleHistory.invalidPosition')
    return
  }
  busy.value = true
  try {
    const { data } = await researchApi.puzzlePreview(props.comparisonId, pack, run)
    if (token !== request) return
    if (data.result.report.pack_id !== pack || data.result.report.run_id !== run)
      throw { code: 'EVIDENCE_PREVIEW', message: t('puzzleCitation.invalid') }
    if (data.result.report_hash !== hash)
      throw { code: 'EVIDENCE_PREVIEW', message: t('puzzleCitation.changedPreview') }
    preview.value = data
  } catch (cause) {
    if (token === request) error.value = getErrorMessage(cause)
  } finally {
    if (token === request) busy.value = false
  }
}
function close() {
  void router.replace({
    query: {
      ...route.query,
      review_pack: undefined,
      review_result: undefined,
      review_hash: undefined,
      review_page: undefined,
    },
  })
}
function cite(reference: PuzzleEvidenceReference) {
  if (
    !preview.value ||
    busy.value ||
    props.disabled ||
    props.included.length >= 5 ||
    props.included.some(
      (item) => item.pack_id === reference.pack_id && item.run_id === reference.run_id,
    )
  )
    return
  emit('cite', reference)
  close()
}
watch(
  () => [
    props.comparisonId,
    route.query.review_pack,
    route.query.review_result,
    route.query.review_hash,
  ],
  load,
  { immediate: true },
)
onBeforeUnmount(() => {
  request++
})
</script>

<template>
  <UiDialog :open="open" :title="t('puzzleCitation.review')" @update:open="!$event && close()">
    <div class="space-y-ink-4">
      <p>{{ t('puzzleCitation.reviewScope') }}</p>
      <RouterLink
        v-if="
          typeof route.query.review_pack === 'string' &&
          typeof route.query.review_result === 'string'
        "
        :to="sourceLink"
        class="text-ink-primary hover:underline"
        >{{ t('puzzleCitation.backToResult') }}</RouterLink
      >
      <p v-if="busy" role="status">{{ t('common.loading') }}</p>
      <div v-if="error">
        <p role="alert">{{ error }}</p>
        <UiButton @click="load">{{ t('common.retry') }}</UiButton>
      </div>
      <PuzzleCitationPreview
        v-if="preview"
        :preview="preview"
        :included="included"
        :page="page"
        :disabled="disabled || busy"
        @cite="cite"
      />
    </div>
  </UiDialog>
</template>
