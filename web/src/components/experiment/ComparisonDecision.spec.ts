/** @vitest-environment happy-dom */
import { afterEach, expect, it, vi } from 'vitest'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { decisionApi, type DecisionPoint } from '@/api/decision'
import type { EvidenceCandidate } from '@/api/researchApi'
import DecisionPreview from './DecisionPreview.vue'
import zhCN from '@/i18n/locales/zh-CN'
import ComparisonDecision from './ComparisonDecision.vue'

afterEach(() => vi.restoreAllMocks())
const a = { id: 'a', game_id: 'g-a', player_id: 'p', round_number: 1 } as EvidenceCandidate
const b = { ...a, id: 'b', game_id: 'g-b', round_number: 2 }
function mountPreview() {
  return shallowMount(ComparisonDecision, {
    props: { candidate: a },
    global: {
      plugins: [createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })],
    },
  })
}
function response(candidate: EvidenceCandidate, cards: string[]) {
  return {
    code: 0,
    message: 'success',
    data: {
      ...candidate,
      hand_cards: cards,
      chosen_action: { action_type: 'SINGLE', cards },
    } as unknown as DecisionPoint,
  }
}

it('ignores late responses from a previously selected decision', async () => {
  let resolveFirst!: (value: ReturnType<typeof response>) => void
  vi.spyOn(decisionApi, 'get')
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveFirst = resolve
        }),
    )
    .mockResolvedValueOnce(response(b, ['H8']))
  const wrapper = mountPreview()
  await wrapper.setProps({ candidate: b })
  await flushPromises()
  resolveFirst(response(a, ['SQ']))
  await flushPromises()
  expect(wrapper.findComponent(DecisionPreview).props('point').chosen_action.cards).toEqual(['H8'])
  expect(wrapper.find('[aria-busy]').attributes('aria-busy')).toBe('false')
  wrapper.unmount()
})

it('rejects a mismatched record instead of presenting it as the selected evidence', async () => {
  vi.spyOn(decisionApi, 'get').mockResolvedValue(response(b, ['H8']))
  const wrapper = mountPreview()
  await flushPromises()
  expect(wrapper.find('[role="alert"]').exists()).toBe(true)
  expect(wrapper.findComponent(DecisionPreview).exists()).toBe(false)
  wrapper.unmount()
})
