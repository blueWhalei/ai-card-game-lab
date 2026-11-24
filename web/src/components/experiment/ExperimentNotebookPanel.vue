<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'
import {
  experimentApi,
  experimentTimelineLabel,
  type Experiment,
  type ConclusionDraftBlunder,
} from '@/api/experimentApi'
import { usePersistentDraft } from '@/composables/usePersistentDraft'
import { useLocale } from '@/composables/useLocale'
import { toast } from '@/components/ui/toast'
import { getErrorMessage, showApiError } from '@/utils/error'
import { formatDateTime } from '@/utils/format'
import DraftStatus from '@/components/common/DraftStatus.vue'
import UiButton from '@/components/ui/Button.vue'
import UiInput from '@/components/ui/Input.vue'
import UiTextarea from '@/components/ui/Textarea.vue'

const props = withDefaults(defineProps<{ experiment: Experiment; flat?: boolean }>(), {
  flat: false,
})
const emit = defineEmits<{ saved: [experiment: Experiment] }>()
const { t } = useI18n()
const { locale } = useLocale()
const { session, flush } = usePersistentDraft('experiment', props.experiment.id)
const draft = computed(() => (session.content?.kind === 'experiment' ? session.content : null))
const saving = ref(false)
const generating = ref(false)
const summaryDecisions = ref<ConclusionDraftBlunder[]>([])
const tags = computed(() =>
  (draft.value?.tags_input ?? '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
    .slice(0, 20),
)
const isDirty = computed(() => {
  const d = draft.value
  return (
    d &&
    (d.hypothesis !== (props.experiment.hypothesis ?? '') ||
      d.notes !== (props.experiment.notes ?? '') ||
      d.conclusion !== (props.experiment.conclusion ?? '') ||
      JSON.stringify(tags.value) !== JSON.stringify(props.experiment.tags ?? []))
  )
})

async function save(): Promise<void> {
  if (!draft.value) return
  saving.value = true
  try {
    if (!(await flush())) return
    const { hypothesis, notes, conclusion } = draft.value
    const result = await experimentApi.update(props.experiment.id, {
      expected_draft_revision: session.revision,
      hypothesis,
      notes,
      conclusion,
      tags: tags.value,
    })
    toast.success(t('experiment.notebookSaved'))
    emit('saved', result.data)
  } catch (error) {
    if (
      typeof error === 'object' &&
      error !== null &&
      'code' in error &&
      error.code === 'DRAFT_CONFLICT'
    ) {
      session.error = getErrorMessage(error)
    }
    showApiError(error, t('experiment.notebookSaveFailed'))
  } finally {
    saving.value = false
  }
}

async function generateSummary(): Promise<void> {
  if (
    !draft.value ||
    (draft.value.conclusion.trim() && !window.confirm(t('stage.draft.overwriteConfirm')))
  )
    return
  generating.value = true
  try {
    const { data } = await experimentApi.conclusionDraft(props.experiment.id, locale.value)
    draft.value.conclusion = data.text
    summaryDecisions.value = data.blunders
    await flush()
  } catch (error) {
    showApiError(error, t('experiment.notebookSaveFailed'))
  } finally {
    generating.value = false
  }
}
</script>

<template>
  <component :is="flat ? 'section' : 'details'" class="notebook-form space-y-4">
    <component
      :is="flat ? 'h3' : 'summary'"
      class="text-body font-medium"
      :class="{ 'cursor-pointer': !flat }"
    >
      {{ t('experiment.notebookTitle') }}
    </component>
    <p class="text-caption text-ink-text-secondary">{{ t('experiment.notebookScope') }}</p>
    <DraftStatus :session="session" />
    <p class="text-caption text-ink-text-secondary">{{ t('stage.draft.sourceHint') }}</p>
    <fieldset v-if="draft" :disabled="saving || generating || session.loading" class="space-y-4">
      <slot name="before" />
      <div class="grid gap-3 sm:grid-cols-2">
        <label
          v-for="field in ['hypothesis', 'conclusion', 'notes'] as const"
          :key="field"
          class="block text-caption"
        >
          {{ t(field === 'notes' ? 'common.notes' : `experiment.${field}`) }}
          <UiTextarea v-model="draft[field]" :rows="3" :maxlength="10000" />
        </label>
        <label class="block text-caption">
          {{ t('experiment.tags') }}
          <UiInput
            v-model="draft.tags_input"
            :maxlength="2000"
            :placeholder="t('experiment.tagsPlaceholder')"
          />
        </label>
      </div>
      <div v-if="summaryDecisions.length" class="space-y-1 text-caption">
        <p>{{ t('stage.draft.blundersHeading') }}</p>
        <RouterLink
          v-for="decision in summaryDecisions"
          :key="decision.id"
          class="block text-ink-primary"
          target="_blank"
          rel="noopener"
          :to="{
            path: '/pipeline/decisions',
            query: {
              experiment_id: experiment.id,
              decision_id: decision.id,
              game_id: decision.game_id,
            },
          }"
        >
          {{
            t('stage.draft.openBlunder', {
              round: decision.round_number,
              action: decision.action_id,
              loss: decision.ev_loss,
            })
          }}
        </RouterLink>
      </div>
      <div class="flex flex-wrap justify-end gap-2">
        <UiButton variant="ghost" :loading="generating" @click="generateSummary">{{
          t('stage.draft.generate')
        }}</UiButton>
        <UiButton :disabled="!isDirty || Boolean(session.error)" :loading="saving" @click="save">{{
          t('experiment.applyNotes')
        }}</UiButton>
      </div>
    </fieldset>
    <details v-if="experiment.timeline?.length">
      <summary class="cursor-pointer text-caption">{{ t('experiment.timelineTitle') }}</summary>
      <ul class="mt-2 space-y-1 text-caption text-ink-text-secondary">
        <li v-for="(event, index) in experiment.timeline" :key="`${event.id}-${index}`">
          {{ experimentTimelineLabel(event.id) }} · {{ formatDateTime(event.at) }}
        </li>
      </ul>
    </details>
  </component>
</template>
