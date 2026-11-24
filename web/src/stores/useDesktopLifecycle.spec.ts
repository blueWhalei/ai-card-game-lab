/** @vitest-environment happy-dom */
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'
import { invoke, isTauri } from '@tauri-apps/api/core'
import { listen, type Event } from '@tauri-apps/api/event'
import { useDraftStore } from './useDraftStore'
import { useDesktopLifecycle } from './useDesktopLifecycle'
import { useDesktopWorkspace } from './useDesktopWorkspace'
import { draftApi } from '@/api/draftApi'

vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn(), isTauri: vi.fn() }))
vi.mock('@tauri-apps/api/event', () => ({ listen: vi.fn() }))
vi.mock('@tauri-apps/api/webviewWindow', () => ({
  getCurrentWebviewWindow: () => ({ label: 'main' }),
}))
const handlers = new Map<string, (event: Event<unknown>) => void>()
function emit(name: string, payload: unknown) {
  handlers.get(name)?.({ event: name, id: 0, payload })
}
const prepare = (id = 1) => emit('cardlab-close-requested', { id, appExit: true })
const cancelled = (id = 1, reason: string | null = null) =>
  emit('cardlab-close-cancelled', { id, reason })

beforeEach(() => {
  setActivePinia(createPinia())
  handlers.clear()
  vi.mocked(isTauri).mockReturnValue(true)
  vi.mocked(invoke).mockResolvedValue(undefined)
  vi.mocked(listen).mockImplementation(async (event, handler) => {
    handlers.set(String(event), handler as (event: Event<unknown>) => void)
    return () => {
      handlers.delete(String(event))
    }
  })
})
afterEach(() => vi.restoreAllMocks())

it('waits for persistence acknowledgment and keeps editing locked until native cancellation', async () => {
  let saved!: (ok: boolean) => void
  vi.spyOn(useDraftStore(), 'flushAll').mockImplementation(
    () =>
      new Promise((resolve) => {
        saved = resolve
      }),
  )
  const lifecycle = useDesktopLifecycle()
  await lifecycle.connect()
  prepare()
  expect(lifecycle.locked).toBe(true)
  expect(invoke).not.toHaveBeenCalled()
  saved(true)
  await flushPromises()
  expect(invoke).toHaveBeenCalledWith('complete_close', { id: 1, outcome: 'saved' })
  expect(lifecycle.locked).toBe(true)
  cancelled()
  expect(lifecycle.locked).toBe(false)
})

it('reports failed saves without discarding or publishing', async () => {
  vi.spyOn(useDraftStore(), 'flushAll').mockResolvedValue(false)
  const discard = vi.spyOn(useDraftStore(), 'discard')
  const lifecycle = useDesktopLifecycle()
  await lifecycle.connect()
  prepare()
  await flushPromises()
  expect(invoke).toHaveBeenCalledWith('complete_close', { id: 1, outcome: 'save_failed' })
  cancelled(1, 'save_failed')
  expect(lifecycle.failure).toBe('save_failed')
  expect(discard).not.toHaveBeenCalled()
  await lifecycle.cancel()
  expect(lifecycle.failure).toBeNull()
})

it('waits for the workspace write before acknowledging and cancels on write failure', async () => {
  vi.spyOn(useDraftStore(), 'flushAll').mockResolvedValue(true)
  let finish!: (ok: boolean) => void
  const flush = vi.spyOn(useDesktopWorkspace(), 'flush').mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve
      }),
  )
  const lifecycle = useDesktopLifecycle()
  await lifecycle.connect()
  prepare()
  await flushPromises()
  expect(invoke).not.toHaveBeenCalled()
  finish(false)
  await flushPromises()
  expect(invoke).toHaveBeenLastCalledWith('complete_close', { id: 1, outcome: 'workspace_failed' })
  cancelled(1, 'workspace_failed')
  expect(lifecycle.failure).toBe('workspace_failed')
  flush.mockResolvedValue(true)
  prepare(2)
  await flushPromises()
  expect(invoke).toHaveBeenLastCalledWith('complete_close', { id: 2, outcome: 'saved' })
})

it('ignores a workspace write that finishes after closing was cancelled', async () => {
  vi.spyOn(useDraftStore(), 'flushAll').mockResolvedValue(true)
  let finish!: (ok: boolean) => void
  vi.spyOn(useDesktopWorkspace(), 'flush').mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve
      }),
  )
  const lifecycle = useDesktopLifecycle()
  await lifecycle.connect()
  prepare()
  await flushPromises()
  cancelled()
  finish(true)
  await flushPromises()
  expect(invoke).not.toHaveBeenCalled()
})

it('revokes the close check when an already pending navigation completes late', async () => {
  vi.spyOn(useDraftStore(), 'flushAll').mockResolvedValue(true)
  const lifecycle = useDesktopLifecycle()
  await lifecycle.connect()
  prepare()
  await flushPromises()
  expect(invoke).toHaveBeenLastCalledWith('complete_close', { id: 1, outcome: 'saved' })
  useDesktopWorkspace().revision++
  await flushPromises()
  expect(invoke).toHaveBeenLastCalledWith('cancel_close', { id: 1 })
  expect(lifecycle.locked).toBe(false)
})

