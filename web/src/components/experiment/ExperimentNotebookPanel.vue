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

const props = withDefaults(
  defineProps<{
    experiment: Experiment
    /** Render form only (inside meta panel). */
    flat?: boolean
  }>(),
  {
    flat: false,
  },
)

const emit = defineEmits<{
  saved: [experiment: Experiment]
}>()

const { t } = useI18n()

const hypothesis = ref('')
const notes = ref('')
const conclusion = ref('')
const tagsInput = ref('')
const saving = ref(false)

function parseTags(raw: string): string[] {
  return raw
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
    .slice(0, 20)
}

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

const isDirty = computed(() => {
  const exp = props.experiment
  const tags = parseTags(tagsInput.value)
  const savedTags = exp.tags ?? []
  if (tags.length !== savedTags.length) return true
  if (tags.some((tag, i) => tag !== savedTags[i])) return true
  return (
    hypothesis.value !== (exp.hypothesis ?? '') ||
    notes.value !== (exp.notes ?? '') ||
    conclusion.value !== (exp.conclusion ?? '')
  )
})

const summaryBits = computed((): string[] => {
  const bits: string[] = []
  const h = hypothesis.value.trim()
  if (h) {
    bits.push(h.length > 36 ? `${h.slice(0, 36)}…` : h)
  } else {
    bits.push(t('experiment.notebookNoHypothesis'))
  }
  if (conclusion.value.trim()) {
    bits.push(t('experiment.notebookHasConclusion'))
  }
  const tagCount = parseTags(tagsInput.value).length
  if (tagCount > 0) {
    bits.push(t('experiment.notebookTagsCount', { n: tagCount }))
  }
  if (timeline.value.length > 0) {
    bits.push(t('experiment.notebookTimelineCount', { n: timeline.value.length }))
  }
  return bits
})

