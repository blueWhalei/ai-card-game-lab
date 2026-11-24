<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { operationKind } from '@/utils/studyOperations'
import StudyOperations from './StudyOperations.vue'
import StudyTrainingOperations from './StudyTrainingOperations.vue'
import StudyFinance from './StudyFinance.vue'
import UiButton from '@/components/ui/Button.vue'
defineProps<{ studyId: string }>()
const { t } = useI18n(),
  route = useRoute(),
  router = useRouter()
const kind = computed(() => operationKind(route.query))
function select(value: 'games' | 'training' | 'finance') {
  void router.replace({
    query: { ...route.query, task_kind: value, task_state: 'all', task_page: '1' },
  })
}
</script>
<template>
  <div class="space-y-ink-4">
    <div class="flex flex-wrap gap-ink-2" :aria-label="t('operations.taskKind')">
      <UiButton
        v-for="value in ['games', 'training', 'finance'] as const"
        :key="value"
        :variant="kind === value ? 'primary' : 'secondary'"
        :aria-pressed="kind === value"
        @click="select(value)"
        >{{ t(`operations.kinds.${value}`) }}</UiButton
      >
    </div>
    <StudyOperations v-if="kind === 'games'" :study-id="studyId" />
    <StudyTrainingOperations v-else-if="kind === 'training'" :study-id="studyId" />
    <StudyFinance v-else-if="kind === 'finance'" :study-id="studyId" />
    <p v-else role="alert">{{ t('operations.invalidKind') }}</p>
  </div>
</template>
