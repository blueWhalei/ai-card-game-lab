<script setup lang="ts">
import { computed } from 'vue'
import { ElMessageBox } from 'element-plus'
import type { PromptTemplateResponse } from '@/api/prompts'
import { TEMPLATE_KEY_LABELS } from '@/utils/constants'
import { formatDateTime } from '@/utils/format'

const props = defineProps<{
  templates: PromptTemplateResponse[]
  loading: boolean
  selectedTemplateKey?: string
}>()

const emit = defineEmits<{
  activate: [templateKey: string, version: string]
  deactivate: [templateKey: string, version: string]
  delete: [templateKey: string, version: string]
  select: [templateKey: string, version: string]
  create: []
}>()

const groupedTemplates = computed(() => {
  const groups: Record<string, PromptTemplateResponse[]> = {}
  for (const t of props.templates) {
    const key = t.template_key
    if (!groups[key]) {
      groups[key] = []
    }
    groups[key]!.push(t)
  }
  return groups
})

const templateKeys = computed(() => Object.keys(groupedTemplates.value))

function getTemplateKeyLabel(key: string): string {
  return TEMPLATE_KEY_LABELS[key] || key
}

async function handleDelete(template: PromptTemplateResponse) {
  try {
    await ElMessageBox.confirm(
      `确定删除模板 "${getTemplateKeyLabel(template.template_key)} v${template.version}" 吗？`,
      '删除确认',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    )
    emit('delete', template.template_key, template.version)
  } catch {
    /* cancelled */
  }
}

function handleActivate(template: PromptTemplateResponse) {
  if (template.is_active) {
    emit('deactivate', template.template_key, template.version)
  } else {
    emit('activate', template.template_key, template.version)
  }
}

function handleSelect(template: PromptTemplateResponse) {
  emit('select', template.template_key, template.version)
}
</script>

<template>
  <div v-loading="loading">
    <div v-if="!loading && templates.length === 0" class="py-16 text-center text-[#86868b]">
      暂无提示词模板
      <button class="ml-2 text-[#0071e3] hover:underline" @click="emit('create')">
        创建第一个模板
      </button>
    </div>

    <div v-else class="space-y-6">
      <div
        v-for="key in templateKeys"
        :key="key"
        class="apple-card"
      >
        <div class="mb-4 flex items-center justify-between border-b border-[#f5f5f7] pb-3">
          <div class="flex items-center gap-3">
            <h3 class="text-base font-semibold text-[#1d1d1f]">{{ getTemplateKeyLabel(key) }}</h3>
            <span class="rounded-full bg-[#f5f5f7] px-2 py-0.5 text-xs text-[#86868b]">
              {{ groupedTemplates[key]?.length ?? 0 }} 个版本
            </span>
          </div>
          <button
            class="rounded-full bg-[#0071e3] px-4 py-1.5 text-xs font-medium text-white transition-all hover:bg-[#0077ed]"
            @click="emit('create')"
          >
            新建版本
          </button>
        </div>

        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-[#f5f5f7] text-left text-xs text-[#86868b]">
                <th class="pb-2 font-medium">版本</th>
                <th class="pb-2 font-medium">状态</th>
                <th class="pb-2 font-medium">更新时间</th>
                <th class="pb-2 font-medium text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="template in groupedTemplates[key]"
                :key="template.version"
                class="group cursor-pointer border-b border-[#f5f5f7] transition-colors hover:bg-[#f5f5f7]"
                :class="{ 'bg-[#f5f5f7]': selectedTemplateKey === key }"
                @click="handleSelect(template)"
              >
                <td class="py-3 font-medium text-[#1d1d1f]">v{{ template.version }}</td>
                <td class="py-3">
                  <span
                    v-if="template.is_active"
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
                </td>
                <td class="py-3 text-[#86868b]">{{ formatDateTime(template.updated_at) }}</td>
                <td class="py-3 text-right">
                  <div class="flex items-center justify-end gap-2 opacity-0 transition-opacity group-hover:opacity-100">
                    <button
                      class="rounded-full px-3 py-1 text-xs font-medium transition-all"
                      :class="template.is_active
                        ? 'bg-[#fff3e0] text-[#e65100] hover:bg-[#ffe0b2]'
                        : 'bg-[#e6f2ff] text-[#0071e3] hover:bg-[#cce4ff]'"
                      @click.stop="handleActivate(template)"
                    >
                      {{ template.is_active ? '停用' : '激活' }}
                    </button>
                    <button
                      class="rounded-full bg-[#fff5f5] px-3 py-1 text-xs font-medium text-[#ff3b30] transition-all hover:bg-[#ffe0e0]"
                      @click.stop="handleDelete(template)"
                    >
                      删除
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>
