import { reactive } from 'vue'
import { tt } from '@/i18n'

export type ConfirmOptions = {
  title?: string
  message: string
  confirmText?: string
  cancelText?: string
  danger?: boolean
}

type ConfirmState = {
  open: boolean
  title: string
  message: string
  confirmText: string
  cancelText: string
  danger: boolean
  resolve: ((ok: boolean) => void) | null
}

export const confirmState = reactive<ConfirmState>({
  open: false,
  title: '',
  message: '',
  confirmText: '',
  cancelText: '',
  danger: false,
  resolve: null,
})

export function confirmDialog(options: ConfirmOptions | string): Promise<boolean> {
  const opts = typeof options === 'string' ? { message: options } : options
  return new Promise((resolve) => {
    confirmState.open = true
    confirmState.title = opts.title ?? tt('common.confirm')
    confirmState.message = opts.message
    confirmState.confirmText = opts.confirmText ?? tt('common.ok')
    confirmState.cancelText = opts.cancelText ?? tt('common.cancel')
    confirmState.danger = opts.danger ?? false
    confirmState.resolve = resolve
  })
}

export function finishConfirm(ok: boolean): void {
  const resolve = confirmState.resolve
  confirmState.resolve = null
  confirmState.open = false
  resolve?.(ok)
}
