<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Trace } from '@/api/traces'
import { traceLatency, traceParserStatus } from '@/utils/traceMetrics'
import MoveExplainStrip from '@/components/common/MoveExplainStrip.vue'
import UiBadge from '@/components/ui/Badge.vue'
import EvidenceCitationEntry from '@/components/experiment/EvidenceCitationEntry.vue'
import { actionTypeLabel, parseTraceDecision } from '@/utils/traceOutput'

const props = defineProps<{
  trace: Trace
}>()

const { t } = useI18n()
const showRaw = ref(false)
const showSpans = ref(false)

const decision = computed(() => parseTraceDecision(props.trace.output_data))
const actionLabel = computed(() => actionTypeLabel(decision.value.actionType))
const parserOk = computed(() => traceParserStatus(props.trace.metrics.parser_ok))
const latency = computed(() => traceLatency(props.trace.metrics.response_time_ms))
watch(
  () => props.trace.id,
  () => {
    showRaw.value = false
    showSpans.value = false
  },
)
const snapshot = computed(() =>
  props.trace.input_snapshot && typeof props.trace.input_snapshot === 'object'
    ? props.trace.input_snapshot
    : {},
)
const legalActions = computed(() => snapshot.value.legal_actions)
const handAnalysis = computed(
  () =>
    snapshot.value.hand_analysis ??
    props.trace.spans?.find((span) => span.data?.hand_analysis)?.data?.hand_analysis,
)

function formatJson(data: unknown): string {
  return JSON.stringify(data, null, 2)
}
</script>

<template>
  <div class="ink-card">
    <div class="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div class="min-w-0">
        <div class="flex flex-wrap items-center gap-2">
          <span class="text-lead font-semibold text-ink-text">{{ actionLabel }}</span>
          <UiBadge v-if="decision.actionType !== actionLabel" variant="muted">
            {{ decision.actionType }}
          </UiBadge>
          <UiBadge :variant="parserOk === null ? 'muted' : parserOk ? 'success' : 'warning'">
            {{
              parserOk === null
                ? t('trace.parserUnknown')
                : parserOk
                  ? t('filter.parseOk')
                  : t('trace.parseFailed')
            }}
          </UiBadge>
        </div>
        <p v-if="decision.cards.length" class="mt-2 font-mono text-body text-ink-text-secondary">
          {{ decision.cards.join(' ') }}
        </p>
        <p v-if="decision.target" class="mt-1 text-caption text-ink-text-muted">
          {{ t('trace.target', { id: decision.target }) }}
        </p>
      </div>
      <div class="text-right text-caption text-ink-text-muted">
        <div>R{{ trace.round_number }} · {{ trace.player_id }}</div>
        <div class="mt-1">
          {{ latency === null ? t('trace.notRecorded') : `${latency} ms` }} · {{ trace.model }}
        </div>
      </div>
    </div>

    <p class="mb-ink-2 text-caption text-ink-text-muted">{{ t('trace.outputScope') }}</p>
    <p
      v-if="decision.thinking"
      class="mb-5 max-h-36 overflow-y-auto text-body leading-relaxed text-ink-text-secondary"
    >
      {{ decision.thinking }}
    </p>
    <p v-else class="mb-5 text-body text-ink-text-muted">{{ t('trace.noThinking') }}</p>

    <MoveExplainStrip
      class="mb-5"
      :legal-actions="legalActions"
      :chosen="{ action_type: decision.actionType, cards: decision.cards }"
      :hand-analysis="handAnalysis"
    />

    <div class="flex flex-wrap items-center gap-2">
      <UiBadge variant="muted">{{ trace.prompt_version }}</UiBadge>
      <UiBadge variant="muted" class="font-mono font-normal">{{ trace.id }}</UiBadge>
    </div>

    <div class="mt-ink-4"><EvidenceCitationEntry :source="{ kind: 'trace', id: trace.id }" /></div>
    <div class="mt-5 border-t border-ink-border pt-3">
      <button
        type="button"
        class="text-body text-ink-text-secondary hover:text-ink-text"
        @click="showRaw = !showRaw"
      >
        {{ showRaw ? t('trace.hideRaw') : t('trace.showRaw') }}
      </button>
      <div v-if="showRaw" class="mt-3 space-y-3">
        <div>
          <p class="mb-1 text-caption text-ink-text-muted">{{ t('trace.input') }}</p>
          <pre
            class="max-h-48 overflow-auto rounded-ink bg-ink-surface-muted p-3 text-caption text-ink-text-secondary"
            >{{ formatJson(trace.input_snapshot) }}</pre
          >
        </div>
        <div>
          <p class="mb-1 text-caption text-ink-text-muted">{{ t('trace.output') }}</p>
          <pre
            class="max-h-48 overflow-auto rounded-ink bg-ink-surface-muted p-3 text-caption text-ink-text-secondary"
            >{{ formatJson(trace.output_data) }}</pre
          >
        </div>
      </div>
    </div>

    <div v-if="trace.spans && trace.spans.length > 0" class="mt-4 border-t border-ink-border pt-3">
      <button
        type="button"
        class="text-body text-ink-text-secondary hover:text-ink-text"
        @click="showSpans = !showSpans"
      >
        {{ t('trace.spans', { n: trace.spans.length }) }}{{ showSpans ? t('trace.spansHide') : '' }}
      </button>
      <div v-if="showSpans" class="mt-2 space-y-2">
        <div
          v-for="span in trace.spans"
          :key="span.id"
          class="rounded-ink-md bg-ink-surface-muted px-3 py-2"
        >
          <div class="flex items-center justify-between gap-2">
            <span class="text-body text-ink-text">{{ span.span_type }}</span>
            <UiBadge :variant="span.status === 'completed' ? 'success' : 'warning'">
              {{ span.status }}
            </UiBadge>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
