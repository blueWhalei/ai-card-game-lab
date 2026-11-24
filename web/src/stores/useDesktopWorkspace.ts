import { defineStore } from 'pinia'
import { ref } from 'vue'
import { invoke, isTauri } from '@tauri-apps/api/core'
import { getCurrentWebviewWindow } from '@tauri-apps/api/webviewWindow'
import type { Router } from 'vue-router'
import { workspaceRoute, restoredWorkspaceRoute } from '@/utils/workspaceRoute'
import { toast } from '@/components/ui/toast'
import { tt } from '@/i18n'

/** Navigation ownership belongs to main; research content belongs to the draft service. */
export const useDesktopWorkspace = defineStore('desktop-workspace', () => {
  let enabled = false
  let location = '/'
  const revision = ref(0)

  async function initialize(router: Router): Promise<() => void> {
    if (!isTauri() || getCurrentWebviewWindow().label !== 'main') return () => {}
    await router.isReady()
    try {
      // A refresh or an explicitly opened location must retain its own address.
      if (router.currentRoute.value.fullPath === '/') {
        const saved = await invoke<string | null>('read_workspace')
        if (saved !== null) await router.replace(restoredWorkspaceRoute(router, saved))
      }
    } catch {
      toast.warning(tt('desktopClose.restore_failed'), 8000)
    }
    enabled = true
    location = workspaceRoute(router, router.currentRoute.value) ?? '/'
    const remove = router.afterEach((to, _from, failure) => {
      if (!failure) {
        location = workspaceRoute(router, to) ?? location
        revision.value++
      }
    })
    return () => {
      enabled = false
      remove()
    }
  }

  async function flush(): Promise<boolean> {
    if (!enabled) return true
    try {
      await invoke('save_workspace', { route: location })
      return true
    } catch {
      return false
    }
  }

  return { initialize, flush, revision }
})
