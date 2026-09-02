import { describe, expect, it } from 'vitest'
import { configIdForModel, ollamaTagForModel } from './adapterConfig'

describe('adapterConfig', () => {
  it('ollamaTagForModel matches backend task_id[:12] rule', () => {
    expect(ollamaTagForModel('train_20260902051910_poruze')).toBe('cardlab-train_202609')
  })

  it('configIdForModel sanitizes task id', () => {
    expect(configIdForModel('train_20260902051910_poruze')).toBe('lora_train_20260902051910_poruze')
  })
})
