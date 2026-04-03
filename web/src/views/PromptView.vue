<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { showApiError } from '@/utils/error'
import { promptsApi, type PromptTemplateResponse, type ABTestConfig, type ABStatsResponse } from '@/api/prompts'
import PromptList from '@/components/prompt/PromptList.vue'
import PromptEditor from '@/components/prompt/PromptEditor.vue'

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

const dialogTitle = computed(() => isEditing.value ? '编辑模板' : '新建模板')

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
        await promptsApi.activate(editorForm.value.template_key, { version: editorForm.value.version })
      }
      ElMessage.success('模板已更新')
    } else {
      await promptsApi.create({
        template_key: editorForm.value.template_key,
        version: editorForm.value.version,
        content: editorForm.value.content,
      })
      if (editorForm.value.is_active) {
        await promptsApi.activate(editorForm.value.template_key, { version: editorForm.value.version })
      }
      ElMessage.success('模板已创建')
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
    ElMessage.success('模板已激活')
    await fetchTemplates()
  } catch (e: unknown) {
    showApiError(e, '激活失败')
  }
}

async function handleDeactivate(templateKey: string, version: string) {
  try {
    await promptsApi.deactivate(templateKey, { version })
    ElMessage.success('模板已停用')
    await fetchTemplates()
  } catch (e: unknown) {
    showApiError(e, '停用失败')
  }
}

async function handleDelete(templateKey: string, version: string) {
  try {
    await promptsApi.delete(templateKey, version)
    ElMessage.success('模板已删除')
    if (selectedTemplate.value?.template_key === templateKey && selectedTemplate.value?.version === version) {
      selectedTemplate.value = null
    }
    await fetchTemplates()
  } catch (e: unknown) {
    showApiError(e, '删除失败')
  }
}

function handleSelect(templateKey: string, version: string) {
  selectedTemplateKey.value = templateKey
  const template = templates.value.find(t => t.template_key === templateKey && t.version === version)
  if (template) {
    selectedTemplate.value = template
  }
}

async function handleABConfigUpdate() {
  try {
    await promptsApi.updateAbConfig(abConfig.value)
    ElMessage.success('A/B 测试配置已更新')
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
    <div class="mb-8 flex items-center justify-between">
      <div>
        <h2 class="page-title">提示词管理</h2>
        <p class="page-subtitle">管理 AI 决策的提示词模板，支持版本控制和 A/B 测试</p>
      </div>
      <div class="flex gap-3">
        <button
          class="rounded-full border border-[#d2d2d7] px-4 py-2 text-sm font-medium text-[#424245] transition-all hover:border-[#86868b]"
          @click="showABPanel = !showABPanel"
        >
          {{ showABPanel ? '隐藏' : 'A/B 测试' }}
        </button>
        <button class="apple-btn" @click="openCreateDialog()">新建模板</button>
      </div>
    </div>

    <div v-if="showABPanel" class="apple-card mb-6">
      <div class="mb-4 flex items-center justify-between border-b border-[#f5f5f7] pb-3">
        <h3 class="text-base font-semibold text-[#1d1d1f]">A/B 测试配置</h3>
      </div>
      <div class="grid grid-cols-1 gap-6 md:grid-cols-2">
        <div>
          <div class="mb-4">
            <label class="mb-2 block text-sm font-medium text-[#424245]">启用 A/B 测试</label>
            <el-switch
              v-model="abConfig.enabled"
              active-text="启用"
              inactive-text="禁用"
            />
          </div>
          <div v-if="abConfig.enabled" class="mb-4">
            <label class="mb-2 block text-sm font-medium text-[#424245]">
              v2 版本分配比例: {{ (abConfig.ratio * 100).toFixed(0) }}%
            </label>
            <el-slider v-model="abConfig.ratio" :min="0" :max="1" :step="0.1" />
          </div>
          <button
            class="rounded-full bg-[#0071e3] px-4 py-2 text-sm font-medium text-white transition-all hover:bg-[#0077ed]"
            @click="handleABConfigUpdate"
          >
            保存配置
          </button>
        </div>
        <div v-if="abStats" class="rounded-xl bg-[#f5f5f7] p-4">
          <h4 class="mb-3 text-sm font-semibold text-[#424245]">分配统计</h4>
          <div class="grid grid-cols-3 gap-4 text-center">
            <div>
              <div class="text-2xl font-semibold text-[#1d1d1f]">{{ abStats.total_assignments }}</div>
              <div class="text-xs text-[#86868b]">总分配次数</div>
            </div>
            <div>
              <div class="text-2xl font-semibold text-[#0071e3]">{{ abStats.v1_count }}</div>
              <div class="text-xs text-[#86868b]">v1 版本</div>
            </div>
            <div>
              <div class="text-2xl font-semibold text-[#4a9c2d]">{{ abStats.v2_count }}</div>
              <div class="text-xs text-[#86868b]">v2 版本</div>
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
        <div v-if="selectedTemplate" class="apple-card sticky top-20">
          <div class="mb-4 flex items-center justify-between border-b border-[#f5f5f7] pb-3">
            <h3 class="text-base font-semibold text-[#1d1d1f]">模板详情</h3>
            <button
              class="rounded-full bg-[#e6f2ff] px-3 py-1 text-xs font-medium text-[#0071e3] transition-all hover:bg-[#cce4ff]"
              @click="openEditDialog(selectedTemplate)"
            >
              编辑
            </button>
          </div>
          <div class="space-y-3">
            <div>
              <span class="text-xs text-[#86868b]">模板类型</span>
              <div class="font-medium text-[#1d1d1f]">{{ selectedTemplate.template_key }}</div>
            </div>
            <div>
              <span class="text-xs text-[#86868b]">版本</span>
              <div class="font-medium text-[#1d1d1f]">v{{ selectedTemplate.version }}</div>
            </div>
            <div>
              <span class="text-xs text-[#86868b]">状态</span>
              <div>
                <span
                  v-if="selectedTemplate.is_active"
                  class="rounded-full bg-[#e1f3d8] px-2 py-0.5 text-xs font-medium text-[#4a9c2d]"
                >
                  已激活
                </span>
                <span
                  v-else
                  class="rounded-full bg-[#f5f5f7] px-2 py-0.5 text-xs text-[#86868b]"
                >
                  未激活
                </span>
              </div>
            </div>
            <div>
              <span class="text-xs text-[#86868b]">内容</span>
              <div class="mt-1 max-h-64 overflow-y-auto rounded-lg bg-[#f5f5f7] p-3">
                <pre class="whitespace-pre-wrap font-mono text-xs text-[#424245]">{{ selectedTemplate.content }}</pre>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="apple-card sticky top-20">
          <div class="py-8 text-center text-[#86868b]">
            <p class="mb-2">选择一个模板查看详情</p>
            <p class="text-xs">或点击"新建模板"创建</p>
          </div>
        </div>
      </div>
    </div>

    <el-dialog
      v-model="showEditorDialog"
      :title="dialogTitle"
      width="700px"
      destroy-on-close
    >
      <PromptEditor
        v-model="editorForm"
        :is-editing="isEditing"
        :loading="editorLoading"
        @submit="handleEditorSubmit"
        @cancel="showEditorDialog = false"
      />
    </el-dialog>
  </div>
</template>
