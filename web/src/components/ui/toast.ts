import { reactive } from 'vue'

export type ToastKind = 'success' | 'error' | 'warning' | 'info'

export type ToastItem = {
  id: number
  kind: ToastKind
  message: string
}

const state = reactive<{ items: ToastItem[] }>({ items: [] })
let seq = 0

function push(kind: ToastKind, message: string, durationMs = 3200): number {
  const id = ++seq
  state.items.push({ id, kind, message })
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
  return {
    items: state.items,
    success: (message: string, durationMs?: number) => push('success', message, durationMs),
    error: (message: string, durationMs?: number) => push('error', message, durationMs),
    warning: (message: string, durationMs?: number) => push('warning', message, durationMs),
    info: (message: string, durationMs?: number) => push('info', message, durationMs),
    dismiss: dismissToast,
  }
}

export const toast = {
  success: (message: string, durationMs?: number) => push('success', message, durationMs),
  error: (message: string, durationMs?: number) => push('error', message, durationMs),
  warning: (message: string, durationMs?: number) => push('warning', message, durationMs),
  info: (message: string, durationMs?: number) => push('info', message, durationMs),
  /** Long-lived toast for in-flight operations; call dismiss(id) when done. */
  pending: (message: string) => push('info', message, 0),
  dismiss: dismissToast,
}
