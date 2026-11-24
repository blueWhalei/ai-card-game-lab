/** @vitest-environment happy-dom */
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import ToastHost from './ToastHost.vue'
import { runToastAction, toast, useToast } from './toast'

vi.mock('@iconify/vue', () => ({ Icon: { render: () => null } }))

enableAutoUnmount(afterEach)
beforeEach(() => vi.useFakeTimers())
afterEach(() => {
  useToast().items.map((item) => item.id).forEach(toast.dismiss)
  vi.clearAllTimers()
  vi.useRealTimers()
})

function mountHost() {
  return mount(ToastHost, {
    global: {
      plugins: [
        createI18n({
          legacy: false,
          locale: 'en',
          messages: { en: { common: { close: 'Close' } } },
        }),
      ],
    },
  })
}

it('keeps an action available, disables repeat activation while pending, and dismisses after success', async () => {
  let finish!: () => void
  const run = vi.fn(
    () =>
      new Promise<void>((resolve) => {
        finish = resolve
      }),
  )
  const wrapper = mountHost()
  const id = toast.success('File saved', 0, {
    label: 'Show in folder',
    run,
    errorMessage: 'Cannot locate',
  })
  await vi.advanceTimersByTimeAsync(60000)
  const button = wrapper.findAll('button').find((button) => button.text() === 'Show in folder')!
  expect(button.exists()).toBe(true)
  await button.trigger('click')
  expect(button.attributes('disabled')).toBeDefined()
  await runToastAction(id)
  expect(run).toHaveBeenCalledOnce()
  finish()
  await flushPromises()
  expect(useToast().items).toHaveLength(0)
})

it('preserves the saved-file action on failure and permits a successful retry', async () => {
  const run = vi
    .fn()
    .mockRejectedValueOnce(new Error('file moved'))
    .mockResolvedValueOnce(undefined)
  const id = toast.success('File saved', 0, {
    label: 'Show in folder',
    run,
    errorMessage: 'Cannot locate',
  })
  await runToastAction(id)
  expect(useToast().items.find((item) => item.id === id)?.busy).toBe(false)
  expect(useToast().items.some((item) => item.message === 'Cannot locate')).toBe(true)
  await runToastAction(id)
  expect(run).toHaveBeenCalledTimes(2)
  expect(useToast().items.some((item) => item.id === id)).toBe(false)
})

it('retains ordinary toast expiry and allows dismissing an actionable notification', async () => {
  const wrapper = mountHost()
  toast.info('Ordinary notification')
  await vi.advanceTimersByTimeAsync(3200)
  expect(useToast().items).toHaveLength(0)
  const run = vi.fn()
  toast.success('File saved', 0, { label: 'Show in folder', run, errorMessage: 'Cannot locate' })
  await flushPromises()
  await wrapper.get('button[aria-label="Close"]').trigger('click')
  expect(useToast().items).toHaveLength(0)
  expect(run).not.toHaveBeenCalled()
})
