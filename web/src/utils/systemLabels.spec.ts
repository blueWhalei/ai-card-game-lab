import { describe, expect, it } from 'vitest'
import { localeRef } from '@/i18n'
import { preflightCheckMessage, providerName } from './systemLabels'

describe('preflightCheckMessage', () => {
  it('localizes seat-provider failures with interpolated ids', () => {
    const check = {
      id: 'providers_seats',
      severity: 'block' as const,
      ok: false,
      message: '实验座位供应商未配置：ollama。请在 .env 配置密钥，或改选手配置。',
      params: { providers: 'ollama' },
    }
    localeRef().value = 'zh-CN'
    expect(preflightCheckMessage(check)).toContain('ollama')
    expect(preflightCheckMessage(check)).toContain('改选手配置')
    localeRef().value = 'en'
    expect(preflightCheckMessage(check)).toContain('ollama')
    expect(preflightCheckMessage(check)).toMatch(/player configs|\.env/i)
    localeRef().value = 'zh-CN'
  })

  it('uses the incomplete-protocol copy when params.incomplete is set', () => {
    const check = {
      id: 'providers_seats',
      severity: 'block' as const,
      ok: false,
      message: '无法校验座位供应商（协议不完整）',
      params: { incomplete: true },
    }
    localeRef().value = 'en'
    expect(preflightCheckMessage(check)).toMatch(/protocol/i)
    localeRef().value = 'zh-CN'
    expect(preflightCheckMessage(check)).toContain('协议')
  })
})

describe('providerName', () => {
  it('translates known provider ids', () => {
    localeRef().value = 'en'
    expect(providerName('zhipu', '智谱 AI')).toBe('Zhipu AI')
    localeRef().value = 'zh-CN'
    expect(providerName('zhipu', '智谱 AI')).toBe('智谱 AI')
  })
})
