import type { LocationQuery, LocationQueryRaw } from 'vue-router'
import type { ScenarioQuery } from '@/api/experimentApi'
import { EXPERIMENT_SCENARIO_IDS } from '@/utils/experimentWorkbench'

export const SCENARIO_QUERY_KEYS = [
  'scenario',
  'scenario_game',
  'scenario_decision',
  'scenario_games_page',
  'scenario_page',
] as const

export function scenarioPosition(query: LocationQuery): ScenarioQuery | null {
  for (const key of SCENARIO_QUERY_KEYS) {
    if (
      Object.hasOwn(query, key) &&
      (typeof query[key] !== 'string' || !query[key] || query[key].length > 128)
    )
      return null
  }
  const scenario = query.scenario
  if (scenario && scenario !== 'all' && !EXPERIMENT_SCENARIO_IDS.some((id) => id === scenario))
    return null
  const number = (key: string) => {
    const raw = query[key]
    if (raw === undefined) return 1
    return typeof raw === 'string' && /^[1-9]\d*$/.test(raw) && Number(raw) <= 100000
      ? Number(raw)
      : 0
  }
  const page = number('scenario_page')
  const game_page = number('scenario_games_page')
  if (!page || !game_page || (query.scenario_decision && !query.scenario_game)) return null
  return {
    scenario: scenario === 'all' ? undefined : (scenario as ScenarioQuery['scenario']),
    game_id: query.scenario_game as string | undefined,
    decision_id: query.scenario_decision as string | undefined,
    game_page,
    page,
  }
}

export function scenarioQuery(position: ScenarioQuery): LocationQueryRaw {
  return {
    scenario: position.scenario ?? 'all',
    scenario_game: position.game_id,
    scenario_decision: position.decision_id,
    scenario_games_page: position.game_page > 1 ? String(position.game_page) : undefined,
    scenario_page: position.page > 1 ? String(position.page) : undefined,
  }
}

export function scenarioReturn(query: LocationQuery) {
  const id = query.scenario_run
  const position = scenarioPosition(query)
  if (typeof id !== 'string' || !id || id.length > 128 || !position) return null
  return {
    name: 'experiment-detail',
    params: { id },
    query: { panel: 'scenarios', ...scenarioQuery(position) },
  }
}
