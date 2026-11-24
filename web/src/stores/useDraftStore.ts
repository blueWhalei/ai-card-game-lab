import { reactive } from 'vue'
import { defineStore } from 'pinia'
import { draftApi, type DraftContent, type DraftKind } from '@/api/draftApi'
import { getErrorMessage } from '@/utils/error'

export interface DraftSession {
  kind: DraftKind
  id: string
  content: DraftContent | null
  revision: number
  updatedAt: string | null
  acknowledged: string
  loading: boolean
  saving: boolean
  error: string
}

export function draftDirty(session: DraftSession): boolean {
  return session.content !== null && JSON.stringify(session.content) !== session.acknowledged
}

/** Sessions outlive editors: closing a dialog cannot discard a failed write. */
export const useDraftStore = defineStore('workspace-drafts', () => {
  const sessions = reactive<Record<string, DraftSession>>({})
  const timers = new Map<string, ReturnType<typeof setTimeout>>()
  const writes = new Map<string, Promise<boolean>>()

  function keyOf(session: DraftSession): string {
    return `${session.kind}:${session.id}`
  }

  async function reload(session: DraftSession): Promise<void> {
    clearTimeout(timers.get(keyOf(session)))
    timers.delete(keyOf(session))
    session.loading = true
    session.error = ''
    try {
      const { data } = await draftApi.get(session.kind, session.id)
      session.content = data.content
      session.revision = data.revision
      session.updatedAt = data.updated_at
      session.acknowledged = JSON.stringify(data.content)
    } catch (error) {
      session.error = getErrorMessage(error)
    } finally {
      session.loading = false
    }
  }

  function open(kind: DraftKind, id: string): DraftSession {
    const key = `${kind}:${id}`
    if (!sessions[key]) {
      sessions[key] = {
        kind,
        id,
        content: null,
        revision: 0,
        updatedAt: null,
        acknowledged: '',
        loading: true,
        saving: false,
        error: '',
      }
      void reload(sessions[key])
    }
    return sessions[key]
  }

  async function flush(session: DraftSession): Promise<boolean> {
    if (session.loading) return false
    const key = keyOf(session)
    clearTimeout(timers.get(key))
    timers.delete(key)
    const active = writes.get(key)
    if (active) return active
    if (!draftDirty(session)) return !session.loading
    const task = (async () => {
      session.saving = true
      session.error = ''
      try {
        // Drain new edits made during an in-flight request in order.
        while (session.content && draftDirty(session)) {
          const sent = JSON.stringify(session.content)
          const content: DraftContent = JSON.parse(sent)
          const { data } = await draftApi.save(session.kind, session.id, session.revision, content)
          session.revision = data.revision
          session.updatedAt = data.updated_at
          session.acknowledged = sent
        }
        return true
      } catch (error) {
        session.error = getErrorMessage(error)
        return false
      } finally {
        session.saving = false
      }
    })()
    writes.set(key, task)
    try {
      return await task
    } finally {
      writes.delete(key)
    }
  }

  function schedule(session: DraftSession): void {
    if (session.loading || !draftDirty(session) || session.error) return
    const key = keyOf(session)
    clearTimeout(timers.get(key))
    timers.set(
      key,
      setTimeout(() => {
        void flush(session)
      }, 400),
    )
  }

  async function flushAll(): Promise<boolean> {
    const pending = Object.values(sessions).filter(
      (session) => draftDirty(session) || session.saving,
    )
    const results = await Promise.all(pending.map(flush))
    return results.every(Boolean)
  }

  function discard(session: DraftSession): void {
    clearTimeout(timers.get(keyOf(session)))
    timers.delete(keyOf(session))
    session.content = session.acknowledged
      ? (JSON.parse(session.acknowledged) as DraftContent)
      : null
    session.error = ''
  }

  return { sessions, open, reload, flush, schedule, flushAll, discard }
})
