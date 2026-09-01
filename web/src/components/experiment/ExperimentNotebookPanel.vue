<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Icon } from '@iconify/vue'
import {
  experimentApi,
  experimentTimelineLabel,
  type Experiment,
  type ExperimentTimelineEvent,
} from '@/api/experimentApi'
import { toast } from '@/components/ui/toast'
import { showApiError } from '@/utils/error'
import { formatDateTime } from '@/utils/format'
import UiButton from '@/components/ui/Button.vue'
import UiInput from '@/components/ui/Input.vue'
import UiTextarea from '@/components/ui/Textarea.vue'

const props = defineProps<{
  experiment: Experiment
}>()

const emit = defineEmits<{
  saved: [experiment: Experiment]
}>()

const { t } = useI18n()

const hypothesis = ref('')
const notes = ref('')
const conclusion = ref('')
const tagsInput = ref('')
const saving = ref(false)

function syncFromExperiment(exp: Experiment): void {
  hypothesis.value = exp.hypothesis ?? ''
  notes.value = exp.notes ?? ''
  conclusion.value = exp.conclusion ?? ''
  tagsInput.value = (exp.tags ?? []).join(', ')
}

watch(
  () => props.experiment,
  (exp) => syncFromExperiment(exp),
  { immediate: true, deep: true },
)

const timeline = computed((): ExperimentTimelineEvent[] => props.experiment.timeline ?? [])

async function save(): Promise<void> {
  saving.value = true
  try {
    const tags = tagsInput.value
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
      .slice(0, 20)
    const res = await experimentApi.update(props.experiment.id, {
      hypothesis: hypothesis.value,
      notes: notes.value,
      conclusion: conclusion.value,
      tags,
    })
    toast.success(t('experiment.notebookSaved'))
    emit('saved', res.data)
  } catch (e: unknown) {
    showApiError(e, t('experiment.notebookSaveFailed'))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="rounded-ink border border-ink-border bg-ink-surface px-3 py-3 space-y-3">
    <div class="flex items-center justify-between gap-2">
      <h2 class="text-sm font-semibold text-ink-text">{{ t('experiment.notebookTitle') }}</h2>
      <UiButton size="sm" :disabled="saving" @click="save">
        {{ t('common.save') }}
      </UiButton>
    </div>

    <div class="grid gap-3 md:grid-cols-2">
      <div>
        <label class="mb-1 block text-xs font-medium text-ink-text-secondary">
          {{ t('experiment.hypothesis') }}
        </label>
        <UiTextarea
          v-model="hypothesis"
          :rows="2"
          :placeholder="t('experiment.hypothesisPlaceholder')"
        />
      </div>
      <div>
        <label class="mb-1 block text-xs font-medium text-ink-text-secondary">
          {{ t('experiment.conclusion') }}
        </label>
        <UiTextarea
          v-model="conclusion"
          :rows="2"
          :placeholder="t('experiment.conclusionPlaceholder')"
        />
      </div>
    </div>

    <div>
      <label class="mb-1 block text-xs font-medium text-ink-text-secondary">
        {{ t('common.notes') }}
      </label>
      <UiTextarea v-model="notes" :rows="2" :placeholder="t('experiment.notesPlaceholder')" />
    </div>

    <div>
      <label class="mb-1 block text-xs font-medium text-ink-text-secondary">
        {{ t('experiment.tags') }}
      </label>
      <UiInput v-model="tagsInput" :placeholder="t('experiment.tagsPlaceholder')" />
    </div>

    <div v-if="timeline.length" class="border-t border-ink-border pt-2">
      <p class="mb-1.5 text-xs font-medium text-ink-text-secondary">
        {{ t('experiment.timelineTitle') }}
      </p>
      <ul class="space-y-1 text-xs text-ink-text-secondary">
        <li v-for="(event, idx) in timeline" :key="`${event.id}-${idx}`" class="flex gap-2">
          <Icon icon="lucide:dot" class="mt-0.5 h-3 w-3 shrink-0 text-ink-primary" />
          <span>
            <span class="font-medium text-ink-text">{{ experimentTimelineLabel(event.id) }}</span>
            · {{ formatDateTime(event.at) }}
          </span>
        </li>
      </ul>
    </div>
  </div>
</template>
