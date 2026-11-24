import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { invoke, isTauri } from '@tauri-apps/api/core'
import { listen, type UnlistenFn } from '@tauri-apps/api/event'
import { getCurrentWebviewWindow } from '@tauri-apps/api/webviewWindow'
import { draftDirty, useDraftStore } from '@/stores/useDraftStore'
import { useDesktopWorkspace } from '@/stores/useDesktopWorkspace'

interface CloseRequest {
  id: number
  appExit: boolean
}
type Failure = 'save_failed' | 'unfinished_design' | 'workspace_failed' | 'unresponsive' | 'bridge'
interface Cancelled {
  id: number
  reason: Failure | null
}

/** One native close protocol; persistence stays in the shared draft store. */
export const useDesktopLifecycle = defineStore('desktop-lifecycle', () => {
  const request = ref<CloseRequest | null>(null)
  const phase = ref<'saving' | 'waiting'>('saving')
  const failure = ref<Failure | null>(null)
  const prepared = ref(false)
  const drafts = useDraftStore()
  const workspace = useDesktopWorkspace()
  let preparedRevision = 0
  const blockers = new Set<() => boolean>()
  const locked = computed(() => request.value !== null)

  // Async editor work can finish after an earlier save check. Revoke that check.
  watch(
    () =>
      prepared.value &&
      request.value !== null &&
      (workspace.revision !== preparedRevision ||
        Object.values(drafts.sessions).some((session) => draftDirty(session) || session.saving) ||
        [...blockers].some((blocked) => blocked())),
    (changed) => {
      if (changed) void cancel()
    },
    { flush: 'sync' },
  )

  function registerBlocker(blocked: () => boolean): () => void {
    blockers.add(blocked)
    return () => {
      blockers.delete(blocked)
    }
  }

  async function prepare(next: CloseRequest): Promise<void> {
    if (request.value?.id === next.id) return
    prepared.value = false
    request.value = next
    phase.value = 'saving'
    failure.value = null
    preparedRevision = workspace.revision
    try {
      const saved = await drafts.flushAll()
      if (request.value?.id !== next.id) return
      let outcome = !saved
        ? 'save_failed'
        : [...blockers].some((blocked) => blocked())
          ? 'unfinished_design'
          : 'saved'
      if (outcome === 'saved' && !(await workspace.flush())) outcome = 'workspace_failed'
      if (request.value?.id !== next.id) return
      phase.value = 'waiting'
      await invoke('complete_close', { id: next.id, outcome })
      if (request.value?.id === next.id) prepared.value = outcome === 'saved'
    } catch {
      if (request.value?.id === next.id) failure.value = 'bridge'
    }
  }

  async function cancel(): Promise<void> {
    const id = request.value?.id
    if (id === undefined) {
      failure.value = null
      return
    }
    try {
      await invoke('cancel_close', { id })
      if (request.value?.id === id) {
        request.value = null
        prepared.value = false
        failure.value = null
      }
    } catch {
      if (request.value?.id === id) failure.value = 'bridge'
    }
  }

  async function connect(): Promise<UnlistenFn> {
    if (!isTauri()) return () => {}
    const unsubscribers: UnlistenFn[] = []
    const target = { kind: 'WebviewWindow' as const, label: getCurrentWebviewWindow().label }
    try {
      unsubscribers.push(
        await listen<Cancelled>(
          'cardlab-close-cancelled',
          ({ payload }) => {
            if (request.value?.id !== payload.id) return
            prepared.value = false
            request.value = null
            failure.value = payload.reason
          },
          { target },
        ),
      )
      unsubscribers.push(
        await listen<CloseRequest>(
          'cardlab-close-requested',
          ({ payload }) => {
            void prepare(payload)
          },
          { target },
        ),
      )
    } catch {
      unsubscribers.forEach((unsubscribe) => unsubscribe())
      failure.value = 'bridge'
      return () => {}
    }
    return () => {
      unsubscribers.forEach((unsubscribe) => unsubscribe())
    }
  }

  return { request, phase, failure, locked, registerBlocker, connect, cancel }
})
