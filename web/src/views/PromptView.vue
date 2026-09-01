<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { toast } from '@/components/ui/toast'
import { showApiError } from '@/utils/error'
import {
  promptsApi,
  type PromptTemplateResponse,
  type ABTestConfig,
  type ABStatsResponse,
} from '@/api/prompts'
import PromptComparePanel from '@/components/prompt/PromptComparePanel.vue'
import PromptList from '@/components/prompt/PromptList.vue'
import PromptEditor from '@/components/prompt/PromptEditor.vue'
import KpiStrip from '@/components/common/KpiStrip.vue'
import type { KpiItem } from '@/components/common/KpiStrip.vue'
import UiButton from '@/components/ui/Button.vue'
import UiDialog from '@/components/ui/Dialog.vue'
import UiSwitch from '@/components/ui/Switch.vue'
import UiSlider from '@/components/ui/Slider.vue'
import UiBadge from '@/components/ui/Badge.vue'
import UiEmpty from '@/components/ui/Empty.vue'

const { t } = useI18n()
const templates = ref<PromptTemplateResponse[]>([])
const loading = ref(false)
const showEditorDialog = ref(false)
const isEditing = ref(false)
const selectedTemplate = ref<PromptTemplateResponse | null>(null)
const selectedTemplateKey = ref<string | undefined>(undefined)

const abStats = ref<ABStatsResponse | null>(null)
const abConfig = ref<ABTestConfig>({ enabled: false, ratio: 0.5 })
const showABPanel = ref(false)

const editorForm = ref({
  template_key: '',
  version: '',
  content: '',
  is_active: false,
})

const editorLoading = ref(false)

const dialogTitle = computed(() => (isEditing.value ? t('prompt.editTemplate') : t('prompt.newTemplate')))

const promptVersions = computed(() =>
  [...new Set(templates.value.map((item) => item.version).filter(Boolean))],
)

const abKpiItems = computed((): KpiItem[] => {
  if (!abStats.value) return []
  return [
    {
      id: 'total',
      label: t('prompt.totalAlloc'),
      value: String(abStats.value.total_assignments),
    },
    {
      id: 'v1',
      label: t('prompt.v1'),
      value: String(abStats.value.v1_count),
      tone: 'primary',
    },
    {
      id: 'v2',
      label: t('prompt.v2'),
      value: String(abStats.value.v2_count),
      tone: 'default',
    },
  ]
})

async function fetchTemplates() {
  loading.value = true
  try {
    const res = await promptsApi.list()
    templates.value = res.data
  } catch (e: unknown) {
    showApiError(e, t('prompt.listFailed'))
  } finally {
    loading.value = false
  }
}

async function fetchABStats() {
  try {
    const res = await promptsApi.getAbStats()
    abStats.value = res.data
    abConfig.value = {
      enabled: res.data.enabled,
      ratio: res.data.ratio,
    }
  } catch (e: unknown) {
    showApiError(e, t('prompt.abStatsFailed'))
  }
}

function openCreateDialog(templateKey?: string) {
  isEditing.value = false
  selectedTemplate.value = null
  editorForm.value = {
    template_key: templateKey || '',
    version: '1.0.0',
    content: '',
    is_active: true,
  }
  showEditorDialog.value = true
}

function openEditDialog(template: PromptTemplateResponse) {
  isEditing.value = true
  selectedTemplate.value = template
  editorForm.value = {
    template_key: template.template_key,
    version: template.version,
    content: template.content,
    is_active: template.is_active,
  }
  showEditorDialog.value = true
}

async function handleEditorSubmit() {
  editorLoading.value = true
  try {
    if (isEditing.value) {
      await promptsApi.update(editorForm.value.template_key, editorForm.value.version, {
        content: editorForm.value.content,
      })
      if (editorForm.value.is_active && !selectedTemplate.value?.is_active) {
        await promptsApi.activate(editorForm.value.template_key, {
          version: editorForm.value.version,
        })
      }
      toast.success(t('prompt.updated'))
    } else {
      await promptsApi.create({
        template_key: editorForm.value.template_key,
        version: editorForm.value.version,
        content: editorForm.value.content,
      })
      if (editorForm.value.is_active) {
        await promptsApi.activate(editorForm.value.template_key, {
          version: editorForm.value.version,
        })
      }
      toast.success(t('prompt.created'))
    }
    showEditorDialog.value = false
    await fetchTemplates()
  } catch (e: unknown) {
    showApiError(e, isEditing.value ? t('prompt.updateFailed') : t('prompt.createFailed'))
  } finally {
    editorLoading.value = false
  }
}

async function handleActivate(templateKey: string, version: string) {
  try {
    await promptsApi.activate(templateKey, { version })
    toast.success(t('prompt.activated'))
    await fetchTemplates()
  } catch (e: unknown) {
    showApiError(e, t('prompt.activateFailed'))
  }
}

async function handleDeactivate(templateKey: string, version: string) {
  try {
    await promptsApi.deactivate(templateKey, { version })
    toast.success(t('prompt.deactivated'))
    await fetchTemplates()
  } catch (e: unknown) {
    showApiError(e, t('prompt.deactivateFailed'))
  }
}

async function handleDelete(templateKey: string, version: string) {
  try {
    await promptsApi.delete(templateKey, version)
    toast.success(t('prompt.deleted'))
    if (
      selectedTemplate.value?.template_key === templateKey &&
      selectedTemplate.value?.version === version
    ) {
      selectedTemplate.value = null
    }
    await fetchTemplates()
  } catch (e: unknown) {
    showApiError(e, t('error.deleteFailed'))
  }
}

