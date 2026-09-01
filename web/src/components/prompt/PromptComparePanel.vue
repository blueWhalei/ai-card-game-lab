<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { tracesApi, type CompareResult } from '@/api/traces'
import { showApiError } from '@/utils/error'
import UiButton from '@/components/ui/Button.vue'
import UiSelect from '@/components/ui/Select.vue'
import UiSpinner from '@/components/ui/Spinner.vue'

const props = defineProps<{
  versions: string[]
}>()

const { t } = useI18n()
const version1 = ref('')
const version2 = ref('')
const loading = ref(false)
const result = ref<CompareResult | null>(null)

const options = computed(() =>
  props.versions.map((v) => ({ label: v, value: v })),
)

const canCompare = computed(
  () => Boolean(version1.value && version2.value && version1.value !== version2.value),
)

const compareColumns = computed(() => [
  t('prompt.colVersion'),
  t('prompt.colTraces'),
  t('prompt.colAvg'),
  t('prompt.colParser'),
])

async function runCompare(): Promise<void> {
  if (!canCompare.value) return
  loading.value = true
  try {
    const res = await tracesApi.compare(version1.value, version2.value)
    result.value = res.data
  } catch (e: unknown) {
    showApiError(e, t('prompt.compareFailed'))
    result.value = null
  } finally {
    loading.value = false
  }
}

function formatMs(ms: number): string {
  return `${Math.round(ms)}ms`
}

function formatRate(rate: number): string {
  return `${rate.toFixed(1)}%`
}
</script>

<template>
  <section class="space-y-3 rounded-ink-md border border-ink-border bg-ink-surface px-3 py-3">
    <div class="flex flex-wrap items-baseline justify-between gap-2">
      <h3 class="text-sm font-semibold text-ink-text">{{ t('prompt.compareTitle') }}</h3>
      <p class="text-xs text-ink-text-muted">{{ t('prompt.compareHint') }}</p>
    </div>
    <div v-if="versions.length < 2" class="text-sm text-ink-text-muted">
      {{ t('prompt.needTwo') }}
    </div>
    <div v-else class="space-y-3">
      <div class="flex flex-wrap items-end gap-2">
        <label class="min-w-[8rem] flex-1 space-y-1">
          <span class="text-xs font-medium text-ink-text-muted">{{ t('prompt.versionA') }}</span>
          <UiSelect
            v-model="version1"
            :options="options"
            :placeholder="t('prompt.pickVersion')"
            class="w-full"
          />
        </label>
        <label class="min-w-[8rem] flex-1 space-y-1">
          <span class="text-xs font-medium text-ink-text-muted">{{ t('prompt.versionB') }}</span>
          <UiSelect
            v-model="version2"
            :options="options"
            :placeholder="t('prompt.pickVersion')"
            class="w-full"
          />
        </label>
        <UiButton
          class="shrink-0"
          :disabled="!canCompare"
          :loading="loading"
          @click="runCompare"
        >
          {{ t('prompt.compare') }}
        </UiButton>
      </div>
      <div v-if="loading" class="flex justify-center py-3">
        <UiSpinner :label="t('common.loading')" />
      </div>
      <div v-else-if="result" class="overflow-x-auto rounded-ink border border-ink-border">
        <table class="w-full text-left text-sm">
          <thead class="bg-ink-surface-muted text-ink-text-muted">
            <tr>
              <th class="px-3 py-1.5 font-medium">{{ compareColumns[0] }}</th>
              <th class="px-3 py-1.5 font-medium">{{ compareColumns[1] }}</th>
              <th class="px-3 py-1.5 font-medium">{{ compareColumns[2] }}</th>
              <th class="px-3 py-1.5 font-medium">{{ compareColumns[3] }}</th>
            </tr>
          </thead>
          <tbody>
            <tr class="border-t border-ink-border">
              <td class="px-3 py-1.5">v{{ result.version1.version }}</td>
              <td class="px-3 py-1.5 tabular-nums">{{ result.version1.total_traces }}</td>
              <td class="px-3 py-1.5 tabular-nums">
                {{ formatMs(result.version1.avg_response_time_ms) }}
              </td>
              <td class="px-3 py-1.5 tabular-nums">{{ formatRate(result.version1.success_rate) }}</td>
            </tr>
            <tr class="border-t border-ink-border">
              <td class="px-3 py-1.5">v{{ result.version2.version }}</td>
              <td class="px-3 py-1.5 tabular-nums">{{ result.version2.total_traces }}</td>
              <td class="px-3 py-1.5 tabular-nums">
                {{ formatMs(result.version2.avg_response_time_ms) }}
              </td>
              <td class="px-3 py-1.5 tabular-nums">{{ formatRate(result.version2.success_rate) }}</td>
            </tr>
          </tbody>
        </table>
        <p class="px-3 py-1.5 text-xs text-ink-text-muted">
          {{
            t('prompt.diff', {
              ms: result.response_time_diff.toFixed(0),
              n: result.success_rate_diff.toFixed(1),
            })
          }}
        </p>
      </div>
    </div>
  </section>
</template>
