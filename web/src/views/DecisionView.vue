<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import DecisionWorkbenchPanel from '@/components/decision/DecisionWorkbenchPanel.vue'
import ExperimentContextBar from '@/components/common/ExperimentContextBar.vue'

const route = useRoute()
const router = useRouter()

const experimentId = computed(() => {
  const v = route.query.experiment_id
  return typeof v === 'string' && v ? v : undefined
})
</script>

<template>
  <div>
    <div v-if="experimentId" class="page-container pb-0">
      <ExperimentContextBar
        :experiment-id="experimentId"
        return-tab="decisions"
        clearable
        @clear="
          router.replace({
            path: '/decisions',
            query: { ...route.query, experiment_id: undefined },
          })
        "
      />
    </div>
    <DecisionWorkbenchPanel :experiment-id="experimentId" />
  </div>
</template>
