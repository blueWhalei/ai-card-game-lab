import { invoke, isTauri } from '@tauri-apps/api/core'
import { toast } from '@/components/ui/toast'
import { tt } from '@/i18n'

let savedToast: number | undefined

/** Shared transport for the two supported document formats. No destination paths. */
export async function downloadText(
  filename: string,
  content: string,
  format: 'json' | 'html',
): Promise<boolean> {
  try {
    if (new TextEncoder().encode(content).byteLength > 32 * 1024 * 1024) {
      toast.error(tt('common.exportTooLarge'))
      return false
    }
    if (isTauri()) {
      const id = await invoke<string | null>('save_export', { filename, content, format })
      if (id === null) return false
      if (savedToast !== undefined) toast.dismiss(savedToast)
      savedToast = toast.success(tt('common.exportSaved'), 0, {
        label: tt('common.exportReveal'),
        run: () => invoke<void>('reveal_saved_export', { id }),
        errorMessage: tt('common.exportRevealFailed'),
      })
      return true
    }
    const url = URL.createObjectURL(
      new Blob([content], {
        type: format === 'html' ? 'text/html;charset=utf-8' : 'application/json',
      }),
    )
    try {
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = filename
      anchor.click()
    } finally {
      URL.revokeObjectURL(url)
    }
    toast.info(tt('common.exportDownloadStarted'))
    return true
  } catch {
    toast.error(tt('common.exportSaveFailed'))
    return false
  }
}
