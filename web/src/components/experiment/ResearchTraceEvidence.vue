<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type { ResearchReport } from '@/api/researchApi'
import TraceRecordDocument from '@/components/trace/TraceRecordDocument.vue'
defineProps<{ report: ResearchReport }>()
const { t } = useI18n()
</script>
<template>
  <section v-if="report.record.trace_evidence?.length" id="report-trace-evidence">
    <h2>{{ t('traceCitation.title') }}</h2>
    <p>{{ t('traceCitation.reportScope') }}</p>
    <article
      v-for="(item, index) in report.record.trace_evidence"
      :id="`report-trace-${index + 1}`"
      :key="item.trace.id"
      tabindex="-1"
    >
      <h3>{{ t('traceCitation.citation', { n: index + 1 }) }}</h3>
      <p class="whitespace-pre-wrap">{{ item.note || t('report.missing') }}</p>
      <p>
        {{ t('traceCitation.currentStatus') }}
        {{
          t('traceCitation.status.' + (report.trace_evidence_status?.[item.trace.id] ?? 'unknown'))
        }}
      </p>
      <RouterLink
        v-if="
          ['available', 'changed'].includes(report.trace_evidence_status?.[item.trace.id] ?? '')
        "
        data-report-local
        :to="{
          path: '/pipeline/traces',
          query: {
            trace_id: item.trace.id,
            game_id: item.trace.game_id,
            experiment_id: item.source.experiment_id,
            report_id: report.record.id,
            trace_evidence: item.trace.id,
            comparison_id: report.record.comparison_id,
          },
        }"
        >{{ t('traceCitation.current') }}</RouterLink
      >
      <p>{{ t('traceCitation.frozen') }}</p>
      <TraceRecordDocument :preview="item" />
    </article>
  </section>
</template>
