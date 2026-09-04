import { describe, expect, it } from 'vitest'
import type { Experiment, ExperimentDelta } from '@/api/experimentApi'
import {
  gamesNeededForPower,
  remainingGames,
  resolveStageId,
  verdictKeyOf,
} from '@/utils/experimentStage'

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
    target_games: 10,
    created_at: '',
    updated_at: '',
    summary: {
      status: 'ready_review',
      target_games: 10,
      total_games: 10,
      active_games: 0,
      finished_games: 10,
      games_with_winner: 10,
      train_usable_decisions: 100,
      avg_rounds: 12,
      wins_by_config: {},
      player_stats: [],
      latest_game_id: 'g1',
      ...overrides.summary,
    },
    ...overrides,
  } as Experiment
}

function makeDelta(overrides: Partial<ExperimentDelta> = {}): ExperimentDelta {
  return {
    peer_id: 'exp-2',
    peer_name: 'control',
    relation: 'vs_control',
    peer_ready: true,
    this_landlord_win_rate: 0.6,
    peer_landlord_win_rate: 0.4,
    landlord_win_rate_diff: 0.2,
    this_landlord_win_rate_ci: null,
    peer_landlord_win_rate_ci: null,
    this_decisive_n: 40,
    peer_decisive_n: 40,
    paired_n: 40,
    paired_landlord_win_rate_diff: 0.2,
    low_power: false,
    can_conclude: true,
    inconclusive_reason: null,
    ...overrides,
  }
}

describe('resolveStageId', () => {
  it('shows the empty phase before any game runs', () => {
    const experiment = makeExperiment({ summary: { status: 'pending_collect' } as never })
    expect(resolveStageId(experiment)).toBe('empty')
  })

  it('prefers the collecting phase while games are running, even for a control run', () => {
    const experiment = makeExperiment({
      summary: { status: 'collecting' } as never,
      delta: makeDelta({ relation: 'vs_source' }),
    })
    expect(resolveStageId(experiment)).toBe('collecting')
  })

  it('shows the verdict phase once there is something to compare against', () => {
    expect(resolveStageId(makeExperiment({ delta: makeDelta() }))).toBe('verdict')
  })

  it('asks for a control run after training completes', () => {
    const experiment = makeExperiment({
      next_step: { id: 'open_control', action: 'control' },
    })
    expect(resolveStageId(experiment)).toBe('control')
  })

  it('falls back to the harvest phase', () => {
    expect(resolveStageId(makeExperiment())).toBe('harvest')
  })
})

describe('verdictKeyOf', () => {
  it('uses the key the backend sent', () => {
    const experiment = makeExperiment({ delta: makeDelta({ verdict_key: 'weaker' }) })
    expect(verdictKeyOf(experiment)).toBe('weaker')
  })

  it('derives the same claim for payloads that predate verdict_key', () => {
    expect(verdictKeyOf(makeExperiment({ delta: makeDelta() }))).toBe('stronger')
    expect(
      verdictKeyOf(makeExperiment({ delta: makeDelta({ landlord_win_rate_diff: -0.2 }) })),
    ).toBe('weaker')
    expect(
      verdictKeyOf(makeExperiment({ delta: makeDelta({ landlord_win_rate_diff: 0.005 }) })),
    ).toBe('even')
    expect(
      verdictKeyOf(
        makeExperiment({ delta: makeDelta({ inconclusive_reason: 'peer_not_ready' }) }),
      ),
    ).toBe('peer_pending')
  })

  it('reports no data without a delta', () => {
    expect(verdictKeyOf(makeExperiment())).toBe('no_data')
  })
})

describe('remainingGames and gamesNeededForPower', () => {
  it('never goes negative when collection overshoots the target', () => {
    const experiment = makeExperiment({
      summary: { target_games: 10, finished_games: 14 } as never,
    })
    expect(remainingGames(experiment)).toBe(0)
  })

  it('reports how many decisive games are still missing', () => {
    const experiment = makeExperiment({
      delta: makeDelta({ this_decisive_n: 6, peer_decisive_n: 12 }),
    })
    expect(gamesNeededForPower(experiment)).toBe(14)
  })

  it('reports nothing missing once both sides are powered', () => {
    expect(gamesNeededForPower(makeExperiment({ delta: makeDelta() }))).toBe(0)
  })
})
