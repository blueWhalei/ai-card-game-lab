<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  researchApi,
  type PuzzleEvidenceReference,
  type ResearchPuzzlePreview,
} from '@/api/researchApi'
import { puzzleApi, type PuzzlePackSummary, type PuzzleResultList } from '@/api/puzzleApi'
import { formatDateTime } from '@/utils/format'
import { getErrorMessage } from '@/utils/error'
import PuzzleCitationPreview from './PuzzleCitationPreview.vue'
import UiButton from '@/components/ui/Button.vue'
import UiSelect from '@/components/ui/Select.vue'
import UiTextarea from '@/components/ui/Textarea.vue'
import UiPagination from '@/components/ui/Pagination.vue'

const props = defineProps<{
  comparisonId: string
  modelValue: PuzzleEvidenceReference[]
  disabled?: boolean
}>()
const emit = defineEmits<{ 'update:modelValue': [value: PuzzleEvidenceReference[]] }>()
const { t } = useI18n()
const opened = ref(false)
const packs = ref<PuzzlePackSummary[]>([])
const pack = ref('')
const page = ref(1)
const list = ref<PuzzleResultList | null>(null)
const preview = ref<ResearchPuzzlePreview | null>(null)
const loading = ref(false)
const inspecting = ref(false)
const error = ref('')
let request = 0
let inspection = 0
onBeforeUnmount(() => {
  request++
  inspection++
})
const options = computed(() =>
  packs.value.map((item) => ({
    value: item.pack_id,
    label: `${item.pack_id} · ${formatDateTime(item.created_at)}`,
  })),
)
const included = computed(() =>
  props.modelValue.some(
    (item) =>
      item.pack_id === preview.value?.result.report.pack_id &&
      item.run_id === preview.value?.result.report.run_id,
  ),
)

async function open() {
  opened.value = true
  const token = ++request
  loading.value = true
  error.value = ''
  try {
    const response = await researchApi.puzzlePacks(props.comparisonId)
    if (token === request) packs.value = response.data
  } catch (e) {
    if (token === request) error.value = getErrorMessage(e)
  } finally {
    if (token === request) loading.value = false
  }
}
async function load() {
  const token = ++request
  inspection++
  inspecting.value = false
  list.value = null
  preview.value = null
  error.value = ''
  loading.value = false
  if (!pack.value) return
  loading.value = true
  try {
    const response = await puzzleApi.results(pack.value, page.value)
    if (token === request) list.value = response.data
  } catch (e) {
    if (token === request) error.value = getErrorMessage(e)
  } finally {
    if (token === request) loading.value = false
  }
}
async function inspect(run: string) {
  const token = ++inspection
  preview.value = null
  error.value = ''
  inspecting.value = true
  try {
    const response = await researchApi.puzzlePreview(props.comparisonId, pack.value, run)
    if (token !== inspection) return
    if (
      response.data.result.report.pack_id !== pack.value ||
      response.data.result.report.run_id !== run
    )
      throw new Error(t('puzzleCitation.invalid'))
    preview.value = response.data
  } catch (e) {
    if (token === inspection) error.value = getErrorMessage(e)
  } finally {
    if (token === inspection) inspecting.value = false
  }
}
function add(reference: PuzzleEvidenceReference) {
  if (!preview.value || props.disabled || included.value || props.modelValue.length >= 5) return
  emit('update:modelValue', [...props.modelValue, reference])
}
function note(index: number, value: string) {
  emit(
    'update:modelValue',
    props.modelValue.map((item, i) => (i === index ? { ...item, note: value } : item)),
  )
}
watch(pack, () => {
  page.value = 1
  void load()
})
watch(page, load)
watch(
  () => props.comparisonId,
  () => {
    request++
    inspection++
    opened.value = false
    packs.value = []
    list.value = null
    preview.value = null
    pack.value = ''
    loading.value = false
    inspecting.value = false
    error.value = ''
  },
)
</script>

<template>
  <section
    class="space-y-ink-3 border-t border-ink-border pt-ink-3"
    :aria-label="t('puzzleCitation.title')"
  >
    <h3 class="font-semibold">{{ t('puzzleCitation.title') }} · {{ modelValue.length }}/5</h3>
    <p class="text-caption text-ink-text-secondary">{{ t('puzzleCitation.scope') }}</p>
    <div
      v-for="(item, index) in modelValue"
      :key="`${item.pack_id}/${item.run_id}`"
      class="space-y-ink-2 text-caption"
    >
      <p class="break-all">{{ item.pack_id }} · {{ item.run_id }}</p>
      <UiTextarea
        :model-value="item.note"
        :aria-label="`${item.run_id}: ${t('researchReport.note')}`"
        :placeholder="t('researchReport.note')"
        :maxlength="1000"
        :rows="2"
        :disabled="disabled"
        @update:model-value="note(index, $event)"
      />
      <UiButton
        variant="ghost"
        :disabled="disabled"
        @click="
          emit(
            'update:modelValue',
            modelValue.filter((_, i) => i !== index),
          )
        "
        >{{ t('researchReport.remove') }}</UiButton
      >
    </div>
    <UiButton variant="secondary" :disabled="disabled" :loading="loading" @click="open">{{
      t('puzzleCitation.choose')
    }}</UiButton>
    <div v-if="opened" class="space-y-ink-3">
      <p v-if="error" role="alert" class="text-ink-error">{{ error }}</p>
      <p v-if="!loading && !packs.length">{{ t('puzzleCitation.noPacks') }}</p>
      <UiSelect
        v-if="packs.length"
        v-model="pack"
        class="w-full"
        :options="options"
        :placeholder="t('puzzleCitation.pack')"
        :aria-label="t('puzzleCitation.pack')"
        :disabled="disabled || loading"
      />
      <UiButton v-if="pack" variant="ghost" :disabled="disabled || loading" @click="load">{{
        t('puzzleCitation.refresh')
      }}</UiButton>
      <ul v-if="list" class="divide-y divide-ink-border">
        <li v-for="item in list.items" :key="item.run_id">
          <button
            type="button"
            class="w-full py-ink-2 text-left text-caption"
            :disabled="disabled || inspecting || item.status !== 'available'"
            @click="inspect(item.run_id)"
          >
            {{ t(`puzzleHistory.${item.kind}`) }} ·
            {{ item.created_at ? formatDateTime(item.created_at) : '—' }} · {{ item.run_id }} ·
            {{ t(`puzzleHistory.status.${item.status}`) }}
          </button>
        </li>
      </ul>
      <p v-if="list && !list.items.length">{{ t('puzzleHistory.empty') }}</p>
      <UiPagination
        v-if="list"
        v-model:page="page"
        :page-size="20"
        :total="list.total"
        fixed-page-size
      />
      <p v-if="inspecting" role="status">{{ t('common.loading') }}</p>
      <PuzzleCitationPreview
        v-if="preview"
        :preview="preview"
        :included="modelValue"
        :page="page"
        :disabled="disabled"
        @cite="add"
      />
    </div>
  </section>
</template>
