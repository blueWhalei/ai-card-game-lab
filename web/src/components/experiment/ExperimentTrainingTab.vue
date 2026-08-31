<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type { TrainingTask } from '@/api/trainingApi'
import { formatDateTime } from '@/utils/format'
import UiBadge from '@/components/ui/Badge.vue'

defineProps<{
  tasks: TrainingTask[]
  experimentId: string
}>()

const { t } = useI18n()
const router = useRouter()
</script>

<template>
  <section class="space-y-2">
    <p
      v-if="tasks.length === 0"
      class="rounded-ink-md border border-dashed border-ink-border bg-ink-surface px-4 py-5 text-center text-sm text-ink-text-muted"
    >
      {{ t('trainingTab.empty') }}
    </p>
    <div v-else class="overflow-x-auto rounded-ink-md border border-ink-border">
      <table class="w-full min-w-lg text-left text-sm">
        <thead class="bg-ink-surface-muted text-ink-text-muted">
          <tr>
            <th class="px-3 py-2 font-medium">{{ t('trainingTab.colTask') }}</th>
            <th class="px-3 py-2 font-medium">{{ t('trainingTab.colStatus') }}</th>
            <th class="px-3 py-2 font-medium">{{ t('trainingTab.colProgress') }}</th>
            <th class="px-3 py-2 font-medium">{{ t('trainingTab.colCreated') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="task in tasks" :key="task.id" class="border-t border-ink-border">
            <td class="px-3 py-2">
              <button
                type="button"
                class="font-medium text-ink-primary hover:underline"
                @click="
                  router.push({
                    path: '/training',
                    query: { experiment_id: experimentId, task_id: task.id },
                  })
                "
              >
                {{ task.name }}
              </button>
            </td>
            <td class="px-3 py-2">
              <UiBadge
                :variant="
                  task.status === 'completed'
                    ? 'success'
                    : task.status === 'failed'
                      ? 'danger'
                      : 'muted'
                "
              >
                {{ task.status }}
              </UiBadge>
            </td>
            <td class="px-3 py-2 tabular-nums">{{ Math.round((task.progress || 0) * 100) }}%</td>
            <td class="px-3 py-2 whitespace-nowrap text-ink-text-secondary">
              {{ formatDateTime(task.created_at) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
