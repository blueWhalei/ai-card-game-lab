/** @vitest-environment happy-dom */
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import zhCN from '@/i18n/locales/zh-CN'
import type { ReplayData } from '@/api/gameApi'
import GameReplayControls from './GameReplayControls.vue'

function setup(count: number, index = 0) {
  return mount(GameReplayControls, {
    props: {
      replayData: { rounds: Array.from({ length: count }, () => ({})), thinking: {} } as ReplayData,
      replayIndex: index,
      replayPlaying: false,
      replaySpeed: 1000,
    },
    global: {
      plugins: [createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })],
    },
  })
}

describe('replay navigation', () => {
  it('emits a numeric seek position and names the timeline and speed controls', async () => {
    const wrapper = setup(8)
    const slider = wrapper.get('input[type="range"]')
    expect(slider.attributes('aria-label')).toBe('回放位置')
    expect(slider.attributes('max')).toBe('7')
    await slider.setValue('5')
    expect(wrapper.emitted('seek')).toEqual([[5]])
    expect(wrapper.get('select').attributes('aria-label')).toBe('回放速度')
  })
  it('disables navigation for an empty replay and reports zero of zero', () => {
    const wrapper = setup(0)
    expect(wrapper.get('input').attributes('disabled')).toBeDefined()
    expect(
      wrapper.findAll('button').every((button) => button.attributes('disabled') !== undefined),
    ).toBe(true)
    expect(wrapper.text()).toContain('0 / 0')
  })
  it('disables next and play at the last position but keeps previous available', () => {
    const buttons = setup(3, 2).findAll('button')
    expect(buttons[0]?.attributes('disabled')).toBeUndefined()
    expect(buttons[1]?.attributes('disabled')).toBeDefined()
    expect(buttons[2]?.attributes('disabled')).toBeDefined()
  })
})
