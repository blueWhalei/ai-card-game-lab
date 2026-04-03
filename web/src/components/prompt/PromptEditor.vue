<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { TEMPLATE_KEY_OPTIONS } from '@/utils/constants'

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

const formRef = ref<FormInstance>()

const formRules: FormRules = {
  template_key: [{ required: true, message: '请选择模板类型', trigger: 'change' }],
  version: [
    { required: true, message: '请输入版本号', trigger: 'blur' },
    {
      pattern: /^\d+\.\d+\.\d+$/,
      message: '版本号格式应为 x.y.z (如 1.0.0)',
      trigger: 'blur',
    },
  ],
  content: [
    { required: true, message: '请输入模板内容', trigger: 'blur' },
    { min: 10, message: '内容至少需要 10 个字符', trigger: 'blur' },
  ],
}

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
  (newValue) => {
    if (newValue && formRef.value) {
      formRef.value.clearValidate()
    }
  },
)

function validateForm(): boolean {
  let isValid = false
  formRef.value?.validate((valid) => {
    isValid = valid
  })
  return isValid
}

function handleSubmit() {
  if (!validateForm()) {
    return
  }
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
  <div class="prompt-editor">
    <el-form
      ref="formRef"
      :model="form"
      :rules="formRules"
      label-width="100px"
      label-position="top"
    >
      <el-form-item label="模板类型" prop="template_key">
        <el-select
          v-model="form.template_key"
          placeholder="请选择模板类型"
          style="width: 100%"
          :disabled="isEditing"
        >
          <el-option
            v-for="item in TEMPLATE_KEY_OPTIONS"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="版本号" prop="version">
        <el-input
          v-model="form.version"
          placeholder="如 1.0.0"
          clearable
        />
      </el-form-item>

      <el-form-item label="模板内容" prop="content">
        <el-input
          v-model="form.content"
          type="textarea"
          :rows="12"
          placeholder="请输入提示词模板内容，支持变量占位符，如 {player_name}、{game_state} 等"
          clearable
        />
      </el-form-item>

      <el-form-item label="启用状态">
        <el-switch
          v-model="form.is_active"
          active-text="启用"
          inactive-text="禁用"
        />
      </el-form-item>

      <el-divider content-position="left">实时预览</el-divider>

      <div class="preview-container">
        <div class="preview-header">
          <span class="preview-label">内容预览</span>
          <span class="preview-status" :class="{ active: form.is_active }">
            {{ form.is_active ? '已启用' : '已禁用' }}
          </span>
        </div>
        <div class="preview-content">
          <pre>{{ previewContent }}</pre>
        </div>
      </div>
    </el-form>

    <div class="form-actions">
      <el-button @click="handleCancel">取消</el-button>
      <el-button
        type="primary"
        :loading="loading"
        @click="handleSubmit"
      >
        {{ isEditing ? '保存' : '创建' }}
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.prompt-editor {
  padding: 0;
}

.preview-container {
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  overflow: hidden;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
}

.preview-label {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
}

.preview-status {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 12px;
  background: #e4e7ed;
  color: #909399;
}

.preview-status.active {
  background: #e1f3d8;
  color: #67c23a;
}

.preview-content {
  max-height: 200px;
  overflow-y: auto;
  padding: 12px;
  background: #fafafa;
}

.preview-content pre {
  margin: 0;
  font-family: 'Courier New', Courier, monospace;
  font-size: 13px;
  line-height: 1.6;
  color: #303133;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #e4e7ed;
}
</style>
