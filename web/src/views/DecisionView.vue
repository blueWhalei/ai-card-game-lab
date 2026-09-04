<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import DecisionWorkbenchPanel from '@/components/decision/DecisionWorkbenchPanel.vue'

const route = useRoute()

const experimentId = computed(() => {
  const v = route.query.experiment_id
  return typeof v === 'string' && v ? v : undefined
})
</script>

<template>
  <DecisionWorkbenchPanel :experiment-id="experimentId" />
</template>
