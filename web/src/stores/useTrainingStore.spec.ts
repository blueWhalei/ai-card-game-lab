import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { trainingApi, type TrainingTaskPage, type TrainingTask } from '@/api/trainingApi'
import { useTrainingStore } from './useTrainingStore'

beforeEach(() => setActivePinia(createPinia()))
afterEach(() => vi.restoreAllMocks())
const response = (study: string) => ({
  code: 0,
  message: '',
  data: {
    items: [{ id: study, name: study } as TrainingTask],
    total: 1,
    page: 1,
    page_size: 100,
    read_at: 'time',
    filters: { study_id: study, task_id: null, experiment_id: null, state: 'all', status: null },
  } satisfies TrainingTaskPage,
})
it('clears changed scopes and ignores responses after switching or unmounting', async () => {
  let resolveA!: (value: ReturnType<typeof response>) => void
  const pending = new Promise<ReturnType<typeof response>>((resolve) => {
    resolveA = resolve
  })
  const api = vi
    .spyOn(trainingApi, 'listTasks')
    .mockReturnValueOnce(pending)
    .mockResolvedValue(response('b'))
  const store = useTrainingStore()
  const a = store.fetchTasks({ study_id: 'a' })
  await store.fetchTasks({ study_id: 'b' })
  resolveA(response('a'))
  await a
  expect(store.tasks[0]?.id).toBe('b')
  let resolveC!: (value: ReturnType<typeof response>) => void
  api.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        resolveC = resolve
      }),
  )
  const c = store.fetchTasks({ study_id: 'c' })
  expect(store.tasks).toEqual([])
  store.clearTasks()
  resolveC(response('c'))
  await c
  expect(store.tasks).toEqual([])
  expect(store.isLoading).toBe(false)
})
it('shows failures and rejects scope mismatch, then permits retry', async () => {
  const api = vi.spyOn(trainingApi, 'listTasks').mockResolvedValue(response('wrong'))
  const store = useTrainingStore()
  await store.fetchTasks({ study_id: 'a' })
  expect(store.tasksFailed).toBe(true)
  expect(store.tasks).toEqual([])
  api.mockRejectedValueOnce(new Error('offline'))
  await store.fetchTasks({ study_id: 'a' })
  expect(store.tasksFailed).toBe(true)
  api.mockResolvedValue(response('a'))
  await store.fetchTasks({ study_id: 'a' })
  expect(store.tasksFailed).toBe(false)
  expect(store.tasks[0]?.id).toBe('a')
})
