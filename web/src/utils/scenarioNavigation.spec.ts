import { expect, it } from 'vitest'
import { createMemoryHistory, createRouter, type LocationQuery } from 'vue-router'
import {
  scenarioPosition,
  scenarioQuery,
  scenarioReturn,
  SCENARIO_QUERY_KEYS,
} from './scenarioNavigation'
import { restoredWorkspaceRoute } from './workspaceRoute'

it('preserves the original scenario, game, pages and decision independently of the current decision', () => {
  const source = {
    scenario: 'bomb',
    game_id: 'game-a',
    decision_id: 'original',
    page: 2,
    game_page: 3,
  } as const
  const query = {
    ...scenarioQuery(source),
    scenario_run: 'run-a',
    decision_id: 'different',
    game_id: 'different-game',
  }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/experiments/:id',
        name: 'experiment-detail',
        component: { template: '<div />' },
        meta: { desktopResume: ['panel', ...SCENARIO_QUERY_KEYS] },
      },
    ],
  })
  const resolved = router.resolve(
    scenarioReturn(router.resolve({ path: '/experiments/a', query }).query)!,
  )
  expect(scenarioPosition(resolved.query)).toEqual(source)
  expect(resolved.params.id).toBe('run-a')
  expect(restoredWorkspaceRoute(router, resolved.fullPath)).toBe(resolved.fullPath)
})

const invalidPositions: LocationQuery[] = [
  { scenario: 'unknown' },
  { scenario: null },
  { scenario_game: ['a', 'b'] },
  { scenario_page: '0' },
  { scenario_page: '1.5' },
  { scenario_games_page: '100001' },
  { scenario_decision: 'd' },
]
it.each(invalidPositions)('rejects incomplete or ambiguous positions: %j', (query) => {
  expect(scenarioPosition(query)).toBeNull()
  expect(scenarioReturn({ ...query, scenario_run: 'a' })).toBeNull()
})
