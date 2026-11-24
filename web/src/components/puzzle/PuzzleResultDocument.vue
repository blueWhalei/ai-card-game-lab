<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  decisionPuzzleExtract,
  type PuzzleResult,
  type PuzzleRunReport,
  type PuzzleProbeReport,
} from '@/api/puzzleApi'
import { formatDateTime, formatPercentage } from '@/utils/format'
import { formatRolloutScope } from '@/utils/gameHighlights'
import '@/styles/research-report.css'
import BatchPuzzleSelection from './BatchPuzzleSelection.vue'

const props = withDefaults(
  defineProps<{
    result: PuzzleResult
    page: number
    localLinks?: boolean
    embedded?: boolean
    frozen?: boolean
    reportId?: string
    citation?: string
  }>(),
  { localLinks: true, embedded: false },
)
const { t } = useI18n()
const report = computed(() => props.result.report)
const run = computed(() =>
  report.value.run_id.startsWith('run_') ? (report.value as PuzzleRunReport) : null,
)
const probe = computed(() =>
  report.value.run_id.startsWith('probe_') ? (report.value as PuzzleProbeReport) : null,
)
const snapshot = computed(() => report.value.pack_snapshot)
const selected = computed(() => decisionPuzzleExtract(snapshot.value?.manifest ?? null))
const baseline = computed(() =>
  t(
    {
      heuristic: 'puzzle.baselineHeuristic',
      first: 'puzzle.baselineFirst',
      random: 'puzzle.baselineRandom',
    }[report.value.baseline_kind] ?? 'common.unknown',
  ),
)
const kinds = computed(() =>
  probe.value?.summary.kinds
    .map((kind) =>
      t(
        {
          shuffle_legal_actions: 'puzzle.perturbActions',
          shuffle_hand_cards: 'puzzle.perturbHand',
        }[kind] ?? 'puzzleHistory.otherKind',
        { kind },
      ),
    )
    .join(' + '),
)
const gap = (value: number | null) => (value === null ? '—' : value.toFixed(3))
const score = (hit: boolean | null) =>
  t(hit === null ? 'puzzle.unevaluated' : hit ? 'puzzle.hit' : 'puzzle.miss')
</script>

