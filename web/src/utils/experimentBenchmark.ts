import type { Experiment } from '@/api/experimentApi'
import { isBenchmarkExperiment } from '@/api/experimentApi'
import { remainingCollectCount } from '@/utils/experimentWorkbench'

/** Quiet report: only for benchmark runs that already have a finished game. */
export function shouldShowBenchmarkReport(experiment: Experiment): boolean {
  return (
    isBenchmarkExperiment(experiment) &&
    experiment.benchmark != null &&
    (experiment.summary.finished_games ?? 0) > 0
  )
}

export function remainingBenchmarkSeeds(experiment: Experiment): number {
  return Math.max(0, experiment.benchmark?.seed_remaining ?? 0)
}

/**
 * How many games the collect dialog may still start.
 * Benchmark runs stop at the declared seed set; free runs keep the existing clamp.
 */
export function remainingCollectGames(experiment: Experiment): number {
  if (isBenchmarkExperiment(experiment) && experiment.benchmark) {
    return remainingBenchmarkSeeds(experiment)
  }
  return remainingCollectCount(
    experiment.summary.target_games,
    experiment.summary.finished_games,
  )
}
