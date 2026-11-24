import type { LocationQuery } from 'vue-router'
import type { OperationFilter } from '@/api/studyApi'

export function operationKind(query: LocationQuery): 'games' | 'training' | 'finance' | null {
  const kind = query.task_kind ?? 'games'
  return kind === 'games' || kind === 'training' || kind === 'finance' ? kind : null
}

export function operationPosition(
  query: LocationQuery,
): { state: OperationFilter; page: number } | null {
  const state = query.task_state ?? 'all'
  const rawPage = query.task_page ?? '1'
  if (state !== 'all' && state !== 'active' && state !== 'attention') return null
  if (typeof rawPage !== 'string' || !/^[1-9]\d{0,6}$/.test(rawPage)) return null
  const page = Number(rawPage)
  return page <= 1000000 ? { state, page } : null
}

export function operationReturn(query: LocationQuery, studyId: string | null | undefined) {
  const position = operationPosition(query)
  const kind = operationKind(query)
  if (!studyId || query.task_study !== studyId || !position || !kind) return null
  return {
    path: `/research/${encodeURIComponent(studyId)}`,
    query: {
      panel: 'operations',
      task_state: position.state,
      task_page: String(position.page),
      ...(kind !== 'games' ? { task_kind: kind } : {}),
    },
  }
}
