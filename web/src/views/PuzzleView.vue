<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import PuzzleWorkbenchPanel from '@/components/puzzle/PuzzleWorkbenchPanel.vue'

const route = useRoute()

const experimentId = computed(() => {
  const v = route.query.experiment_id
  return typeof v === 'string' && v ? v : undefined
})
</script>

<template>
  <PuzzleWorkbenchPanel :experiment-id="experimentId" />
</template>
