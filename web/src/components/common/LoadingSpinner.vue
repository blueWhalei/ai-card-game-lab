<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import UiSpinner from '@/components/ui/Spinner.vue'

interface Props {
  text?: string
}

const { t } = useI18n()
const props = defineProps<Props>()
</script>

<template>
  <UiSpinner size="lg" :label="props.text ?? t('common.loadingEllipsis')" class="py-12" />
</template>
