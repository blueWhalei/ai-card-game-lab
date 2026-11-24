/** @vitest-environment happy-dom */
import { afterEach, expect, it } from 'vitest'
import { enableAutoUnmount, shallowMount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import zhCN from '@/i18n/locales/zh-CN'
import en from '@/i18n/locales/en'
import type { DecisionBoards, PairedDecision } from '@/api/researchApi'
import ComparisonBoard from './ComparisonBoard.vue'
import GenericBoard from '@/components/game/GenericBoard.vue'

enableAutoUnmount(afterEach)
const point = { id: 'd', player_id: 'a', round_number: 2 } as PairedDecision
const boards: DecisionBoards = {
  status: 'verified',
  stopped_at: null,
  frames: {
    2: {
      decision_id: 'd',
      snapshot: {
        game_type: 'doudizhu',
        phase: 'playing',
        round: 2,
        current_player_id: 'a',
        players: [
          { id: 'a', is_active: true, hand_count: 1, hand_cards: ['S3'] },
          { id: 'b', is_active: false, hand_count: 1, hand_cards: ['H4'] },
        ],
      },
    },
  },
}
it.each(['zh-CN', 'en'])(
  'hides opponents by default and never attaches a different source (%s)',
  async (locale) => {
    const wrapper = shallowMount(ComparisonBoard, {
      props: { point, boards, showAll: false, playerNames: {} },
      global: {
        plugins: [createI18n({ legacy: false, locale, messages: { 'zh-CN': zhCN, en } })],
      },
    })
    expect(
      wrapper.findComponent(GenericBoard).props('snapshot')?.players[1]?.hand_cards,
    ).toBeUndefined()
    expect(wrapper.findComponent(GenericBoard).props('snapshot')?.players[0]?.hand_cards).toEqual([
      'S3',
    ])
    await wrapper.setProps({ showAll: true })
    expect(wrapper.findComponent(GenericBoard).props('snapshot')?.players[1]?.hand_cards).toEqual([
      'H4',
    ])
    await wrapper.setProps({ point: { ...point, id: 'other' } })
    expect(wrapper.findComponent(GenericBoard).exists()).toBe(false)
    expect(wrapper.text()).toContain(locale === 'en' ? 'No board was reconstructed' : '未重建牌桌')
    await wrapper.setProps({ point: { ...point, round_number: 3 } })
    expect(wrapper.findComponent(GenericBoard).exists()).toBe(false)
  },
)
