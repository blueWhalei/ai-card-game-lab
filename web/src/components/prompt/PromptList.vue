<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { confirmDialog } from '@/components/ui/confirm'
import type { PromptTemplateResponse } from '@/api/prompts'
import { TEMPLATE_KEY_LABELS } from '@/utils/constants'
import { formatDateTime } from '@/utils/format'
import UiSpinner from '@/components/ui/Spinner.vue'
import UiButton from '@/components/ui/Button.vue'
import UiBadge from '@/components/ui/Badge.vue'
import UiEmpty from '@/components/ui/Empty.vue'

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

const { t } = useI18n()

const groupedTemplates = computed(() => {
  const groups: Record<string, PromptTemplateResponse[]> = {}
  for (const item of props.templates) {
    const key = item.template_key
    if (!groups[key]) {
      groups[key] = []
    }
    groups[key]!.push(item)
  }
  return groups
})

const templateKeys = computed(() => Object.keys(groupedTemplates.value))

const tableHeaders = computed(() => [
  t('prompt.version'),
  t('common.status'),
  t('common.updatedAt'),
  t('common.actions'),
])

function getTemplateKeyLabel(key: string): string {
  return TEMPLATE_KEY_LABELS[key] || key
}

async function handleDelete(template: PromptTemplateResponse) {
  const ok = await confirmDialog({
    message: t('prompt.deleteConfirm', {
      name: getTemplateKeyLabel(template.template_key),
      version: template.version,
    }),
    title: t('common.confirm'),
    confirmText: t('common.delete'),
    danger: true,
  })
  if (!ok) return
  emit('delete', template.template_key, template.version)
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
  <div class="relative min-h-[120px]">
    <UiSpinner v-if="loading" overlay :label="t('common.loading')" />
    <UiEmpty v-if="!loading && templates.length === 0" :title="t('prompt.empty')">
      <UiButton variant="ghost" size="sm" @click="emit('create')">{{ t('prompt.createFirst') }}</UiButton>
    </UiEmpty>

    <div v-else-if="!loading" class="space-y-6">
      <div
        v-for="key in templateKeys"
        :key="key"
        class="rounded-ink-md border border-ink-border bg-ink-surface p-5"
      >
        <div class="mb-4 flex items-center justify-between border-b border-ink-border pb-3">
          <div class="flex items-center gap-3">
            <h3 class="text-base font-semibold text-ink-text">{{ getTemplateKeyLabel(key) }}</h3>
            <UiBadge variant="muted">{{
              t('prompt.versionCount', { n: groupedTemplates[key]?.length ?? 0 })
            }}</UiBadge>
          </div>
          <UiButton size="sm" @click="emit('create')">{{ t('prompt.newVersion') }}</UiButton>
        </div>

        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-ink-border text-left text-xs text-ink-text-muted">
                <th class="pb-2 font-medium">{{ tableHeaders[0] }}</th>
                <th class="pb-2 font-medium">{{ tableHeaders[1] }}</th>
                <th class="pb-2 font-medium">{{ tableHeaders[2] }}</th>
                <th class="pb-2 text-right font-medium">{{ tableHeaders[3] }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="template in groupedTemplates[key]"
                :key="template.version"
                class="group cursor-pointer border-b border-ink-border transition-colors hover:bg-ink-surface-muted"
                :class="{ 'bg-ink-surface-muted': selectedTemplateKey === key }"
                @click="handleSelect(template)"
              >
                <td class="py-3 font-medium text-ink-text">v{{ template.version }}</td>
                <td class="py-3">
                  <UiBadge :variant="template.is_active ? 'success' : 'muted'">
                    {{ template.is_active ? t('prompt.active') : t('prompt.inactive') }}
                  </UiBadge>
                </td>
                <td class="py-3 text-ink-text-muted">{{ formatDateTime(template.updated_at) }}</td>
                <td class="py-3 text-right">
                  <div
                    class="flex items-center justify-end gap-2 opacity-0 transition-opacity group-hover:opacity-100"
                  >
                    <UiButton
                      size="sm"
                      :variant="template.is_active ? 'secondary' : 'primary'"
                      @click.stop="handleActivate(template)"
                    >
                      {{ template.is_active ? t('prompt.deactivate') : t('prompt.activate') }}
                    </UiButton>
                    <UiButton
                      size="sm"
                      variant="ghost"
                      class="text-ink-danger"
                      @click.stop="handleDelete(template)"
                    >
                      {{ t('common.delete') }}
                    </UiButton>
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
