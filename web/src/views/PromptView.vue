<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { toast } from '@/components/ui/toast'
import { showApiError } from '@/utils/error'
import { promptsApi, type PromptTemplateResponse } from '@/api/prompts'
import PromptComparePanel from '@/components/prompt/PromptComparePanel.vue'
import PromptList from '@/components/prompt/PromptList.vue'
import PromptEditor from '@/components/prompt/PromptEditor.vue'
import UiButton from '@/components/ui/Button.vue'
import UiDialog from '@/components/ui/Dialog.vue'
import UiBadge from '@/components/ui/Badge.vue'
import UiEmpty from '@/components/ui/Empty.vue'

const { t } = useI18n()
const templates = ref<PromptTemplateResponse[]>([])
const loading = ref(false)
const showEditorDialog = ref(false)
const isEditing = ref(false)
const selectedTemplate = ref<PromptTemplateResponse | null>(null)
const selectedTemplateKey = ref<string | undefined>(undefined)

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

onMounted(() => {
  fetchTemplates()
})
</script>

<template>
  <div class="page-container">
    <div class="mb-5 flex flex-wrap items-center justify-end gap-2">
      <UiButton @click="openCreateDialog()">{{ t('prompt.newTemplate') }}</UiButton>
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
