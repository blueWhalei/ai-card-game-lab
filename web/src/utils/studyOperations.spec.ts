import { expect, it } from 'vitest'
import type { LocationQuery } from 'vue-router'
import { operationKind, operationPosition, operationReturn } from './studyOperations'

it('validates task positions without widening invalid scopes', () => {
  expect(operationPosition({})).toEqual({ state: 'all', page: 1 })
  expect(operationPosition({ task_state: 'attention', task_page: '2' })).toEqual({
    state: 'attention',
    page: 2,
  })
  const invalidQueries: LocationQuery[] = [
    { task_state: 'other' },
    { task_state: ['all', 'active'] },
    { task_page: '0' },
    { task_page: '-1' },
    { task_page: '2foo' },
    { task_page: '1000001' },
  ]
  for (const query of invalidQueries) expect(operationPosition(query)).toBeNull()
})
it('returns only to the owning research and retains filter and page', () => {
  const query = { task_study: 'study', task_state: 'active', task_page: '3' }
  expect(operationReturn(query, 'study')).toEqual({
    path: '/research/study',
    query: { panel: 'operations', task_state: 'active', task_page: '3' },
  })
  expect(operationReturn(query, 'other')).toBeNull()
  expect(operationReturn(query, null)).toBeNull()
  expect(operationReturn({ ...query, task_page: 'bad' }, 'study')).toBeNull()
  expect(operationReturn({ ...query, task_kind: 'training' }, 'study')?.query.task_kind).toBe(
    'training',
  )
  expect(operationReturn({ ...query, task_kind: 'other' }, 'study')).toBeNull()
  expect(operationKind({ task_kind: ['training', 'games'] })).toBeNull()
  expect(operationKind({ task_kind: 'finance' })).toBe('finance')
})
