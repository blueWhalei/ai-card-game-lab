import { reactive } from 'vue'

export type ToastKind = 'success' | 'error' | 'warning' | 'info'

export type ToastAction = {
  label: string
  run: () => Promise<void>
  errorMessage: string
}

export type ToastItem = {
  id: number
  kind: ToastKind
  message: string
  action?: ToastAction
  busy: boolean
}

const state = reactive<{ items: ToastItem[] }>({ items: [] })
let seq = 0

function push(kind: ToastKind, message: string, durationMs = 3200, action?: ToastAction): number {
  const id = ++seq
  state.items.push({ id, kind, message, action, busy: false })
  if (durationMs > 0) {
    window.setTimeout(() => dismissToast(id), durationMs)
  }
  return id
}

export function dismissToast(id: number): void {
  const i = state.items.findIndex((t) => t.id === id)
  if (i >= 0) state.items.splice(i, 1)
}

export function useToast() {
  return { items: state.items, ...toast }
}

export async function runToastAction(id: number): Promise<void> {
  const item = state.items.find((entry) => entry.id === id)
  if (!item?.action || item.busy) return
  item.busy = true
  try {
    await item.action.run()
    dismissToast(id)
  } catch {
    toast.error(item.action.errorMessage)
  } finally {
    item.busy = false
  }
}

export const toast = {
  success: (message: string, durationMs?: number, action?: ToastAction) =>
    push('success', message, durationMs, action),
  error: (message: string, durationMs?: number) => push('error', message, durationMs),
  warning: (message: string, durationMs?: number) => push('warning', message, durationMs),
  info: (message: string, durationMs?: number) => push('info', message, durationMs),
  /** Long-lived toast for in-flight operations; call dismiss(id) when done. */
  pending: (message: string) => push('info', message, 0),
  dismiss: dismissToast,
}
