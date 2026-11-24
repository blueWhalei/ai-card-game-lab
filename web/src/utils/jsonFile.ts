import { downloadText } from '@/utils/exportFile'
import { toast } from '@/components/ui/toast'
import { tt } from '@/i18n'

/** JSON serialization delegates saving and feedback to the shared export transport. */
export async function downloadJson(filename: string, data: unknown): Promise<boolean> {
  try {
    const content = JSON.stringify(data, null, 2)
    if (content === undefined) throw new Error('Missing JSON content')
    return await downloadText(filename, content, 'json')
  } catch {
    toast.error(tt('common.exportSaveFailed'))
    return false
  }
}

/**
 * Open the system file picker and parse one JSON file.
 *
 * Resolves ``null`` when the user cancels. The browser fires no ``change`` event
 * on cancel, so we treat the window regaining focus (without a selection) as the
 * cancel signal -- otherwise callers that flip a loading flag before awaiting
 * this would spin forever.
 */
export function pickJsonFile(): Promise<unknown | null> {
  return new Promise((resolve, reject) => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = 'application/json,.json'

    let settled = false
    const finish = (value: unknown | null) => {
      if (settled) return
      settled = true
      window.removeEventListener('focus', onFocus)
      resolve(value)
    }

    const onFocus = () => {
      // ``change`` runs before ``focus`` when a file is chosen; give it a tick.
      window.setTimeout(() => {
        if (!settled) finish(null)
      }, 0)
    }

    input.addEventListener('change', () => {
      const file = input.files?.[0]
      if (!file) {
        finish(null)
        return
      }
      // Claim the promise before the async read so the cancel path cannot win.
      settled = true
      window.removeEventListener('focus', onFocus)
      void file
        .text()
        .then((text) => {
          try {
            resolve(JSON.parse(text) as unknown)
          } catch {
            reject(new Error('invalid json'))
          }
        })
        .catch(() => reject(new Error('invalid json')))
    })

    window.addEventListener('focus', onFocus)
    input.click()
  })
}
