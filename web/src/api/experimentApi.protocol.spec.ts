import { describe, expect, it } from 'vitest'
import {
  flattenProtocol,
  isBenchmarkExperiment,
  type ExperimentProtocolNested,
} from '@/api/experimentApi'

describe('flattenProtocol', () => {
  it('flattens nested schema_version 2 protocol', () => {
    const protocol: ExperimentProtocolNested = {
      schema_version: 2,
      frozen_at: 't0',
      dataset: {
        collect_mode: 'benchmark',
        deal_seeds: [1, 2],
        pair_deals: false,
        source_experiment_id: null,
      },
      solver: {
        players: [
          { id: 'a', name: 'A', notes: '', model_config: { provider: 'ollama', model_name: 'm' } },
        ],
        prompt_version: 'v3',
      },
      scorer: { eval_metric_ids: ['parser_success'] },
      engine: {
        game_type: 'doudizhu',
        engine_version: '1',
        decision_schema_version: 2,
        rules_ref: null,
        phases: ['playing'],
        prompt_keys: {},
        roles: [],
        supports_deal_seed: true,
        benchmark_seed_count: 50,
      },
    }
    const flat = flattenProtocol(protocol)
    expect(flat?.collect_mode).toBe('benchmark')
    expect(flat?.deal_seeds).toEqual([1, 2])
    expect(flat?.players[0]?.id).toBe('a')
    expect(flat?.engine_version).toBe('1')
    expect(isBenchmarkExperiment({ protocol })).toBe(true)
  })
})