function handleSelect(templateKey: string, version: string) {
  selectedTemplateKey.value = templateKey
  const template = templates.value.find(
    (item) => item.template_key === templateKey && item.version === version,
  )
  if (template) {
    selectedTemplate.value = template
  }
}

async function handleABConfigUpdate() {
  try {
    await promptsApi.updateAbConfig(abConfig.value)
    toast.success(t('prompt.abUpdated'))
    await fetchABStats()
  } catch (e: unknown) {
    showApiError(e, t('prompt.abUpdateFailed'))
  }
}

watch(showABPanel, (val) => {
  if (val && !abStats.value) {
    fetchABStats()
  }
})

onMounted(() => {
  fetchTemplates()
})
</script>

<template>
  <div class="page-container">
    <div class="mb-5 flex flex-wrap items-center justify-end gap-2">
      <UiButton variant="secondary" @click="showABPanel = !showABPanel">
        {{ showABPanel ? t('common.hide') : t('prompt.abTest') }}
      </UiButton>
      <UiButton @click="openCreateDialog()">{{ t('prompt.newTemplate') }}</UiButton>
    </div>

    <div v-if="showABPanel" class="mb-5 rounded-ink-md border border-ink-border bg-ink-surface px-3 py-3">
      <div class="mb-3 flex items-center justify-between">
        <h3 class="text-sm font-semibold text-ink-text">{{ t('prompt.abConfig') }}</h3>
      </div>
      <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div class="space-y-3">
          <div>
            <label class="mb-1.5 block text-sm font-medium text-ink-text">{{ t('prompt.enableAb') }}</label>
            <div class="flex items-center gap-2">
              <UiSwitch v-model="abConfig.enabled" />
              <span class="text-sm text-ink-text-muted">{{
                abConfig.enabled ? t('common.enabled') : t('common.disabled')
              }}</span>
            </div>
          </div>
          <div v-if="abConfig.enabled">
            <label class="mb-1.5 block text-sm font-medium text-ink-text">
              {{ t('prompt.v2Ratio', { n: (abConfig.ratio * 100).toFixed(0) }) }}
            </label>
            <UiSlider v-model="abConfig.ratio" :min="0" :max="1" :step="0.1" />
          </div>
          <UiButton size="sm" @click="handleABConfigUpdate">{{ t('prompt.saveConfig') }}</UiButton>
        </div>
        <div v-if="abStats" class="space-y-2">
          <h4 class="text-xs font-medium text-ink-text-muted">{{ t('prompt.allocStats') }}</h4>
          <KpiStrip :items="abKpiItems" class="md:!grid-cols-3" />
        </div>
      </div>
    </div>

    <PromptComparePanel class="mb-6" :versions="promptVersions" />

    <div class="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <div class="lg:col-span-2">
        <PromptList
          :templates="templates"
          :loading="loading"
          :selected-template-key="selectedTemplateKey"
          @activate="handleActivate"
          @deactivate="handleDeactivate"
          @delete="handleDelete"
          @select="handleSelect"
          @create="openCreateDialog"
        />
      </div>

      <div class="lg:col-span-1">
        <div
          v-if="selectedTemplate"
          class="sticky top-20 rounded-ink-md border border-ink-border bg-ink-surface p-5"
        >
          <div class="mb-4 flex items-center justify-between border-b border-ink-border pb-3">
            <h3 class="text-base font-semibold text-ink-text">{{ t('prompt.detail') }}</h3>
            <UiButton size="sm" variant="secondary" @click="openEditDialog(selectedTemplate)">
              {{ t('common.edit') }}
            </UiButton>
          </div>
          <div class="space-y-3">
            <div>
              <span class="text-xs text-ink-text-muted">{{ t('prompt.type') }}</span>
              <div class="font-medium text-ink-text">{{ selectedTemplate.template_key }}</div>
            </div>
            <div>
              <span class="text-xs text-ink-text-muted">{{ t('prompt.version') }}</span>
              <div class="font-medium text-ink-text">v{{ selectedTemplate.version }}</div>
            </div>
            <div>
              <span class="text-xs text-ink-text-muted">{{ t('common.status') }}</span>
              <div class="mt-1">
                <UiBadge :variant="selectedTemplate.is_active ? 'success' : 'muted'">
                  {{ selectedTemplate.is_active ? t('prompt.active') : t('prompt.inactive') }}
                </UiBadge>
              </div>
            </div>
            <div>
              <span class="text-xs text-ink-text-muted">{{ t('prompt.content') }}</span>
              <div class="mt-1 max-h-64 overflow-y-auto rounded-ink bg-ink-surface-muted p-3">
                <pre class="whitespace-pre-wrap font-mono text-xs text-ink-text-secondary">{{
                  selectedTemplate.content
                }}</pre>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="sticky top-20 rounded-ink-md border border-ink-border bg-ink-surface p-5">
          <UiEmpty :title="t('prompt.pickDetail')" :description="t('prompt.pickDetailHint')" />
        </div>
      </div>
    </div>

    <UiDialog
      :open="showEditorDialog"
      :title="dialogTitle"
      class="w-[min(92vw,700px)]"
      @update:open="showEditorDialog = $event"
    >
      <PromptEditor
        v-model="editorForm"
        :is-editing="isEditing"
        :loading="editorLoading"
        @submit="handleEditorSubmit"
        @cancel="showEditorDialog = false"
      />
    </UiDialog>
  </div>
</template>
