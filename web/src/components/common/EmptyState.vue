<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import UiEmpty from '@/components/ui/Empty.vue'

interface Props {
  title?: string
  description?: string
}

const { t } = useI18n()
const props = defineProps<Props>()
</script>

<template>
  <UiEmpty
    :title="props.title ?? t('common.noData')"
    :description="props.description ?? t('common.emptyRecords')"
  >
    <slot name="action" />
  </UiEmpty>
</template>
