<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { ExperimentCompareResult } from '@/api/experimentApi'
import UiCheckbox from '@/components/ui/Checkbox.vue'
const props = defineProps<{
  result: ExperimentCompareResult
  allowed: string[]
  readonly?: boolean
}>()
const emit = defineEmits<{ 'update:allowed': [value: string[]] }>()
const { t } = useI18n()
function name(id: string) {
  return props.result.experiments.find((r) => r.id === id)?.name ?? id
}
function value(v: unknown, missing: boolean) {
  return missing ? t('compare.audit.unknown') : JSON.stringify(v)
}
function toggle(path: string, enabled: boolean) {
  emit(
    'update:allowed',
    enabled ? [...new Set([...props.allowed, path])] : props.allowed.filter((p) => p !== path),
  )
}
</script>
<template>
  <section
    class="space-y-4 rounded-ink-md border border-ink-border bg-ink-surface p-4"
    :aria-label="t('compare.audit.title')"
  >
    <h2 class="text-lead font-semibold text-ink-text">{{ t('compare.audit.title') }}</h2>
    <p class="text-body text-ink-text-secondary">
      {{ t('compare.audit.reference', { name: name(result.experiments[0]?.id ?? '') }) }}
    </p>
    <template v-if="result.protocol_review">
      <p class="font-medium text-ink-text">
        {{
          t(
            result.protocol_review.controlled
              ? 'compare.audit.controlled'
              : 'compare.audit.descriptive',
          )
        }}
      </p>
      <p
        v-for="reason in result.protocol_review.reasons"
        :key="reason"
        class="text-caption text-ink-text-secondary"
      >
        {{ t(`compare.audit.reasons.${reason}`) }}
      </p>
      <details
        v-if="result.protocol_review.unknown.length"
        class="text-caption text-ink-text-secondary"
      >
        <summary class="cursor-pointer">{{ t('compare.audit.unknownFields') }}</summary>
        <p
          v-for="item in result.protocol_review.unknown"
          :key="item.experiment_id"
          class="mt-2 break-words"
        >
          {{ name(item.experiment_id) }}: {{ item.fields.join(', ') }}
        </p>
      </details>
      <p class="text-caption text-ink-text-secondary">{{ t('compare.audit.declarationHint') }}</p>
      <details v-if="result.protocol_review.differences.length">
        <summary class="cursor-pointer text-body font-medium">
          {{ t('compare.audit.differenceCount', { n: result.protocol_review.differences.length }) }}
        </summary>
        <div class="mt-3 overflow-x-auto">
          <table class="w-full text-left text-caption">
            <thead>
              <tr>
                <th class="p-2">{{ t('compare.audit.field') }}</th>
                <th class="p-2">{{ t('compare.audit.before') }}</th>
                <th class="p-2">{{ t('compare.audit.after') }}</th>
                <th class="p-2">{{ t('compare.audit.declared') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="diff in result.protocol_review.differences"
                :key="`${diff.experiment_id}:${diff.path}`"
                class="border-t border-ink-border"
              >
                <th class="p-2 font-normal">
                  <p>{{ name(diff.experiment_id) }}</p>
                  <code class="break-all">{{ diff.path }}</code>
                </th>
                <td class="max-w-72 p-2">
                  <pre class="max-h-40 overflow-auto whitespace-pre-wrap break-all">{{
                    value(diff.baseline, diff.baseline_missing)
                  }}</pre>
                </td>
                <td class="max-w-72 p-2">
                  <pre class="max-h-40 overflow-auto whitespace-pre-wrap break-all">{{
                    value(diff.variant, diff.variant_missing)
                  }}</pre>
                </td>
                <td class="p-2">
                  <UiCheckbox
                    v-if="diff.allowable"
                    :model-value="allowed.includes(diff.path)"
                    :disabled="readonly"
                    :label="diff.path"
                    @update:model-value="toggle(diff.path, $event)"
                  /><span v-else>{{ t('compare.audit.fixed') }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </details>
    </template>
    <template v-if="result.coverage">
      <h3 class="font-semibold text-ink-text">
        {{
          t('compare.audit.coverage', {
            planned: result.coverage.planned_shared,
            effective: result.coverage.effective_n,
          })
        }}
      </h3>
      <p class="text-caption text-ink-text-secondary">{{ t('compare.audit.cohortHint') }}</p>
      <div class="overflow-x-auto">
        <table class="w-full text-left text-caption">
          <thead>
            <tr>
              <th class="p-2">{{ t('compare.colExperiment') }}</th>
              <th class="p-2">{{ t('compare.audit.planned') }}</th>
              <th class="p-2">{{ t('compare.audit.valid') }}</th>
              <th class="p-2">{{ t('compare.audit.notShared') }}</th>
              <th class="p-2">{{ t('compare.audit.excluded') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in result.coverage.experiments"
              :key="item.experiment_id"
              class="border-t border-ink-border"
            >
              <th class="p-2 font-normal">{{ name(item.experiment_id) }}</th>
              <td class="p-2">{{ item.planned }}</td>
              <td class="p-2">{{ item.valid }}</td>
              <td class="p-2">{{ item.not_shared }}</td>
              <td class="p-2">
                <p v-for="(n, reason) in item.excluded" :key="reason">
                  {{ t(`compare.audit.exclusions.${reason}`) }}: {{ n }}
                </p>
                <p>
                  {{
                    t('compare.audit.outside', {
                      missing: item.missing_seed_games,
                      unplanned: item.unplanned_games,
                    })
                  }}
                </p>
                <details v-if="item.conflicts.length">
                  <summary class="cursor-pointer">{{ t('compare.audit.conflicts') }}</summary>
                  <p v-for="conflict in item.conflicts" :key="conflict.seed" class="break-all">
                    {{ conflict.seed }}: {{ conflict.game_ids.join(', ') }}
                  </p>
                </details>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
    <p v-if="result.paired_summary?.paired_ci" class="text-caption text-ink-text-secondary">
      {{
        t('compare.audit.statistics', {
          p: result.paired_summary.paired_p?.toFixed(4),
          low: (result.paired_summary.paired_ci[0] * 100).toFixed(1),
          high: (result.paired_summary.paired_ci[1] * 100).toFixed(1),
        })
      }}
    </p>
    <p class="text-caption text-ink-text-secondary">{{ t('compare.audit.metricScope') }}</p>
  </section>
</template>
