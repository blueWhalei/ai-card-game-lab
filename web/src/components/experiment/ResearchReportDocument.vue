<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type { EvidenceCandidate, ResearchReport } from '@/api/researchApi'
import { evidenceOrigin, reportComparisonLink, reportDecisionLink } from '@/utils/researchReport'
import { metricLabel } from '@/utils/researchOutcome'
import { policyLabels } from '@/utils/playerPolicy'
import { displayCard } from '@/utils/card'
import '@/styles/research-report.css'
import ResearchPuzzleEvidence from './ResearchPuzzleEvidence.vue'
import ResearchTraceEvidence from './ResearchTraceEvidence.vue'

const props = defineProps<{ report: ResearchReport }>()
const emit = defineEmits<{
  locate: [id: string]
  locatePuzzle: [id: string]
  locateTrace: [id: string]
}>()
const { t, te } = useI18n()
const result = computed(() => props.report.comparison.result)
const runs = computed(() => result.value.experiments)
const coverage = computed(() => result.value.coverage)
const paired = computed(() => result.value.paired_summary)
const supported = computed(
  () =>
    result.value.metric_version === 'paired-cohort-v5' &&
    (!paired.value || paired.value.ci_method === 'clopper_pearson_bonferroni'),
)
const validPairs = computed(
  () =>
    supported.value &&
    runs.value.length === 2 &&
    (paired.value?.shared_seeds ?? 0) > 0 &&
    paired.value?.win_rate_diff != null,
)
const sections = ['question', 'conditions', 'sample', 'author', 'evidence', 'limits'] as const
const cells = ['both_won', 'a_only_won', 'b_only_won', 'both_lost'] as const
const evaluationFields = {
  candidates: 'candidates_evaluated',
  legalCount: 'legal_action_count',
  worlds: 'determinizations',
  rollouts: 'rollouts_per_world',
  opponent: 'opponent_kind_effective',
  selfProxy: 'self_proxy',
  steps: 'max_steps',
  randomSeed: 'seed',
}
function text(value: unknown): string {
  if (value == null || value === '') return t('report.missing')
  return typeof value === 'object' ? JSON.stringify(value) : String(value)
}
function fields(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
}
function pp(value: unknown) {
  return typeof value === 'number' && Number.isFinite(value)
    ? `${(value * 100).toFixed(1)}`
    : t('report.missing')
}
function pValue(value: unknown) {
  return typeof value === 'number' && Number.isFinite(value)
    ? value < 0.001
      ? '< 0.001'
      : value.toFixed(3)
    : t('report.missing')
}
function name(id: string | undefined) {
  return runs.value.find((run) => run.id === id)?.name ?? text(id)
}
function hypothesis(run: (typeof runs.value)[number]) {
  return run.protocol?.design?.hypothesis || run.hypothesis
}
function source(decision: EvidenceCandidate) {
  const origin = evidenceOrigin(props.report, decision)
  return origin
    ? `${name(origin.experimentId)} · ${t('report.seed')} ${origin.seed}`
    : t('report.missing')
}
function playerName(decision: EvidenceCandidate, id: string) {
  const origin = evidenceOrigin(props.report, decision)
  return (
    runs.value
      .find((run) => run.id === origin?.experimentId)
      ?.protocol?.solver?.players.find((player) => player.id === id)?.name ?? id
  )
}
function cards(value: unknown) {
  return Array.isArray(value) && value.every((card) => typeof card === 'string')
    ? value.map(displayCard).join(' ')
    : text(value)
}
function action(value: unknown) {
  const record = fields(value)
  const key = `action.${record.action_type}`
  return record.action_type
    ? `${te(key) ? t(key) : text(record.action_type)} ${cards(record.cards)}`.trim()
    : text(value)
}
function status(decision: EvidenceCandidate) {
  const value = props.report.evidence_status[decision.id]
  return value ? t(`researchReport.status.${value}`) : t('report.unknownStatus')
}
function canInspect(decision: EvidenceCandidate) {
  return ['available', 'changed'].includes(props.report.evidence_status[decision.id] ?? '')
}
function reason(key: string) {
  const path = `compare.audit.exclusions.${key}`
  return te(path) ? t(path) : key
}
</script>

