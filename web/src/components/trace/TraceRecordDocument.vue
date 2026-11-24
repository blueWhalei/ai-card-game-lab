<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { ResearchTracePreview } from '@/api/researchApi'
import { traceLatency, traceParserStatus } from '@/utils/traceMetrics'
import { formatDateTime } from '@/utils/format'
defineProps<{ preview: ResearchTracePreview }>()
const { t } = useI18n()
</script>
<template>
  <div class="space-y-ink-3 break-words text-body">
    <p>{{ t('traceCitation.scope') }}</p>
    <dl class="grid grid-cols-1 gap-ink-2 sm:grid-cols-2">
      <div>
        <dt>{{ t('traceCitation.identity') }}</dt>
        <dd>{{ preview.trace.id }}</dd>
      </div>
      <div>
        <dt>{{ t('traceCitation.origin') }}</dt>
        <dd>
          {{ preview.source.experiment_id }} / {{ preview.trace.game_id }} /
          {{ preview.source.deal_seed }}
        </dd>
      </div>
      <div>
        <dt>{{ t('traceCitation.position') }}</dt>
        <dd>{{ preview.trace.player_id }} / {{ preview.trace.round_number }}</dd>
      </div>
      <div>
        <dt>{{ t('traceCitation.model') }}</dt>
        <dd>{{ preview.trace.model }} / {{ preview.trace.prompt_version }}</dd>
      </div>
      <div>
        <dt>{{ t('traceCitation.created') }}</dt>
        <dd>{{ formatDateTime(preview.trace.created_at) }}</dd>
      </div>
      <div>
        <dt>{{ t('traceCitation.cutoff') }}</dt>
        <dd>{{ formatDateTime(preview.cutoff) }}</dd>
      </div>
      <div>
        <dt>{{ t('traceCitation.latency') }}</dt>
        <dd>
          {{ traceLatency(preview.trace.metrics.response_time_ms) ?? t('trace.notRecorded') }}
        </dd>
      </div>
      <div>
        <dt>{{ t('traceCitation.parser') }}</dt>
        <dd>
          {{
            traceParserStatus(preview.trace.metrics.parser_ok) === null
              ? t('trace.parserUnknown')
              : preview.trace.metrics.parser_ok
                ? t('filter.parseOk')
                : t('trace.parseFailed')
          }}
        </dd>
      </div>
    </dl>
    <p class="text-caption text-ink-text-secondary">
      {{ t('traceCitation.readAt', { at: formatDateTime(preview.read_at) }) }}
    </p>
    <p class="text-caption text-ink-text-secondary">
      {{ t('traceCitation.hash') }}
      <span class="break-all font-mono">{{ preview.source_hash }}</span>
    </p>
    <details
      v-for="section in [
        { key: 'input', value: preview.trace.input_snapshot },
        { key: 'output', value: preview.trace.output_data },
        { key: 'metrics', value: preview.trace.metrics },
        { key: 'spans', value: preview.trace.spans ?? [] },
      ]"
      :key="section.key"
    >
      <summary class="cursor-pointer">{{ t(`traceCitation.${section.key}`) }}</summary>
      <pre class="max-w-full overflow-auto whitespace-pre-wrap break-all text-caption">{{
        JSON.stringify(section.value, null, 2)
      }}</pre>
    </details>
  </div>
</template>
