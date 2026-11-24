<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { ReconciliationResult } from '@/api/billingReconciliationApi'
import { formatDateTime } from '@/utils/format'
import UiButton from '@/components/ui/Button.vue'
defineProps<{ result: ReconciliationResult; disabled?: boolean }>()
defineEmits<{ evidence: [attemptId: string] }>()
const { t } = useI18n()
const utc = (value: number) =>
  new Date(value * 1000).toISOString().replace('T', ' ').replace('.000Z', '')
</script>
<template>
  <div class="space-y-ink-2 break-words">
    <p role="status" class="font-medium">
      {{ t(`billing.reconciliation.result.${result.result}`) }}
    </p>
    <p v-for="reason in result.reasons" :key="reason">
      {{ t(`billing.reconciliation.reasons.${reason}`) }}
    </p>
    <dl class="space-y-ink-2">
      <dt>{{ t('billing.reconciliation.amount') }}</dt>
      <dd>{{ result.input.source_amount }} {{ result.input.currency }}</dd>
      <dt>{{ t('billing.reconciliation.interfaceAmount') }}</dt>
      <dd>{{ result.interface_amount ?? t('billing.reconciliation.unknown') }}</dd>
      <dt>{{ t('billing.reconciliation.difference') }}</dt>
      <dd>{{ result.difference ?? t('billing.reconciliation.unknown') }}</dd>
    </dl>
    <p>
      {{ t('billing.reconciliation.start') }}：{{ result.input.period_start }} ·
      {{ t('billing.reconciliation.end') }}：{{ result.input.period_end }}
    </p>
    <p>
      {{ t(`billing.reconciliation.types.${result.input.source_type}`) }} ·
      {{ result.input.source_reference }}
    </p>
    <p>
      {{ t('billing.reconciliation.organization') }}：{{ result.input.organization_id }} ·
      {{
        t(
          result.csv_evidence
            ? 'billing.reconciliation.csv.project'
            : 'billing.reconciliation.project',
        )
      }}：{{ result.input.project_id ?? t('finance.notSet') }}
    </p>
    <p class="whitespace-pre-wrap">{{ result.input.scope_note }}</p>
    <details v-if="result.csv_evidence" class="space-y-ink-2">
      <summary class="cursor-pointer text-ink-accent">
        {{ t('billing.reconciliation.csv.evidence', { name: result.csv_evidence.filename }) }}
      </summary>
      <p>
        {{
          t('billing.reconciliation.csv.dataRows', {
            count: result.csv_evidence.row_count,
            first: result.csv_evidence.first_service_date,
            last: result.csv_evidence.last_service_date,
          })
        }}
      </p>
      <ul class="space-y-ink-1">
        <li v-for="(name, role) in result.csv_evidence.columns" :key="role">
          {{ t(`billing.reconciliation.csv.columns.${role}`) }} ·
          {{ name ?? t('billing.reconciliation.csv.declared') }}
        </li>
      </ul>
      <p class="break-all">SHA-256 · {{ result.csv_evidence.sha256 }}</p>
      <p>{{ t('billing.reconciliation.csv.retention') }}</p>
    </details>
    <p>
      {{
        t('billing.reconciliation.snapshot', {
          revision: result.snapshot.revision,
          organization: result.snapshot.organization_id,
          project: result.snapshot.project_id,
        })
      }}
    </p>
    <p>
      {{
        t('billing.reconciliation.query', {
          start: utc(result.snapshot.start_time),
          end: utc(result.snapshot.end_time),
        })
      }}
    </p>
    <p>
      {{
        t('billing.reconciliation.sourceSaved', {
          time: formatDateTime(result.snapshot.finished_at ?? ''),
        })
      }}
    </p>
    <p class="break-all">{{ result.source_url }}</p>
    <p v-if="result.included_line_count !== null">
      {{ t('billing.reconciliation.count', { n: result.included_line_count }) }}
    </p>
    <p v-if="result.included_line_count === 0">{{ t('billing.reconciliation.empty') }}</p>
    <p>{{ t('billing.reconciliation.limitation') }}</p>
    <UiButton variant="ghost" :disabled="disabled" @click="$emit('evidence', result.snapshot.id)">{{
      t('billing.reconciliation.evidence')
    }}</UiButton>
  </div>
</template>
