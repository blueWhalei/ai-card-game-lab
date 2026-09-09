/**
 * @vitest-environment happy-dom
 */
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import zhCN from '@/i18n/locales/zh-CN'
import StageAction from './StageAction.vue'

function mountAction(props: Record<string, unknown>) {
  const i18n = createI18n({
    legacy: false,
    locale: 'zh-CN',
    missingWarn: false,
    fallbackWarn: false,
    messages: { 'zh-CN': zhCN },
  })
  return mount(StageAction, {
    props: { claim: 'collecting', ...props },
    global: { plugins: [i18n] },
  })
}

describe('StageAction progress display', () => {
  it('never shows an uncapped ratio like 14/10', () => {
    const wrapper = mountAction({
      metricValue: 14,
      metricTotal: 10,
      metricLabel: 'games',
    })
    const number = wrapper.get('.ink-verdict-number')
    expect(number.text().replace(/\s+/g, ' ')).toContain('10 / 10')
    expect(number.text()).not.toMatch(/14\s*\/\s*10/)
    expect(wrapper.text()).toMatch(/多跑了|beyond|extra|\+?\s*4/)
  })

  it('keeps an on-target ratio as finished/target', () => {
    const wrapper = mountAction({
      metricValue: 5,
      metricTotal: 5,
    })
    expect(wrapper.get('.ink-verdict-number').text().replace(/\s+/g, ' ')).toContain('5 / 5')
  })
})
