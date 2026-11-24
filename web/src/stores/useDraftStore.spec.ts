/** @vitest-environment happy-dom */
import { beforeEach, afterEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'
import { draftApi, type DraftContent, type DraftRecord } from '@/api/draftApi'
import type { ApiResponse } from '@/api/types'
import { draftDirty, useDraftStore } from './useDraftStore'

const initial: DraftContent = {
  kind: 'experiment',
  hypothesis: '',
  notes: '',
  conclusion: '',
  tags_input: '',
}
function response(content: DraftContent, revision = 0): ApiResponse<DraftRecord> {
  return {
    code: 0,
    message: 'success',
    data: {
      content: structuredClone(content),
      revision,
      updated_at: revision ? '2026-11-03' : null,
    },
  }
}
beforeEach(() => {
  setActivePinia(createPinia())
  vi.spyOn(draftApi, 'get').mockResolvedValue(response(initial))
})
afterEach(() => vi.restoreAllMocks())

it('serializes writes without overwriting edits made during an in-flight save', async () => {
  const store = useDraftStore()
  const session = store.open('experiment', 'e')
  await flushPromises()
  if (session.content?.kind !== 'experiment') throw new Error('missing draft')
  session.content.notes = 'first edit'
  let resolveFirst!: (value: ApiResponse<DraftRecord>) => void
  const save = vi
    .spyOn(draftApi, 'save')
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveFirst = resolve
        }),
    )
    .mockImplementation(async (_kind, _id, revision, content) => response(content, revision + 1))
  const pending = store.flush(session)
  session.content.notes = 'second edit'
  resolveFirst(response({ ...initial, notes: 'first edit' }, 1))
  expect(await pending).toBe(true)
  expect(save.mock.calls.map((call) => call[2])).toEqual([0, 1])
  expect(session.content.notes).toBe('second edit')
  expect(draftDirty(session)).toBe(false)
})

it('retains failed input across editor reopening and refuses navigation flush', async () => {
  const store = useDraftStore()
  const session = store.open('experiment', 'e')
  await flushPromises()
  if (session.content?.kind !== 'experiment') throw new Error('missing draft')
  session.content.notes = 'keep this'
  vi.spyOn(draftApi, 'save').mockRejectedValue({ code: 'DRAFT_CONFLICT', message: 'conflict' })
  expect(await store.flushAll()).toBe(false)
  expect(store.open('experiment', 'e')).toBe(session)
  expect(session.content.notes).toBe('keep this')
  expect(session.revision).toBe(0)
  expect(session.error).toBeTruthy()
  expect(draftDirty(session)).toBe(true)
})

it('restores a saved draft in a fresh application without writing on load', async () => {
  vi.mocked(draftApi.get).mockResolvedValue(response({ ...initial, notes: 'restored text' }, 4))
  const save = vi.spyOn(draftApi, 'save')
  const session = useDraftStore().open('experiment', 'e')
  await flushPromises()
  expect(session.content).toEqual({ ...initial, notes: 'restored text' })
  expect(session.revision).toBe(4)
  expect(save).not.toHaveBeenCalled()
})

it('allows leaving an untouched editor while its first read is pending', async () => {
  let resolveRead!: (value: ApiResponse<DraftRecord>) => void
  vi.mocked(draftApi.get).mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        resolveRead = resolve
      }),
  )
  const save = vi.spyOn(draftApi, 'save')
  const store = useDraftStore()
  const session = store.open('experiment', 'e')
  expect(session.loading).toBe(true)
  expect(await store.flushAll()).toBe(true)
  expect(save).not.toHaveBeenCalled()
  resolveRead(response({ ...initial, notes: 'saved text' }, 2))
  await flushPromises()
  expect(store.open('experiment', 'e').content).toEqual({ ...initial, notes: 'saved text' })
})
