import { reactive } from 'vue'

export type ToastKind = 'success' | 'error' | 'warning' | 'info'

export type ToastItem = {
  id: number
  kind: ToastKind
  message: string
}

const state = reactive<{ items: ToastItem[] }>({ items: [] })
let seq = 0

function push(kind: ToastKind, message: string, durationMs = 3200): void {
  const id = ++seq
  state.items.push({ id, kind, message })
  window.setTimeout(() => dismissToast(id), durationMs)
}

export function dismissToast(id: number): void {
  const i = state.items.findIndex((t) => t.id === id)
  if (i >= 0) state.items.splice(i, 1)
}

export function useToast() {
  return {
    items: state.items,
    success: (message: string) => push('success', message),
    error: (message: string) => push('error', message),
    warning: (message: string) => push('warning', message),
    info: (message: string) => push('info', message),
    dismiss: dismissToast,
  }
}

export const toast = {
  success: (message: string) => push('success', message),
  error: (message: string) => push('error', message),
  warning: (message: string) => push('warning', message),
  info: (message: string) => push('info', message),
}
