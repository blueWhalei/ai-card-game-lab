import { reactive } from 'vue'

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
  title: '确认',
  message: '',
  confirmText: '确定',
  cancelText: '取消',
  danger: false,
  resolve: null,
})

export function confirmDialog(options: ConfirmOptions | string): Promise<boolean> {
  const opts = typeof options === 'string' ? { message: options } : options
  return new Promise((resolve) => {
    confirmState.open = true
    confirmState.title = opts.title ?? '确认'
    confirmState.message = opts.message
    confirmState.confirmText = opts.confirmText ?? '确定'
    confirmState.cancelText = opts.cancelText ?? '取消'
    confirmState.danger = opts.danger ?? false
    confirmState.resolve = resolve
  })
}

export function finishConfirm(ok: boolean): void {
  confirmState.open = false
  confirmState.resolve?.(ok)
  confirmState.resolve = null
}