<template>
  <article class="space-y-ink-4" :class="{ 'research-report': !embedded }">
    <component :is="embedded ? 'h4' : 'h2'">{{ t('puzzleHistory.record') }}</component>
    <p>
      {{ t(run ? 'puzzleHistory.run' : 'puzzleHistory.probe') }} ·
      {{ formatDateTime(report.created_at) }}
    </p>
    <p class="text-caption">
      {{
        t('puzzleHistory.identity', {
          pack: report.pack_id,
          run: report.run_id,
          version: report.metric_version,
        })
      }}
    </p>
    <section>
      <component :is="embedded ? 'h5' : 'h3'">{{ t('puzzleHistory.conditions') }}</component>
      <p>{{ t('puzzle.testConditions', { baseline, seed: report.seed }) }}</p>
      <p>{{ t('puzzleHistory.positions', { n: report.summary.n }) }}</p>
      <p v-if="probe">
        {{
          t('puzzle.probeConditions', {
            trials: probe.summary.n_trials,
            n: probe.summary.comparisons_n,
            kinds,
          })
        }}
      </p>
      <p v-if="frozen">
        {{ t('puzzleCitation.verifiedAt', { at: formatDateTime(result.read_at) }) }}
      </p>
      <p v-else>{{ t('puzzleHistory.sourceStatus.' + result.source_status) }}</p>
      <p v-if="!frozen" class="text-caption">
        {{ t('puzzleHistory.checkedAt', { at: formatDateTime(result.read_at) }) }}
      </p>
      <template v-if="snapshot">
        <p>{{ t('puzzle.sourceExperiment') }}：{{ snapshot.manifest.source_experiment_id }}</p>
        <p v-if="selected">{{ t('puzzle.testQuestion') }}：{{ selected.question }}</p>
        <BatchPuzzleSelection :manifest="snapshot.manifest" :frozen="frozen" />
        <details>
          <summary>{{ t('puzzleHistory.selection') }}</summary>
          <pre class="overflow-x-auto text-caption">{{
            JSON.stringify(snapshot.manifest.extract, null, 2)
          }}</pre>
        </details>
      </template>
    </section>
    <section>
      <component :is="embedded ? 'h5' : 'h3'">{{ t('puzzleHistory.results') }}</component>
      <p v-if="run">
        {{
          t('puzzle.runSummary', {
            acc: formatPercentage(run.summary.accuracy),
            loss: gap(run.summary.mean_ev_loss),
            n: run.summary.n,
            evaluated: run.summary.evaluated_n,
            unknown: run.summary.unevaluated_n,
          })
        }}
      </p>
      <template v-if="probe">
        <p>
          {{
            t('puzzle.probeSummary', {
              cons: formatPercentage(probe.summary.consistency),
              repeat: formatPercentage(probe.summary.repeat_consistency),
              base: formatPercentage(probe.summary.base_accuracy),
              pert: formatPercentage(probe.summary.pert_accuracy),
              baseN: probe.summary.base_evaluated_n,
              pertN: probe.summary.pert_evaluated_n,
              total: probe.summary.comparisons_n,
            })
          }}
        </p>
        <p>
          {{
            t('puzzleHistory.probeGaps', {
              base: gap(probe.summary.base_mean_ev_loss),
              pert: gap(probe.summary.pert_mean_ev_loss),
              baseN: probe.summary.base_unevaluated_n,
              pertN: probe.summary.pert_unevaluated_n,
            })
          }}
        </p>
      </template>
      <p>{{ t('puzzle.scoreScope') }}</p>
      <p v-if="probe">{{ t('puzzle.probeScope') }}</p>
    </section>
    <section>
      <component :is="embedded ? 'h5' : 'h3'">{{ t('puzzleHistory.rows') }}</component>
      <p v-if="!report.summary.n">{{ t('puzzleHistory.noPositions') }}</p>
      <details v-for="(row, index) in report.puzzles" :key="row.puzzle_id" class="mb-ink-3">
        <summary>{{ index + 1 }} · {{ row.puzzle_id }}</summary>
        <template
          v-for="point in snapshot?.puzzles.filter((p) => p.puzzle_id === row.puzzle_id) ?? []"
          :key="point.puzzle_id"
        >
          <p class="text-caption">
            {{
              t('puzzleHistory.sourceIds', {
                game: point.source.game_id ?? '—',
                decision: point.source.decision_point_id ?? '—',
              })
            }}
          </p>
          <RouterLink
            v-if="localLinks && point.source.game_id && point.source.decision_point_id"
            data-report-local
            :to="{
              path: '/pipeline/decisions',
              query: {
                game_id: point.source.game_id,
                decision_id: point.source.decision_point_id,
                puzzle_pack: report.pack_id,
                puzzle_result: report.run_id,
                puzzle_page: String(page),
                ...(reportId ? { report_id: reportId, puzzle_evidence: citation } : {}),
              },
            }"
            >{{ t('puzzle.sourceDecision') }}</RouterLink
          >
          <p class="text-caption">
            {{
              t('puzzle.evaluatedActions', {
                n: point.candidates_evaluated,
                total: point.legal_action_count,
              })
            }}
            · {{ formatRolloutScope(point.evaluator_params, t) }}
          </p>
          <details>
            <summary>{{ t('puzzle.storedEvaluation') }}</summary>
            <pre class="overflow-x-auto text-caption">{{
              JSON.stringify(point.evaluator_params, null, 2)
            }}</pre>
          </details>
        </template>
        <p v-if="'hit' in row">
          {{ score(row.hit) }} · {{ row.chosen_action_id }} → {{ row.best_action_id }} ·
          {{ t('puzzle.payoffGap') }} {{ gap(row.ev_loss) }}
        </p>
        <template v-else>
          <p>{{ t('puzzleHistory.initialAction', { action: row.base_chosen_action_id }) }}</p>
          <div class="overflow-x-auto">
            <table>
              <thead>
                <tr>
                  <th>{{ t('puzzleHistory.trial') }}</th>
                  <th>{{ t('puzzleHistory.control') }}</th>
                  <th>{{ t('puzzleHistory.perturbed') }}</th>
                  <th>{{ t('puzzleHistory.agreement') }}</th>
                  <th>{{ t('puzzle.payoffGap') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="trial in row.trials" :key="trial.trial">
                  <td>{{ trial.trial + 1 }}</td>
                  <td>{{ trial.control_action_id }}</td>
                  <td>{{ trial.chosen_action_id }}</td>
                  <td>
                    {{ t(trial.consistent ? 'puzzleHistory.same' : 'puzzleHistory.different') }}
                  </td>
                  <td>{{ score(trial.hit) }} · {{ gap(trial.ev_loss) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
      </details>
    </section>
    <section>
      <component :is="embedded ? 'h5' : 'h3'">{{ t('puzzleHistory.limits') }}</component>
      <p>{{ t(frozen ? 'puzzleCitation.testLimits' : 'puzzleHistory.scope') }}</p>
    </section>
    <details class="text-caption">
      <summary>{{ t('puzzleHistory.fingerprints') }}</summary>
      <p>SHA-256 · {{ result.report_hash }}</p>
      <p v-if="report.pack_fingerprint">
        {{ t('puzzleHistory.packFingerprint') }} · {{ report.pack_fingerprint }}
      </p>
    </details>
  </article>
</template>
