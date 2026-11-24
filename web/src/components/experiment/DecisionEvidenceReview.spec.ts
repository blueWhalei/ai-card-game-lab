/** @vitest-environment happy-dom */
import { afterEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, shallowMount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter } from 'vue-router'
import zhCN from '@/i18n/locales/zh-CN'
import { researchApi, type DecisionEvidencePreview } from '@/api/researchApi'
import DecisionEvidenceReview from './DecisionEvidenceReview.vue'
import EvidenceCiteButton from './EvidenceCiteButton.vue'
import DecisionPreview from './DecisionPreview.vue'

enableAutoUnmount(afterEach)
afterEach(() => vi.restoreAllMocks())
const preview = (id: string) => ({
  code: 0,
  message: '',
  data: {
    comparison_id: 'cmp',
    seed: 42,
    decision: {
      id,
      player_id: 'p',
      game_id: 'g',
      game_phase: 'playing',
      opponent_hands: {},
      last_action: null,
      action_id: 'PASS||',
      ev_loss: null,
      annotation: null,
      round_number: 2,
      hand_cards: ['S3'],
      chosen_action: { action_type: 'PASS', cards: [] },
    },
  } as DecisionEvidencePreview,
})
async function setup() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: { template: '<div />' } }],
  })
  await router.push('/?review_decision=d&seed=42&turn=2&report_id=rev&evidence=original')
  const wrapper = shallowMount(DecisionEvidenceReview, {
    props: { comparisonId: 'cmp', included: [], disabled: false },
    global: {
      plugins: [
        router,
        createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } }),
      ],
      renderStubDefaultSlot: true,
    },
  })
  await flushPromises()
  return { wrapper, router }
}
it('only adds the reviewed source after an explicit action and preserves the return location', async () => {
  vi.spyOn(researchApi, 'decision').mockResolvedValue(preview('d'))
  const { wrapper, router } = await setup()
  expect(wrapper.emitted('cite')).toBeUndefined()
  expect(wrapper.findComponent(DecisionPreview).props('point')).toMatchObject({ id: 'd' })
  wrapper.findComponent(EvidenceCiteButton).vm.$emit('cite', ['d'])
  await flushPromises()
  expect(wrapper.emitted('cite')).toEqual([[['d']]])
  expect(router.currentRoute.value.query).toEqual({
    seed: '42',
    turn: '2',
    report_id: 'rev',
    evidence: 'original',
  })
})
it('clears old content during changes and ignores late source responses', async () => {
  let resolve!: (value: ReturnType<typeof preview>) => void
  vi.spyOn(researchApi, 'decision').mockImplementation((_cmp, id) =>
    id === 'd'
      ? new Promise((r) => {
          resolve = r
        })
      : Promise.resolve(preview('next')),
  )
  const { wrapper, router } = await setup()
  await router.replace('/?review_decision=next')
  await flushPromises()
  resolve(preview('d'))
  await flushPromises()
  expect(wrapper.findComponent(DecisionPreview).props('point')).toMatchObject({ id: 'next' })
  expect(wrapper.emitted('cite')).toBeUndefined()
})
it('does not offer citation when scope validation fails', async () => {
  vi.spyOn(researchApi, 'decision').mockRejectedValue(new Error('Outside frozen cohort'))
  const { wrapper } = await setup()
  expect(wrapper.findComponent(EvidenceCiteButton).exists()).toBe(false)
  expect(wrapper.find('[role="alert"]').exists()).toBe(true)
})
it('blocks a full draft without adding part of the request', async () => {
  vi.spyOn(researchApi, 'decision').mockResolvedValue(preview('d'))
  const { wrapper } = await setup()
  await wrapper.setProps({ included: Array.from({ length: 30 }, (_, i) => `existing-${i}`) })
  expect(wrapper.findComponent(EvidenceCiteButton).props('disabled')).toBe(true)
  wrapper.findComponent(EvidenceCiteButton).vm.$emit('cite', ['d'])
  expect(wrapper.emitted('cite')).toBeUndefined()
})