<template>
  <article class="research-report" aria-labelledby="report-heading">
    <header>
      <p class="report-muted">CardLab · {{ t('report.title') }}</p>
      <h1 id="report-heading">{{ report.comparison.title }} · v{{ report.record.revision }}</h1>
      <p>{{ t('report.basis') }}</p>
      <dl class="report-muted">
        <dt>{{ t('report.version') }}</dt>
        <dd>{{ report.record.id }}</dd>
        <dt>{{ t('report.cutoff') }}</dt>
        <dd>{{ text(result.computed_at) }}</dd>
        <dt>{{ t('report.published') }}</dt>
        <dd>{{ report.record.created_at }}</dd>
        <dt>{{ t('report.checked') }}</dt>
        <dd>{{ report.exported_at }}</dd>
        <dt>{{ t('report.metricVersion') }}</dt>
        <dd>{{ text(result.metric_version) }}</dd>
        <dt>{{ t('report.source') }}</dt>
        <dd>{{ report.record.comparison_id }}</dd>
      </dl>
    </header>
    <div class="report-grid">
      <nav class="report-nav" :aria-label="t('report.title')">
        <a v-for="section in sections" :key="section" :href="`#report-${section}`">{{
          t(`report.${section}`)
        }}</a>
        <a
          v-for="(item, index) in report.record.evidence"
          :key="item.decision.id"
          :href="`#report-evidence-${index + 1}`"
          @click="emit('locate', item.decision.id)"
          >{{ t('report.citation', { n: index + 1 }) }}</a
        >
        <a
          v-for="(item, index) in report.record.puzzle_evidence ?? []"
          :key="`${item.result.report.pack_id}/${item.result.report.run_id}`"
          :href="`#report-test-${index + 1}`"
          @click="
            emit('locatePuzzle', `${item.result.report.pack_id}/${item.result.report.run_id}`)
          "
          >{{ t('puzzleCitation.citation', { n: index + 1 }) }}</a
        >
        <a
          v-for="(item, index) in report.record.trace_evidence ?? []"
          :key="item.trace.id"
          :href="`#report-trace-${index + 1}`"
          @click="emit('locateTrace', item.trace.id)"
          >{{ t('traceCitation.citation', { n: index + 1 }) }}</a
        >
      </nav>
      <div class="report-body">
        <section id="report-question">
          <h2>{{ t('report.question') }}</h2>
          <template v-if="runs.length">
            <div v-for="run in runs" :key="run.id">
              <h3>{{ run.name }}</h3>
              <p>{{ hypothesis(run) || t('report.noQuestion') }}</p>
            </div>
          </template>
          <p v-else>{{ t('report.noQuestion') }}</p>
          <p class="report-muted">{{ t('report.questionScope') }}</p>
        </section>
        <section id="report-conditions">
          <h2>{{ t('report.conditions') }}</h2>
          <article v-for="run in runs" :key="run.id">
            <h3>{{ run.name }}</h3>
            <p v-if="run.protocol?.design?.source_revision_id">
              {{ t('promptDesign.sourceConclusion') }}: {{ run.protocol.design.source_revision_id }}
              <RouterLink
                :to="{
                  name: 'research-report',
                  params: { id: run.protocol.design.source_revision_id },
                }"
                data-report-local
                >{{ t('report.open') }}</RouterLink
              >
            </p>
            <dl>
              <dt>{{ t('report.run') }}</dt>
              <dd>{{ run.id }}</dd>
              <dt>{{ t('report.engine') }}</dt>
              <dd>{{ text(run.game_type) }} · {{ text(run.protocol?.engine?.engine_version) }}</dd>
            </dl>
            <div class="report-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>{{ t('report.player') }}</th>
                    <th>{{ t('report.policy') }}</th>
                    <th>{{ t('report.sampling') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="(player, index) in run.protocol?.solver?.players ?? []"
                    :key="player.id"
                  >
                    <th scope="row">
                      #{{ index + 1 }} {{ player.name }}
                      <p class="report-muted">{{ player.id }}</p>
                    </th>
                    <td>
                      {{
                        player.policy_kind
                          ? t(policyLabels[player.policy_kind])
                          : t('report.missing')
                      }}
                      <p>
                        {{ text(player.model_config?.provider) }} ·
                        {{ text(player.model_config?.model_name) }}
                      </p>
                    </td>
                    <td>
                      <p v-for="key in ['temperature', 'top_p', 'max_tokens'] as const" :key="key">
                        {{ key }} = {{ text(player.model_config?.[key]) }}
                      </p>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <details>
              <summary>{{ t('report.prompts') }}</summary>
              <div v-for="(prompt, key) in run.protocol?.solver?.prompts ?? {}" :key="key">
                <h4>{{ key }} · {{ text(prompt.version) }}</h4>
                <p class="report-muted">SHA-256: {{ text(prompt.content_hash) }}</p>
                <pre>{{ text(prompt.content) }}</pre>
              </div>
            </details>
          </article>
          <p>
            {{
              t(
                result.protocol_review?.controlled
                  ? 'compare.audit.controlled'
                  : 'compare.audit.descriptive',
              )
            }}
          </p>
          <ul>
            <li v-for="item in result.protocol_review?.reasons ?? []" :key="item">
              {{ te(`compare.audit.reasons.${item}`) ? t(`compare.audit.reasons.${item}`) : item }}
            </li>
          </ul>
          <p class="report-muted">{{ t('report.controlledScope') }}</p>
          <details>
            <summary>{{ t('report.protocol') }}</summary>
            <pre>{{ text(result.protocol_review) }}</pre>
            <div v-for="run in runs" :key="run.id">
              <h4>{{ run.name }}</h4>
              <pre>{{ text(run.protocol) }}</pre>
            </div>
          </details>
        </section>
        <section id="report-sample">
          <h2>{{ t('report.sample') }}</h2>
          <p v-if="!supported">{{ t('report.unsupported') }}</p>
          <template v-else>
            <p>{{ t('report.unit') }}</p>
            <dl>
              <dt>{{ t('report.purpose') }}</dt>
              <dd>
                {{
                  coverage?.deal_purpose
                    ? t(`focus.purpose.${coverage.deal_purpose}`)
                    : t('report.missing')
                }}
              </dd>
              <dt>{{ t('report.planned') }}</dt>
              <dd>{{ text(coverage?.planned_shared) }}</dd>
              <dt>{{ t('report.pairedN') }}</dt>
              <dd>{{ text(paired?.shared_seeds) }}</dd>
              <dt>{{ t('report.excluded') }}</dt>
              <dd>{{ text(coverage?.excluded_n) }}</dd>
            </dl>
            <template v-if="validPairs && paired">
              <dl>
                <dt>{{ t('report.metric') }}</dt>
                <dd>
                  {{
                    metricLabel(
                      t,
                      paired.primary_metric,
                      runs.find((run) => run.id === paired?.control_id)?.protocol?.solver?.players,
                    )
                  }}
                </dd>
                <dt>{{ t('report.direction') }}</dt>
                <dd>B ({{ name(paired.control_id) }}) − A ({{ name(paired.source_id) }})</dd>
                <dt>{{ t('report.difference') }}</dt>
                <dd>{{ pp(paired.win_rate_diff) }}</dd>
                <dt>{{ t('report.interval') }}</dt>
                <dd>
                  {{
                    paired.paired_ci
                      ? `[${pp(paired.paired_ci[0])}, ${pp(paired.paired_ci[1])}]`
                      : t('report.missing')
                  }}
                </dd>
                <dt>{{ t('report.pValue') }}</dt>
                <dd>{{ pValue(paired.paired_p) }}</dd>
              </dl>
              <div class="report-table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th v-for="cell in cells" :key="cell">{{ t(`focus.outcomes.${cell}`) }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td v-for="cell in cells" :key="cell">
                        {{ text(paired.outcome_counts?.[cell]) }}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p class="report-muted">{{ t('report.method') }}</p>
              <p class="report-muted">{{ t('report.ciScope') }}</p>
              <details>
                <summary>{{ t('report.methodTitle') }}</summary>
                <p>{{ t('report.methodDetail') }}</p>
              </details>
              <p v-if="paired.low_power">{{ t('focus.lowPower') }}</p>
            </template>
            <p v-else>{{ t('report.noPairs') }}</p>
          </template>
          <details>
            <summary>{{ t('report.exclusionDetail') }}</summary>
            <div v-for="run in coverage?.experiments ?? []" :key="run.experiment_id">
              <h4>{{ name(run.experiment_id) }}</h4>
              <dl>
                <dt>{{ t('report.notShared') }}</dt>
                <dd>{{ text(run.not_shared) }}</dd>
                <dt>{{ t('report.missingSeed') }}</dt>
                <dd>{{ text(run.missing_seed_games) }}</dd>
                <dt>{{ t('report.unplanned') }}</dt>
                <dd>{{ text(run.unplanned_games) }}</dd>
              </dl>
            </div>
            <div class="report-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>{{ t('report.seed') }}</th>
                    <th>{{ t('report.reason') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="pair in coverage?.excluded_pairs ?? []" :key="pair.seed">
                    <th scope="row">{{ pair.seed }}</th>
                    <td>
                      <p v-for="(why, id) in pair.reasons" :key="id">
                        {{ name(String(id)) }}: {{ reason(why) }}
                      </p>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <h3>{{ t('report.membership') }}</h3>
            <ul>
              <li v-for="member in coverage?.members ?? []" :key="member.seed">
                {{ t('report.seed') }} {{ member.seed }}
                <p v-for="(gid, id) in member.game_ids" :key="id">
                  {{ name(String(id)) }}: {{ gid }}
                </p>
              </li>
            </ul>
          </details>
        </section>
        <section id="report-author">
          <h2>{{ t('report.author') }}</h2>
          <p class="report-muted">{{ t('report.authorScope') }}</p>
          <template
            v-for="field in ['observations', 'interpretation', 'limitations'] as const"
            :key="field"
          >
            <h3>{{ t(`researchReport.${field}`) }}</h3>
            <p>{{ text(report.record[field]) }}</p>
          </template>
        </section>
        <section id="report-evidence">
          <h2>{{ t('report.evidence') }}</h2>
          <p>{{ t('report.evidenceScope', { n: report.record.evidence.length }) }}</p>
          <p v-if="!report.record.evidence.length">{{ t('researchReport.noEvidence') }}</p>
          <article
            v-for="(item, index) in report.record.evidence"
            :id="`report-evidence-${index + 1}`"
            :key="item.decision.id"
            class="report-evidence"
            tabindex="-1"
          >
            <h3>{{ t('report.citation', { n: index + 1 }) }} · {{ source(item.decision) }}</h3>
            <p>{{ status(item.decision) }}</p>
            <p class="report-muted" data-report-local>{{ t('report.currentScope') }}</p>
            <div class="report-actions" data-report-local>
              <RouterLink
                v-if="canInspect(item.decision)"
                :to="reportDecisionLink(report, item.decision)"
                >{{ t('report.current') }}</RouterLink
              >
              <RouterLink
                v-if="evidenceOrigin(report, item.decision)"
                :to="reportComparisonLink(report, item.decision)"
                >{{ t('report.comparison') }}</RouterLink
              >
            </div>
            <dl>
              <dt>{{ t('focus.decisionId') }}</dt>
              <dd>{{ item.decision.id }}</dd>
              <dt>{{ t('focus.gameId') }}</dt>
              <dd>{{ item.decision.game_id }}</dd>
              <dt>{{ t('report.player') }}</dt>
              <dd>
                {{ playerName(item.decision, item.decision.player_id) }} ·
                {{ item.decision.player_id }}
              </dd>
              <dt>{{ t('report.turn') }}</dt>
              <dd>{{ item.decision.round_number }}</dd>
              <dt>{{ t('report.note') }}</dt>
              <dd>{{ text(item.note) }}</dd>
            </dl>
            <h4>{{ t('report.state') }}</h4>
            <dl>
              <dt>{{ t('report.hand') }}</dt>
              <dd>{{ cards(item.decision.hand_cards) }}</dd>
              <dt>{{ t('report.opponents') }}</dt>
              <dd v-if="Object.keys(fields(item.decision.opponent_hands)).length">
                <p v-for="(count, id) in fields(item.decision.opponent_hands)" :key="id">
                  {{ playerName(item.decision, String(id)) }}: {{ text(count) }}
                </p>
              </dd>
              <dd v-else>{{ t('report.missing') }}</dd>
              <dt>{{ t('report.lastAction') }}</dt>
              <dd>{{ action(item.decision.last_action) }}</dd>
              <dt>{{ t('report.action') }}</dt>
              <dd>
                {{ action(item.decision.chosen_action) }} · {{ text(item.decision.action_id) }}
              </dd>
              <dt>{{ t('report.outcome') }}</dt>
              <dd>
                {{
                  item.decision.outcome === 'win' || item.decision.outcome === 'lose'
                    ? t(`filter.${item.decision.outcome}`)
                    : text(item.decision.outcome)
                }}
              </dd>
              <dt>{{ t('report.gap') }}</dt>
              <dd>{{ text(item.decision.ev_loss) }}</dd>
            </dl>
            <p class="report-muted">{{ t('report.stateScope') }}</p>
            <details>
              <summary>{{ t('report.legal') }}</summary>
              <pre>{{ text(item.decision.legal_actions) }}</pre>
            </details>
            <h4>{{ t('report.evaluation') }}</h4>
            <dl>
              <template v-for="(key, label) in evaluationFields" :key="key"
                ><dt>{{ t(`report.${label}`) }}</dt>
                <dd>{{ text(fields(item.decision.evaluator_params)[key]) }}</dd></template
              >
            </dl>
            <p class="report-muted">{{ t('report.evalScope') }}</p>
          </article>
        </section>
        <ResearchPuzzleEvidence :report="report" />
        <ResearchTraceEvidence :report="report" />
        <section id="report-limits">
          <h2>{{ t('report.limits') }}</h2>
          <ul>
            <li>{{ t('report.exploration') }}</li>
            <li>{{ t('report.holdout') }}</li>
            <li>{{ t('report.multiplicity') }}</li>
            <li>{{ t('report.reproduction') }}</li>
          </ul>
        </section>
      </div>
    </div>
  </article>
</template>
