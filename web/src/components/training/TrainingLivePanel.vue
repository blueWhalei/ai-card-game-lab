<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { systemApi } from '@/api/systemApi'
import type { RuntimeStats } from '@/api/systemApi'
import type { TrainingTask } from '@/api/trainingApi'
import { TRAINING_STATUS_MAP } from '@/utils/constants'
import UiButton from '@/components/ui/Button.vue'
import UiBadge from '@/components/ui/Badge.vue'
import UiProgress from '@/components/ui/Progress.vue'

const props = defineProps<{
  tasks: TrainingTask[]
  onCancel: (id: string) => void
  cancelling?: boolean
}>()

const { t } = useI18n()
const stats = ref<RuntimeStats | null>(null)
let pollTimer: ReturnType<typeof setInterval> | null = null

const ACTIVE_STATUSES = ['pending', 'exporting', 'training']

const activeTask = computed<TrainingTask | null>(() => {
  // Prefer the most recent task that is currently active.
  for (const status of ACTIVE_STATUSES) {
    const found = props.tasks.find((task) => task.status === status)
    if (found) return found
  }
  return null
})

const hasActiveTraining = computed(() => activeTask.value !== null)

const memoryLow = computed(() => {
  const avail = stats.value?.memory_available_mb
  return typeof avail === 'number' && avail < 8192
})

const cpuPercent = computed(() => Math.round(stats.value?.cpu_percent ?? 0))
const memoryUsedMb = computed(() => Math.round(stats.value?.memory_used_mb ?? 0))
const memoryAvailMb = computed(() => Math.round(stats.value?.memory_available_mb ?? 0))
const memoryTotalMb = computed(() => Math.round(stats.value?.memory_total_mb ?? 0))

const progressPercent = computed(() => {
  const p = activeTask.value?.progress
  if (typeof p !== 'number') return 0
  return Math.min(100, Math.max(0, Math.round(p * 100)))
})

const taskStatus = computed(() => activeTask.value?.status ?? '')
const taskStatusLabel = computed(
  () => TRAINING_STATUS_MAP[taskStatus.value]?.label ?? taskStatus.value,
)

async function fetchStats() {
  try {
    const res = await systemApi.getRuntimeStats()
    stats.value = res.data
  } catch {
    /* keep last known stats */
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(fetchStats, 1500)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

watch(
  hasActiveTraining,
  (active) => {
    if (active) {
      void fetchStats()
      startPolling()
    } else {
      stopPolling()
    }
  },
  { immediate: true },
)

onMounted(() => {
  if (hasActiveTraining.value) {
    void fetchStats()
    startPolling()
  }
})

onUnmounted(stopPolling)

function handleCancel() {
  if (!activeTask.value) return
  props.onCancel(activeTask.value.id)
}
</script>

<template>
  <div
    v-if="hasActiveTraining"
    class="mb-6 rounded-ink-md border border-ink-border bg-ink-surface p-4"
  >
    <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
      <div class="flex items-center gap-2">
        <span class="text-sm font-semibold text-ink-text">{{ t('training.liveTitle') }}</span>
        <UiBadge variant="muted">{{ taskStatusLabel }}</UiBadge>
        <span v-if="activeTask" class="text-xs text-ink-text-muted">
          {{ activeTask.name }} · {{ activeTask.base_model }}
        </span>
      </div>
      <UiButton
        variant="ghost"
        size="sm"
        class="text-ink-danger"
        :loading="props.cancelling"
        @click="handleCancel"
      >
        {{ t('common.cancel') }}
      </UiButton>
    </div>

    <div class="mb-3">
      <div class="mb-1 flex items-center justify-between text-xs text-ink-text-muted">
        <span>{{ t('training.liveProgress') }}</span>
        <span>{{ progressPercent }}%</span>
      </div>
      <UiProgress :value="progressPercent" />
    </div>

    <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
      <div>
        <div class="mb-1 flex items-center justify-between text-xs text-ink-text-muted">
          <span>{{ t('training.cpu') }}</span>
          <span>{{ cpuPercent }}%</span>
        </div>
        <UiProgress :value="cpuPercent" />
      </div>
      <div>
        <div
          class="mb-1 flex items-center justify-between text-xs"
          :class="memoryLow ? 'text-ink-accent' : 'text-ink-text-muted'"
        >
          <span>{{ t('training.memory') }}</span>
          <span>
            {{ memoryUsedMb }} MB / {{ memoryAvailMb }} MB
            <span class="text-ink-text-muted">{{ t('training.memoryTotal', { n: memoryTotalMb }) }}</span>
          </span>
        </div>
        <UiProgress
          :value="memoryTotalMb > 0 ? Math.round((memoryUsedMb / memoryTotalMb) * 100) : 0"
          :class="memoryLow ? 'bg-ink-accent-muted' : ''"
        />
        <div v-if="memoryLow" class="mt-1 text-xs text-ink-accent">
          {{ t('training.lowMemory') }}
        </div>
      </div>
    </div>
  </div>
</template>
