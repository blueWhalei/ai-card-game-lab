<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import UiButton from '@/components/ui/Button.vue'
const props = defineProps<{
  ids: string[]
  included: string[]
  disabled?: boolean
  pair?: boolean
}>()
const emit = defineEmits<{ cite: [ids: string[]] }>()
const { t } = useI18n()
const already = computed(
  () => props.ids.length > 0 && props.ids.every((id) => props.included.includes(id)),
)
</script>
<template>
  <UiButton :disabled="disabled || !ids.length || already" @click="emit('cite', ids)">
    {{ t(already ? 'focus.included' : pair ? 'paired.cite' : 'focus.include') }}
  </UiButton>
</template>
