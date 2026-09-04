<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import TraceWorkbenchPanel from '@/components/trace/TraceWorkbenchPanel.vue'

const route = useRoute()

const experimentId = computed(() => {
  const v = route.query.experiment_id
  return typeof v === 'string' && v ? v : undefined
})
</script>

<template>
  <TraceWorkbenchPanel :experiment-id="experimentId" />
</template>
