<script setup lang="ts">
import UiSpinner from '@/components/ui/Spinner.vue'

interface Props {
  text?: string
}

withDefaults(defineProps<Props>(), {
  text: '加载中...',
})
</script>

<template>
  <UiSpinner size="lg" :label="text" class="py-12" />
</template>
