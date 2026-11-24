import { computed, watch } from 'vue'
import type { DraftKind } from '@/api/draftApi'
import { draftDirty, useDraftStore } from '@/stores/useDraftStore'

export function usePersistentDraft(kind: DraftKind, id: string) {
  const store = useDraftStore()
  const session = store.open(kind, id)
  watch(
    () => session.content,
    () => store.schedule(session),
    { deep: true, flush: 'sync' },
  )
  const dirty = computed(() => draftDirty(session))
  return { session, dirty, flush: () => store.flush(session) }
}
