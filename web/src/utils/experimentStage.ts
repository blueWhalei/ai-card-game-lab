import type {
  Experiment,
  ExperimentDelta,
  ExperimentVerdictKey,
} from '@/api/experimentApi'

/**
 * The five phases of the experiment workbench. Each one answers a single
 * question and offers a single next step, so the detail page renders one
 * phase at a time instead of stacking every strip and hiding parts with `v-if`.
 */
export type ExperimentStageId = 'empty' | 'collecting' | 'harvest' | 'control' | 'verdict'

/** Semantic actions a phase can ask the page to perform. */
export type ExperimentStageAction =
  | 'collect'
  | 'watch'
  | 'review-decisions'
  | 'train'
  | 'register-player'
  | 'open-control'
  | 'collect-control'
  | 'compare'
  | 'settings'
  | 'cancel-collect'

export function resolveStageId(experiment: Experiment): ExperimentStageId {
  const status = experiment.summary.status
  if (status === 'pending_collect') return 'empty'
  if (status === 'collecting') return 'collecting'
  if (experiment.delta) return 'verdict'
  if (experiment.next_step?.id === 'open_control') return 'control'
  return 'harvest'
}

/**
 * Games still to run before the target is met. Collecting past the target is
 * allowed, so this can be zero while the experiment stays usable.
 */
export function remainingGames(experiment: Experiment): number {
  const { target_games: target, finished_games: finished } = experiment.summary
  return Math.max(0, target - finished)
}

/** Cap the finished count for display so progress never reads as 14/10. */
export type ExperimentProgressParts = {
  finished: number
  target: number
  shownFinished: number
  extra: number
}

export function experimentProgressParts(
  finished: number,
  target: number,
): ExperimentProgressParts {
  const safeFinished = Math.max(0, Math.floor(finished))
  const safeTarget = Math.max(0, Math.floor(target))
  const shownFinished = safeTarget > 0 ? Math.min(safeFinished, safeTarget) : safeFinished
  const extra = safeTarget > 0 ? Math.max(0, safeFinished - safeTarget) : 0
  return {
    finished: safeFinished,
    target: safeTarget,
    shownFinished,
    extra,
  }
}

/**
 * Human progress label. Never shows finished > target in the ratio.
 * Extra games past the target are named separately.
 */
export function formatExperimentProgress(
  finished: number,
  target: number,
  t: (key: string, params?: Record<string, unknown>) => string,
): string {
  const { shownFinished, target: safeTarget, extra } = experimentProgressParts(
    finished,
    target,
  )
  const ratio = t('stage.progressRatio', {
    finished: shownFinished,
    target: safeTarget,
  })
  if (extra <= 0) return ratio
  return t('stage.progressWithExtra', { ratio, extra })
}

export function verdictKeyOf(experiment: Experiment): ExperimentVerdictKey {
  const delta = experiment.delta
  if (!delta) return 'no_data'
  if (delta.verdict_key) return delta.verdict_key
  // Older payloads predate `verdict_key`; derive the same claim client-side.
  if (delta.inconclusive_reason === 'no_games') return 'no_data'
  if (delta.inconclusive_reason === 'peer_not_ready') return 'peer_pending'
  const diff = delta.landlord_win_rate_diff
  if (diff == null) return 'no_data'
  if (Math.abs(diff) < 0.02) return 'even'
  return diff > 0 ? 'stronger' : 'weaker'
}

/**
 * Headline for the verdict phase. Weak evidence must not use a causal claim
 * as the main sentence — `verdict_key` stays directional for matrices, but the
 * UI headline switches to the evidence line until `can_conclude`.
 */
export type VerdictHeadline = {
  /** i18n key under `stage.*` */
  key: string
  params?: Record<string, number>
  /** True when the headline is an evidence sentence, not a causal verdict. */
  isEvidence: boolean
}

export function verdictHeadlineOf(
  delta: ExperimentDelta,
  gamesNeeded = 0,
): VerdictHeadline {
  if (delta.can_conclude) {
    const key = delta.verdict_key ?? 'no_data'
    return { key: `verdict.${key}`, isEvidence: false }
  }
  const reason = delta.inconclusive_reason
  if (reason === 'peer_not_ready') {
    return { key: 'evidence.peerPending', isEvidence: true }
  }
  if (reason === 'low_power') {
    if (gamesNeeded > 0) {
      return {
        key: 'evidence.lowPowerNeed',
        params: { n: delta.paired_n, need: gamesNeeded },
        isEvidence: true,
      }
    }
    return {
      key: 'evidence.lowPower',
      params: { n: delta.paired_n },
      isEvidence: true,
    }
  }
  return { key: 'evidence.noData', isEvidence: true }
}

/**
 * Roughly how many more decisive games would lift the pair out of low power.
 * Used to turn "not enough evidence" into an actionable number.
 */
export function gamesNeededForPower(experiment: Experiment, minDecisive = 20): number {
  const delta = experiment.delta
  if (!delta) return minDecisive
  const decisive = Math.min(delta.this_decisive_n, delta.peer_decisive_n)
  return Math.max(0, minDecisive - decisive)
}
