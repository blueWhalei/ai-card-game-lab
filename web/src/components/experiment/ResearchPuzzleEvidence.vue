<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type { ResearchReport } from '@/api/researchApi'
import PuzzleResultDocument from '@/components/puzzle/PuzzleResultDocument.vue'
defineProps<{ report: ResearchReport }>()
const { t } = useI18n()
</script>

<template>
  <section v-if="report.record.puzzle_evidence?.length" id="report-puzzle-evidence">
    <h2>{{ t('puzzleCitation.title') }}</h2>
    <p>{{ t('puzzleCitation.reportScope') }}</p>
    <article
      v-for="(item, index) in report.record.puzzle_evidence"
      :id="`report-test-${index + 1}`"
      :key="`${item.result.report.pack_id}/${item.result.report.run_id}`"
      tabindex="-1"
    >
      <h3>{{ t('puzzleCitation.citation', { n: index + 1 }) }}</h3>
      <p class="whitespace-pre-wrap">{{ item.note || t('report.missing') }}</p>
      <p>
        {{ t('puzzleCitation.currentRecord') }}：{{
          t(
            'puzzleCitation.status.' +
              (report.puzzle_evidence_status?.[index]?.record_status ?? 'unknown'),
          )
        }}
      </p>
      <p v-if="report.puzzle_evidence_status?.[index]?.source_status">
        {{ t('puzzleCitation.currentPack') }}：{{
          t('puzzleHistory.sourceStatus.' + report.puzzle_evidence_status[index]!.source_status)
        }}
      </p>
      <component :is="item.sources.length > 1 ? 'details' : 'div'">
        <summary v-if="item.sources.length > 1">
          {{ t('puzzleBatch.sourceStates', { n: item.sources.length }) }}
        </summary>
        <p v-for="source in item.sources" :key="source.decision.id" class="report-muted">
          {{ source.decision.id }} ·
          {{
            report.puzzle_evidence_status?.[index]?.decisions[source.decision.id]
              ? t(
                  'researchReport.status.' +
                    report.puzzle_evidence_status[index]!.decisions[source.decision.id],
                )
              : t('report.unknownStatus')
          }}
        </p>
      </component>
      <RouterLink
        v-if="
          ['available', 'changed'].includes(
            report.puzzle_evidence_status?.[index]?.record_status ?? '',
          )
        "
        data-report-local
        :to="{
          path: '/pipeline/puzzles',
          query: {
            pack_id: item.result.report.pack_id,
            result_id: item.result.report.run_id,
            report_id: report.record.id,
            puzzle_evidence: `${item.result.report.pack_id}/${item.result.report.run_id}`,
          },
        }"
        >{{ t('puzzleCitation.current') }}</RouterLink
      >
      <p class="report-muted">{{ t('puzzleCitation.frozen') }}</p>
      <PuzzleResultDocument :result="item.result" :page="1" embedded frozen :local-links="false" />
      <details>
        <summary>{{ t('puzzleCitation.sources') }}</summary>
        <pre>{{ JSON.stringify(item.sources, null, 2) }}</pre>
      </details>
    </article>
  </section>
</template>
