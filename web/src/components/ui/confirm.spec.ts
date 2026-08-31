import { describe, expect, it } from 'vitest'
import { confirmDialog, confirmState, finishConfirm } from './confirm'

describe('confirmDialog', () => {
  it('resolves true once even if the dialog then emits close', async () => {
    const pending = confirmDialog({ message: '删除？', danger: true })
    expect(confirmState.open).toBe(true)
    finishConfirm(true)
    finishConfirm(false)
    await expect(pending).resolves.toBe(true)
    expect(confirmState.open).toBe(false)
  })

  it('treats overlay dismiss as cancel', async () => {
    const pending = confirmDialog('删除？')
    finishConfirm(false)
    await expect(pending).resolves.toBe(false)
  })
})