async function save(): Promise<void> {
  saving.value = true
  try {
    const res = await experimentApi.update(props.experiment.id, {
      hypothesis: hypothesis.value,
      notes: notes.value,
      conclusion: conclusion.value,
      tags: parseTags(tagsInput.value),
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
  <details
    v-if="!flat"
    class="group rounded-ink-md border border-ink-border bg-ink-surface-muted/40 open:bg-ink-surface-muted/60"
  >
    <summary
      class="flex cursor-pointer list-none items-center gap-2 px-3 py-2 text-sm marker:content-none [&::-webkit-details-marker]:hidden"
    >
      <Icon
        icon="lucide:chevron-right"
        class="h-3.5 w-3.5 shrink-0 text-ink-text-secondary transition-transform group-open:rotate-90"
      />
      <span class="shrink-0 font-medium text-ink-text">{{ t('experiment.notebookTitle') }}</span>
      <span class="min-w-0 truncate text-sm text-ink-text-secondary">
        {{ summaryBits.join(' · ') }}
      </span>
      <span v-if="isDirty" class="ml-auto shrink-0 text-xs text-ink-warning">
        {{ t('experiment.notebookUnsaved') }}
      </span>
    </summary>

    <div class="notebook-form space-y-2.5 border-t border-ink-border px-3 py-2.5">
      <slot name="before" />
      <div class="grid gap-2 lg:grid-cols-2">
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

      <div class="grid gap-2 lg:grid-cols-2">
        <div>
          <label class="mb-1 block text-xs font-medium text-ink-text-secondary">
            {{ t('common.notes') }}
          </label>
          <UiTextarea
            v-model="notes"
            :rows="2"
            :placeholder="t('experiment.notesPlaceholder')"
          />
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium text-ink-text-secondary">
            {{ t('experiment.tags') }}
          </label>
          <UiInput v-model="tagsInput" :placeholder="t('experiment.tagsPlaceholder')" />
        </div>
      </div>

      <details
        v-if="timeline.length"
        class="rounded-ink border border-ink-border/80 bg-ink-surface/60 open:bg-ink-surface"
      >
        <summary
          class="flex cursor-pointer list-none items-center gap-2 px-2.5 py-1.5 text-xs marker:content-none [&::-webkit-details-marker]:hidden"
        >
          <Icon icon="lucide:chevron-right" class="h-3 w-3 text-ink-text-secondary" />
          <span class="font-medium text-ink-text-secondary">
            {{ t('experiment.timelineTitle') }}
          </span>
          <span class="text-ink-text-muted tabular-nums">({{ timeline.length }})</span>
        </summary>
        <ul class="space-y-1 border-t border-ink-border px-2.5 py-2 text-xs text-ink-text-secondary">
          <li v-for="(event, idx) in timeline" :key="`${event.id}-${idx}`" class="flex gap-2">
            <Icon icon="lucide:dot" class="mt-0.5 h-3 w-3 shrink-0 text-ink-primary" />
            <span>
              <span class="font-medium text-ink-text">{{ experimentTimelineLabel(event.id) }}</span>
              · {{ formatDateTime(event.at) }}
            </span>
          </li>
        </ul>
      </details>

      <div class="flex justify-end pt-0.5">
        <UiButton size="sm" :disabled="saving || !isDirty" @click="save">
          {{ t('common.save') }}
        </UiButton>
      </div>
    </div>
  </details>

  <div v-else class="notebook-form space-y-4">
    <p class="text-sm font-medium text-ink-text">{{ t('experiment.notebookTitle') }}</p>
    <div class="grid gap-3 sm:grid-cols-2">
      <div>
        <label class="mb-1.5 block text-xs font-medium text-ink-text-secondary">
          {{ t('experiment.hypothesis') }}
        </label>
        <UiTextarea
          v-model="hypothesis"
          :rows="3"
          :placeholder="t('experiment.hypothesisPlaceholder')"
        />
      </div>
      <div>
        <label class="mb-1.5 block text-xs font-medium text-ink-text-secondary">
          {{ t('experiment.conclusion') }}
        </label>
        <UiTextarea
          v-model="conclusion"
          :rows="3"
          :placeholder="t('experiment.conclusionPlaceholder')"
        />
      </div>
    </div>

    <div class="grid gap-3 sm:grid-cols-2">
      <div>
        <label class="mb-1.5 block text-xs font-medium text-ink-text-secondary">
          {{ t('common.notes') }}
        </label>
        <UiTextarea
          v-model="notes"
          :rows="3"
          :placeholder="t('experiment.notesPlaceholder')"
        />
      </div>
      <div>
        <label class="mb-1.5 block text-xs font-medium text-ink-text-secondary">
          {{ t('experiment.tags') }}
        </label>
        <UiInput v-model="tagsInput" :placeholder="t('experiment.tagsPlaceholder')" />
      </div>
    </div>

    <details
      v-if="timeline.length"
      class="rounded-ink border border-ink-border/80 bg-ink-surface/60 open:bg-ink-surface"
    >
      <summary
        class="flex cursor-pointer list-none items-center gap-2 px-2.5 py-1.5 text-xs marker:content-none [&::-webkit-details-marker]:hidden"
      >
        <Icon icon="lucide:chevron-right" class="h-3 w-3 text-ink-text-secondary" />
        <span class="font-medium text-ink-text-secondary">
          {{ t('experiment.timelineTitle') }}
        </span>
        <span class="text-ink-text-muted tabular-nums">({{ timeline.length }})</span>
      </summary>
      <ul class="space-y-1 border-t border-ink-border px-2.5 py-2 text-xs text-ink-text-secondary">
        <li v-for="(event, idx) in timeline" :key="`${event.id}-${idx}`" class="flex gap-2">
          <Icon icon="lucide:dot" class="mt-0.5 h-3 w-3 shrink-0 text-ink-primary" />
          <span>
            <span class="font-medium text-ink-text">{{ experimentTimelineLabel(event.id) }}</span>
            · {{ formatDateTime(event.at) }}
          </span>
        </li>
      </ul>
    </details>

    <div class="flex justify-end pt-0.5">
      <UiButton size="sm" :disabled="saving || !isDirty" @click="save">
        {{ t('common.save') }}
      </UiButton>
    </div>
  </div>
</template>
