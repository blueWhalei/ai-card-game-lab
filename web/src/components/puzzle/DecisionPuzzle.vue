<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { puzzleApi, type DecisionPuzzleSource } from '@/api/puzzleApi'
import { getErrorMessage } from '@/utils/error'
import { formatDateTime } from '@/utils/format'
import { formatRolloutScope } from '@/utils/gameHighlights'
import UiButton from '@/components/ui/Button.vue'
import UiDialog from '@/components/ui/Dialog.vue'

const props = defineProps<{ decisionId: string }>()
const { t } = useI18n()
const router = useRouter()
const open = ref(false)
const loading = ref(false)
const saving = ref(false)
const question = ref('')
const source = ref<DecisionPuzzleSource | null>(null)
const error = ref('')
let request = 0
onBeforeUnmount(() => request++)
watch(
  () => props.decisionId,
  () => {
    request++
    open.value = false
    source.value = null
    question.value = ''
    saving.value = false
  },
)
watch(open, (value) => {
  if (!value) request++
})

function message(e: unknown) {
  const code = typeof e === 'object' && e !== null && 'code' in e ? String(e.code) : ''
  const key = {
    PUZZLE_SOURCE_INVALID: 'sourceInvalid',
    PUZZLE_SOURCE_CHANGED: 'sourceChanged',
    PUZZLE_SOURCE_MISSING: 'sourceMissing',
    EXPERIMENT_NOT_FOUND: 'sourceMissing',
  }[code]
  return key ? t(`puzzle.${key}`) : getErrorMessage(e)
}

async function inspect() {
  open.value = true
  const token = ++request
  source.value = null
  error.value = ''
  loading.value = true
  saving.value = false
  try {
    const result = await puzzleApi.decisionSource(props.decisionId)
    if (token === request) source.value = result.data
  } catch (e) {
    if (token === request) error.value = message(e)
  } finally {
    if (token === request) loading.value = false
  }
}

async function save() {
  if (!source.value || !question.value.trim() || saving.value) return
  const token = request
  saving.value = true
  error.value = ''
  try {
    const result = await puzzleApi.fromDecision({
      decision_id: source.value.decision_point_id,
      question: question.value.trim(),
      expected_source_hash: source.value.source_hash,
    })
    if (token !== request) return
    open.value = false
    await router.push({ path: '/pipeline/puzzles', query: { pack_id: result.data.pack_id } })
  } catch (e) {
    if (token === request) {
      error.value = message(e)
      source.value = null
    }
  } finally {
    if (token === request) saving.value = false
  }
}
</script>

<template>
  <UiButton variant="secondary" size="sm" class="mt-ink-3" @click="inspect">{{
    t('puzzle.fromDecision')
  }}</UiButton>
  <UiDialog v-model:open="open" :title="t('puzzle.fromDecision')">
    <div class="space-y-ink-4">
      <p class="text-body text-ink-text-secondary">{{ t('puzzle.targetScope') }}</p>
      <p v-if="loading" role="status">{{ t('common.loading') }}</p>
      <p v-if="error" role="alert" class="text-body text-ink-text">{{ error }}</p>
      <template v-if="source">
        <p class="text-body">
          {{ source.experiment_name }} · {{ t('puzzle.sourceTurn', { n: source.round_num - 1 }) }}
        </p>
        <p class="text-caption text-ink-text-secondary">
          {{ t('puzzle.sourceRead', { at: formatDateTime(source.read_at) }) }} ·
          {{
            t('puzzle.evaluatedActions', {
              n: source.candidates_evaluated,
              total: source.legal_action_count,
            })
          }}
        </p>
        <p class="text-caption text-ink-text-secondary">
          {{ formatRolloutScope(source.evaluator_params, t) }}
        </p>
      </template>
      <label class="block space-y-ink-2 text-body">
        <span>{{ t('puzzle.testQuestion') }}</span>
        <textarea
          v-model="question"
          maxlength="2000"
          rows="3"
          class="w-full rounded-ink-md border border-ink-border bg-ink-surface p-ink-3"
          :placeholder="t('puzzle.questionPlaceholder')"
        />
      </label>
      <div class="flex flex-wrap gap-ink-2">
        <UiButton
          :disabled="!source || !question.trim() || loading"
          :loading="saving"
          @click="save"
          >{{ t('puzzle.saveTarget') }}</UiButton
        >
        <UiButton v-if="!source && !loading" variant="secondary" @click="inspect">{{
          t('puzzle.recheckSource')
        }}</UiButton>
      </div>
    </div>
  </UiDialog>
</template>
