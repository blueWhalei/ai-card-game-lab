import { describe, expect, it } from 'vitest'
import type { Experiment, ExperimentBenchmark } from '@/api/experimentApi'
import {
  remainingBenchmarkSeeds,
  remainingCollectGames,
  shouldShowBenchmarkReport,
} from './experimentBenchmark'

function makeBenchmark(overrides: Partial<ExperimentBenchmark> = {}): ExperimentBenchmark {
  return {
    seed_total: 50,
    seed_started: 10,
    seed_finished: 8,
    seed_failed: 0,
    seed_running: 2,
    seed_remaining: 40,
    extra_games: 0,
    complete: false,
    ...overrides,
  }
}

function makeExperiment(overrides: Partial<Experiment> = {}): Experiment {
  return {
    id: 'exp-1',
    name: 'run',
    notes: '',
    hypothesis: '',
    conclusion: '',
    tags: [],
    game_type: 'doudizhu',
    player_ids: ['a', 'b', 'c'],
    target_games: 50,
    created_at: '',
    updated_at: '',
    protocol: {
      schema_version: 2,
      frozen_at: '',
      dataset: {
        collect_mode: 'benchmark',
        deal_seeds: [1, 2, 3],
        pair_deals: false,
        source_experiment_id: null,
      },
      solver: { players: [], prompt_version: '' },
      scorer: { eval_metric_ids: [] },
      engine: {
        game_type: 'doudizhu',
        engine_version: '1',
        decision_schema_version: 2,
        rules_ref: null,
        phases: [],
        prompt_keys: {},
        roles: [],
        supports_deal_seed: true,
        benchmark_seed_count: 50,
      },
    },
    summary: {
      status: 'ready_more',
      target_games: 50,
      total_games: 8,
      active_games: 0,
      finished_games: 8,
      games_with_winner: 8,
      train_usable_decisions: 10,
      avg_rounds: 12,
      wins_by_config: {},
      player_stats: [],
      latest_game_id: 'g1',
    },
    benchmark: makeBenchmark(),
    ...overrides,
  }
}

describe('shouldShowBenchmarkReport', () => {
  it('shows after a benchmark run has finished games', () => {
    expect(shouldShowBenchmarkReport(makeExperiment())).toBe(true)
  })

  it('hides before any game finishes', () => {
    const experiment = makeExperiment({
      summary: {
        ...makeExperiment().summary,
        finished_games: 0,
        total_games: 0,
        status: 'pending_collect',
      },
      benchmark: makeBenchmark({ seed_started: 0, seed_finished: 0, seed_remaining: 50 }),
    })
    expect(shouldShowBenchmarkReport(experiment)).toBe(false)
  })

  it('hides free-collect experiments', () => {
    const experiment = makeExperiment({
      protocol: {
        ...makeExperiment().protocol!,
        dataset: { ...makeExperiment().protocol!.dataset, collect_mode: 'free' },
      },
      benchmark: null,
    })
    expect(shouldShowBenchmarkReport(experiment)).toBe(false)
  })
})

describe('remainingBenchmarkSeeds and remainingCollectGames', () => {
  it('uses seed_remaining for benchmark collect', () => {
    const experiment = makeExperiment({
      benchmark: makeBenchmark({ seed_remaining: 3 }),
    })
    expect(remainingBenchmarkSeeds(experiment)).toBe(3)
    expect(remainingCollectGames(experiment)).toBe(3)
  })

  it('is zero once the declared seeds are used', () => {
    const experiment = makeExperiment({
      benchmark: makeBenchmark({ seed_remaining: 0, complete: true }),
    })
    expect(remainingCollectGames(experiment)).toBe(0)
  })

  it('keeps the free-collect clamp when there is no benchmark payload', () => {
    const experiment = makeExperiment({
      protocol: {
        ...makeExperiment().protocol!,
        dataset: { ...makeExperiment().protocol!.dataset, collect_mode: 'free' },
      },
      benchmark: null,
      summary: { ...makeExperiment().summary, target_games: 10, finished_games: 3 },
    })
    expect(remainingCollectGames(experiment)).toBe(7)
  })
})
