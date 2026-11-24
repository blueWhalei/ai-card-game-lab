<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type { ResearchReport } from '@/api/researchApi'
import { promptDesignApi } from '@/api/promptDesignApi'
import UiButton from '@/components/ui/Button.vue'

const props = defineProps<{ report: ResearchReport }>()
const router = useRouter()
const { t } = useI18n()
const open = ref(false)
const baseline = ref('')
const busy = ref(false)
const failed = ref(false)
const issues = ref<string[]>([])
let request = 0
watch(
  () => props.report.record.id,
  () => {
    request++
    open.value = false
    baseline.value = ''
    busy.value = false
    failed.value = false
    issues.value = []
  },
)
watch(baseline, () => {
  issues.value = []
  failed.value = false
})
onBeforeUnmount(() => {
  request++
})
async function continueDesign() {
  if (
    busy.value ||
    !props.report.comparison.result.experiments.some((run) => run.id === baseline.value)
  )
    return
  const version = ++request
  const id = baseline.value
  const source = props.report.record.id
  busy.value = true
  failed.value = false
  issues.value = []
  try {
    const { data } = await promptDesignApi.preview(id, source)
    if (version !== request) return
    if (data.baseline.id !== id || data.source_conclusion?.id !== source)
      throw new Error('Source mismatch')
    issues.value = data.issues
    if (data.issues.length) return
    if (!data.baseline.study_id) throw new Error('Missing research')
    await router.push({
      name: 'prompt-design',
      params: { id: data.baseline.study_id },
      query: { baseline: id, source_revision: source },
    })
  } catch {
    if (version === request) failed.value = true
  } finally {
    if (version === request) busy.value = false
  }
}
</script>

<template>
  <section class="space-y-ink-3">
    <UiButton variant="secondary" :disabled="busy" :aria-expanded="open" @click="open = !open">
      {{ t('promptDesign.followup') }}
    </UiButton>
    <div v-if="open" class="max-w-3xl space-y-ink-3 border-l-2 border-ink-border pl-ink-4">
      <p class="text-body text-ink-text-secondary">{{ t('promptDesign.followupScope') }}</p>
      <label for="report-baseline" class="block text-body">{{ t('promptDesign.baseline') }}</label>
      <select id="report-baseline" v-model="baseline" :disabled="busy" class="ink-input w-full">
        <option value="">{{ t('promptDesign.choose') }}</option>
        <option v-for="run in report.comparison.result.experiments" :key="run.id" :value="run.id">
          {{ run.name }}
        </option>
      </select>
      <ul v-if="issues.length" role="status" class="list-disc space-y-ink-2 pl-ink-4 text-body">
        <li v-for="issue in issues" :key="issue">{{ t(`promptDesign.issues.${issue}`) }}</li>
      </ul>
      <p v-if="failed" role="alert" class="text-body">{{ t('promptDesign.followupFailed') }}</p>
      <UiButton :disabled="!baseline" :loading="busy" @click="continueDesign">{{
        t('promptDesign.followupContinue')
      }}</UiButton>
    </div>
  </section>
</template>
