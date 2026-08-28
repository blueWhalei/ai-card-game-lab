<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { TEMPLATE_KEY_OPTIONS } from '@/utils/constants'
import UiInput from '@/components/ui/Input.vue'
import UiTextarea from '@/components/ui/Textarea.vue'
import UiSelect from '@/components/ui/Select.vue'
import UiSwitch from '@/components/ui/Switch.vue'
import UiButton from '@/components/ui/Button.vue'
import UiBadge from '@/components/ui/Badge.vue'
import { toast } from '@/components/ui/toast'

export interface PromptTemplate {
  id?: string
  template_key: string
  version: string
  content: string
  is_active: boolean
  created_at?: string
}

export interface CreatePromptRequest {
  template_key: string
  version: string
  content: string
  is_active: boolean
}

export interface UpdatePromptRequest {
  version: string
  content: string
  is_active: boolean
}

export interface PromptEditorProps {
  modelValue: PromptTemplate | CreatePromptRequest
  isEditing?: boolean
  loading?: boolean
}

export interface PromptEditorEmits {
  (e: 'update:modelValue', value: PromptTemplate | CreatePromptRequest): void
  (e: 'submit'): void
  (e: 'cancel'): void
}

const props = withDefaults(defineProps<PromptEditorProps>(), {
  isEditing: false,
  loading: false,
})

const emit = defineEmits<PromptEditorEmits>()

const errors = ref<Record<string, string>>({})

const templateKeyOptions = TEMPLATE_KEY_OPTIONS.map((item) => ({
  label: item.label,
  value: item.value,
}))

const form = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const previewContent = computed(() => {
  const content = form.value.content
  if (!content) return '暂无内容'
  return content
})

watch(
  () => props.isEditing,
  () => {
    errors.value = {}
  },
)

function validateForm(): boolean {
  const next: Record<string, string> = {}
  if (!form.value.template_key) {
    next.template_key = '请选择模板类型'
  }
  if (!form.value.version?.trim()) {
    next.version = '请输入版本号'
  } else if (!/^\d+\.\d+\.\d+$/.test(form.value.version)) {
    next.version = '版本号格式应为 x.y.z (如 1.0.0)'
  }
  if (!form.value.content?.trim()) {
    next.content = '请输入模板内容'
  } else if (form.value.content.trim().length < 10) {
    next.content = '内容至少需要 10 个字符'
  }
  errors.value = next
  if (Object.keys(next).length > 0) {
    toast.warning(Object.values(next)[0] ?? '请检查表单')
    return false
  }
  return true
}

function handleSubmit() {
  if (!validateForm()) return
  emit('submit')
}

function handleCancel() {
  emit('cancel')
}

defineExpose({
  validateForm,
})
</script>

<template>
  <div class="space-y-4">
    <div>
      <label class="mb-1.5 block text-sm font-medium text-ink-text">模板类型</label>
      <UiSelect
        :model-value="form.template_key"
        :options="templateKeyOptions"
        placeholder="请选择模板类型"
        :disabled="isEditing"
        class="w-full"
        @update:model-value="(v) => (form = { ...form, template_key: v })"
      />
      <p v-if="errors.template_key" class="mt-1 text-xs text-ink-danger">{{ errors.template_key }}</p>
    </div>

    <div>
      <label class="mb-1.5 block text-sm font-medium text-ink-text">版本号</label>
      <UiInput
        :model-value="form.version"
        placeholder="如 1.0.0"
        class="w-full"
        @update:model-value="(v) => (form = { ...form, version: v })"
      />
      <p v-if="errors.version" class="mt-1 text-xs text-ink-danger">{{ errors.version }}</p>
    </div>

    <div>
      <label class="mb-1.5 block text-sm font-medium text-ink-text">模板内容</label>
      <UiTextarea
        :model-value="form.content"
        :rows="12"
        placeholder="请输入提示词模板内容，支持变量占位符，如 {player_name}、{game_state} 等"
        class="w-full"
        @update:model-value="(v) => (form = { ...form, content: v })"
      />
      <p v-if="errors.content" class="mt-1 text-xs text-ink-danger">{{ errors.content }}</p>
    </div>

    <div class="flex items-center gap-3">
      <label class="text-sm font-medium text-ink-text">启用状态</label>
      <UiSwitch
        :model-value="form.is_active"
        @update:model-value="(v) => (form = { ...form, is_active: v })"
      />
      <span class="text-xs text-ink-text-muted">{{ form.is_active ? '启用' : '禁用' }}</span>
    </div>

    <div class="border-t border-ink-border pt-4">
      <p class="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-text-muted">实时预览</p>
      <div class="overflow-hidden rounded-ink-md border border-ink-border">
        <div class="flex items-center justify-between border-b border-ink-border bg-ink-surface-muted px-3 py-2">
          <span class="text-sm font-medium text-ink-text">内容预览</span>
          <UiBadge :variant="form.is_active ? 'success' : 'muted'">
            {{ form.is_active ? '已启用' : '已禁用' }}
          </UiBadge>
        </div>
        <div class="max-h-[200px] overflow-y-auto bg-ink-paper p-3">
          <pre class="m-0 whitespace-pre-wrap break-words font-mono text-[13px] leading-relaxed text-ink-text">{{
            previewContent
          }}</pre>
        </div>
      </div>
    </div>

    <div class="flex justify-end gap-2 border-t border-ink-border pt-4">
      <UiButton variant="secondary" @click="handleCancel">取消</UiButton>
      <UiButton :loading="loading" @click="handleSubmit">
        {{ isEditing ? '保存' : '创建' }}
      </UiButton>
    </div>
  </div>
</template>