it('blocks uncreated designs and unregisters the blocker when the editor leaves', async () => {
  vi.spyOn(useDraftStore(), 'flushAll').mockResolvedValue(true)
  const lifecycle = useDesktopLifecycle()
  const remove = lifecycle.registerBlocker(() => true)
  await lifecycle.connect()
  prepare()
  await flushPromises()
  expect(invoke).toHaveBeenLastCalledWith('complete_close', { id: 1, outcome: 'unfinished_design' })
  cancelled()
  remove()
  prepare(2)
  await flushPromises()
  expect(invoke).toHaveBeenLastCalledWith('complete_close', { id: 2, outcome: 'saved' })
})

it('does not acknowledge a cancelled request after a late save or start duplicate saves', async () => {
  let saved!: (ok: boolean) => void
  const flush = vi.spyOn(useDraftStore(), 'flushAll').mockImplementation(
    () =>
      new Promise((resolve) => {
        saved = resolve
      }),
  )
  const lifecycle = useDesktopLifecycle()
  await lifecycle.connect()
  prepare()
  prepare()
  expect(flush).toHaveBeenCalledTimes(1)
  await lifecycle.cancel()
  saved(true)
  await flushPromises()
  expect(invoke).toHaveBeenCalledTimes(1)
  expect(invoke).toHaveBeenCalledWith('cancel_close', { id: 1 })
  flush.mockResolvedValue(true)
  prepare(2)
  cancelled(1, 'unresponsive')
  await flushPromises()
  expect(lifecycle.request?.id).toBe(2)
  expect(lifecycle.failure).toBeNull()
})

it('keeps an IPC failure visible and locked until cancellation is confirmed', async () => {
  vi.spyOn(useDraftStore(), 'flushAll').mockResolvedValue(true)
  vi.mocked(invoke).mockRejectedValue(new Error('bridge unavailable'))
  const lifecycle = useDesktopLifecycle()
  await lifecycle.connect()
  prepare()
  await flushPromises()
  expect(lifecycle.locked).toBe(true)
  expect(lifecycle.failure).toBe('bridge')
  await lifecycle.cancel()
  expect(lifecycle.locked).toBe(true)
  cancelled(1, 'unresponsive')
  expect(lifecycle.locked).toBe(false)
})

it('does not register native hooks in the browser and cleans up native listeners', async () => {
  const lifecycle = useDesktopLifecycle()
  vi.mocked(isTauri).mockReturnValue(false)
  const noop = await lifecycle.connect()
  noop()
  expect(listen).not.toHaveBeenCalled()
  vi.mocked(isTauri).mockReturnValue(true)
  const disconnect = await lifecycle.connect()
  expect(handlers.size).toBe(2)
  expect(listen).toHaveBeenLastCalledWith('cardlab-close-requested', expect.any(Function), {
    target: { kind: 'WebviewWindow', label: 'main' },
  })
  disconnect()
  expect(handlers.size).toBe(0)
})

it('revokes a completed save check if asynchronous editor work produces new changes', async () => {
  vi.spyOn(draftApi, 'get').mockResolvedValue({
    code: 0,
    message: '',
    data: {
      revision: 0,
      updated_at: null,
      content: { kind: 'experiment', hypothesis: '', notes: '', conclusion: '', tags_input: '' },
    },
  })
  const drafts = useDraftStore()
  const draft = drafts.open('experiment', 'e')
  await flushPromises()
  const lifecycle = useDesktopLifecycle()
  await lifecycle.connect()
  prepare()
  await flushPromises()
  expect(invoke).toHaveBeenLastCalledWith('complete_close', { id: 1, outcome: 'saved' })
  if (draft.content?.kind !== 'experiment') throw new Error('missing draft')
  draft.content.notes = 'late generated summary'
  await flushPromises()
  expect(invoke).toHaveBeenLastCalledWith('cancel_close', { id: 1 })
  expect(lifecycle.locked).toBe(false)
  expect(draft.content.notes).toBe('late generated summary')
})

it('starts a fresh save check after cancelling an earlier successful check', async () => {
  vi.spyOn(draftApi, 'get').mockResolvedValue({
    code: 0,
    message: '',
    data: {
      revision: 0,
      updated_at: null,
      content: { kind: 'experiment', hypothesis: '', notes: '', conclusion: '', tags_input: '' },
    },
  })
  const drafts = useDraftStore()
  const draft = drafts.open('experiment', 'repeat')
  await flushPromises()
  const lifecycle = useDesktopLifecycle()
  await lifecycle.connect()
  prepare()
  await flushPromises()
  cancelled()
  if (draft.content?.kind !== 'experiment') throw new Error('missing draft')
  draft.content.notes = 'second close has unsaved work'
  let complete!: (ok: boolean) => void
  vi.spyOn(drafts, 'flushAll').mockImplementation(
    () =>
      new Promise((resolve) => {
        complete = resolve
      }),
  )
  vi.mocked(invoke).mockClear()
  prepare(2)
  await flushPromises()
  expect(invoke).not.toHaveBeenCalled()
  expect(lifecycle.request?.id).toBe(2)
  complete(false)
  await flushPromises()
  expect(invoke).toHaveBeenLastCalledWith('complete_close', { id: 2, outcome: 'save_failed' })
})
