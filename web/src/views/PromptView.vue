<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { toast } from '@/components/ui/toast'
import { showApiError } from '@/utils/error'
import {
  promptsApi,
  type PromptTemplateResponse,
  type ABTestConfig,
  type ABStatsResponse,
} from '@/api/prompts'
import PromptList from '@/components/prompt/PromptList.vue'
import PromptEditor from '@/components/prompt/PromptEditor.vue'
import UiButton from '@/components/ui/Button.vue'
import UiDialog from '@/components/ui/Dialog.vue'
import UiSwitch from '@/components/ui/Switch.vue'
import UiSlider from '@/components/ui/Slider.vue'
import UiBadge from '@/components/ui/Badge.vue'
import UiEmpty from '@/components/ui/Empty.vue'

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

const dialogTitle = computed(() => (isEditing.value ? '编辑模板' : '新建模板'))

async function fetchTemplates() {
  loading.value = true
  try {
    const res = await promptsApi.list()
    templates.value = res.data
  } catch (e: unknown) {
    showApiError(e, '获取模板列表失败')
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
    showApiError(e, '获取 A/B 测试统计失败')
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
      toast.success('模板已更新')
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
      toast.success('模板已创建')
    }
    showEditorDialog.value = false
    await fetchTemplates()
  } catch (e: unknown) {
    showApiError(e, isEditing.value ? '更新失败' : '创建失败')
  } finally {
    editorLoading.value = false
  }
}

async function handleActivate(templateKey: string, version: string) {
  try {
    await promptsApi.activate(templateKey, { version })
    toast.success('模板已激活')
    await fetchTemplates()
  } catch (e: unknown) {
    showApiError(e, '激活失败')
  }
}

async function handleDeactivate(templateKey: string, version: string) {
  try {
    await promptsApi.deactivate(templateKey, { version })
    toast.success('模板已停用')
    await fetchTemplates()
  } catch (e: unknown) {
    showApiError(e, '停用失败')
  }
}

async function handleDelete(templateKey: string, version: string) {
  try {
    await promptsApi.delete(templateKey, version)
    toast.success('模板已删除')
    if (
      selectedTemplate.value?.template_key === templateKey &&
      selectedTemplate.value?.version === version
    ) {
      selectedTemplate.value = null
    }
    await fetchTemplates()
  } catch (e: unknown) {
    showApiError(e, '删除失败')
  }
}

function handleSelect(templateKey: string, version: string) {
  selectedTemplateKey.value = templateKey
  const template = templates.value.find(
    (t) => t.template_key === templateKey && t.version === version,
  )
  if (template) {
    selectedTemplate.value = template
  }
}

async function handleABConfigUpdate() {
  try {
    await promptsApi.updateAbConfig(abConfig.value)
    toast.success('A/B 测试配置已更新')
    await fetchABStats()
  } catch (e: unknown) {
    showApiError(e, '更新配置失败')
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
    <div class="mb-8 flex items-center justify-between gap-4">
      <p class="page-subtitle mt-0">管理 AI 决策的提示词模板，支持版本控制和 A/B 测试</p>
      <div class="flex shrink-0 gap-3">
        <UiButton variant="secondary" @click="showABPanel = !showABPanel">
          {{ showABPanel ? '隐藏' : 'A/B 测试' }}
        </UiButton>
        <UiButton @click="openCreateDialog()">新建模板</UiButton>
      </div>
    </div>

    <div v-if="showABPanel" class="mb-6 rounded-ink-md border border-ink-border bg-ink-surface p-5">
      <div class="mb-4 flex items-center justify-between border-b border-ink-border pb-3">
        <h3 class="text-base font-semibold text-ink-text">A/B 测试配置</h3>
      </div>
      <div class="grid grid-cols-1 gap-6 md:grid-cols-2">
        <div>
          <div class="mb-4">
            <label class="mb-2 block text-sm font-medium text-ink-text">启用 A/B 测试</label>
            <div class="flex items-center gap-2">
              <UiSwitch v-model="abConfig.enabled" />
              <span class="text-sm text-ink-text-muted">{{ abConfig.enabled ? '启用' : '禁用' }}</span>
            </div>
          </div>
          <div v-if="abConfig.enabled" class="mb-4">
            <label class="mb-2 block text-sm font-medium text-ink-text">
              v2 版本分配比例: {{ (abConfig.ratio * 100).toFixed(0) }}%
            </label>
            <UiSlider v-model="abConfig.ratio" :min="0" :max="1" :step="0.1" />
          </div>
          <UiButton @click="handleABConfigUpdate">保存配置</UiButton>
        </div>
        <div v-if="abStats" class="rounded-ink-md bg-ink-surface-muted p-4">
          <h4 class="mb-3 text-sm font-semibold text-ink-text-secondary">分配统计</h4>
          <div class="grid grid-cols-3 gap-4 text-center">
            <div>
              <div class="text-2xl font-semibold text-ink-text">{{ abStats.total_assignments }}</div>
              <div class="text-xs text-ink-text-muted">总分配次数</div>
            </div>
            <div>
              <div class="text-2xl font-semibold text-ink-primary">{{ abStats.v1_count }}</div>
              <div class="text-xs text-ink-text-muted">v1 版本</div>
            </div>
            <div>
              <div class="text-2xl font-semibold text-ink-success">{{ abStats.v2_count }}</div>
              <div class="text-xs text-ink-text-muted">v2 版本</div>
            </div>
          </div>
        </div>
      </div>
    </div>

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
            <h3 class="text-base font-semibold text-ink-text">模板详情</h3>
            <UiButton size="sm" variant="secondary" @click="openEditDialog(selectedTemplate)">
              编辑
            </UiButton>
          </div>
          <div class="space-y-3">
            <div>
              <span class="text-xs text-ink-text-muted">模板类型</span>
              <div class="font-medium text-ink-text">{{ selectedTemplate.template_key }}</div>
            </div>
            <div>
              <span class="text-xs text-ink-text-muted">版本</span>
              <div class="font-medium text-ink-text">v{{ selectedTemplate.version }}</div>
            </div>
            <div>
              <span class="text-xs text-ink-text-muted">状态</span>
              <div class="mt-1">
                <UiBadge :variant="selectedTemplate.is_active ? 'success' : 'muted'">
                  {{ selectedTemplate.is_active ? '已激活' : '未激活' }}
                </UiBadge>
              </div>
            </div>
            <div>
              <span class="text-xs text-ink-text-muted">内容</span>
              <div class="mt-1 max-h-64 overflow-y-auto rounded-ink bg-ink-surface-muted p-3">
                <pre class="whitespace-pre-wrap font-mono text-xs text-ink-text-secondary">{{
                  selectedTemplate.content
                }}</pre>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="sticky top-20 rounded-ink-md border border-ink-border bg-ink-surface p-5">
          <UiEmpty title="选择一个模板查看详情" description='或点击"新建模板"创建' />
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
