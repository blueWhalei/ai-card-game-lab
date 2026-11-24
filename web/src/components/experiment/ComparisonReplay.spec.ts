/** @vitest-environment happy-dom */
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, shallowMount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter, RouterLink } from 'vue-router'
import {
  researchApi,
  type DecisionPair,
  type DecisionPairList,
  type PairedDecision,
} from '@/api/researchApi'
import type { ExperimentScenarioId } from '@/utils/experimentWorkbench'
import zhCN from '@/i18n/locales/zh-CN'
import UiButton from '@/components/ui/Button.vue'
import DecisionPreview from './DecisionPreview.vue'
import ComparisonReplay from './ComparisonReplay.vue'
import en from '@/i18n/locales/en'

enableAutoUnmount(afterEach)
afterEach(() => vi.restoreAllMocks())
function pair(seed = 7): DecisionPair {
  const point = (side: string, turn: number): PairedDecision => ({
    id: `${side}-${seed}-${turn}`,
    game_id: side,
    player_id: side,
    round_number: turn,
    game_phase: 'bidding',
    hand_cards: ['S3'],
    opponent_hands: {},
    last_action: null,
    action_id: 'BID||1',
    chosen_action: { action_type: 'BID', cards: [] },
  })
  return {
    boards: {
      cutoff: '2026-01-01',
      read_at: '2026-02-01',
      engine_version: '1',
      left: { frames: {}, status: 'unverified', stopped_at: 0 },
      right: { frames: {}, status: 'unverified', stopped_at: 0 },
    },
    scenario: null,
    matching_turns: [0, 1, 2],
    seed,
    left: { experiment_id: 'a', game_id: 'a', name: 'Run A' },
    right: { experiment_id: 'b', game_id: 'b', name: 'Run B' },
    first_divergence: 1,
    frames: [0, 1, 2].map((turn) => ({
      turn,
      status: turn === 0 ? 'same' : turn === 1 ? 'divergence' : 'unverified',
      reasons: [],
      left: turn === 2 ? null : point('a', turn),
      right: point('b', turn),
      left_ended: turn === 2,
      right_ended: false,
      left_scenario: turn === 2 ? null : 'bidding',
      right_scenario: 'bidding',
    })),
  }
}
beforeEach(() => {
  vi.spyOn(researchApi, 'pairs').mockResolvedValue({
    data: {
      comparison_id: 'cmp',
      scenario: null,
      cutoff: '2026-01-01',
      read_at: '2026-02-01',
      endgame_max_hand: 8,
      cohort_n: 2,
      groups: [
        { scenario: null, left_n: 4, right_n: 6, left_game_n: 2, right_game_n: 2, pair_n: 2 },
      ],
      runs: [
        { id: 'a', name: 'A' },
        { id: 'b', name: 'B' },
      ],
      items: [7, 8].map((seed) => ({
        seed,
        left_game_id: 'a',
        right_game_id: 'b',
        left_n: 2,
        right_n: 3,
      })),
    },
  } as never)
})
async function mountReplay(query = '', locale = 'zh-CN') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/experiments/compare', component: { template: '<div />' } },
      { path: '/pipeline/decisions', component: { template: '<div />' } },
    ],
  })
  await router.push(`/experiments/compare?snapshot=cmp${query}`)
  const wrapper = shallowMount(ComparisonReplay, {
    props: { comparisonId: 'cmp', playerNames: {}, citationDisabled: false },
    global: {
      plugins: [router, createI18n({ legacy: false, locale, messages: { 'zh-CN': zhCN, en } })],
      renderStubDefaultSlot: true,
      stubs: { EvidenceCiteButton: false },
    },
  })
  await flushPromises()
  return { wrapper, router }
}
it('moves both sides, cites the visible pair, and leaves ended sides empty', async () => {
  vi.spyOn(researchApi, 'pair').mockResolvedValue({ data: pair() } as never)
  const { wrapper, router } = await mountReplay()
  await wrapper
    .findAllComponents(UiButton)
    .find((b) => b.text().includes('首次行动分歧'))!
    .trigger('click')
  await flushPromises()
  expect(wrapper.findAllComponents(DecisionPreview).map((p) => p.props('point'))).toMatchObject([
    { id: 'a-7-1' },
    { id: 'b-7-1' },
  ])
  expect(router.currentRoute.value.query.turn).toBe('1')
  await wrapper
    .findAllComponents(UiButton)
    .find((b) => b.text() === '引用当前对照')!
    .trigger('click')
  expect(wrapper.emitted('cite')).toEqual([[['a-7-1', 'b-7-1']]])
  await wrapper
    .findAllComponents(UiButton)
    .find((b) => b.text() === '下一步')!
    .trigger('click')
  expect(wrapper.text()).toContain('这一侧的对局已结束')
  expect(wrapper.findAllComponents(DecisionPreview)).toHaveLength(1)
})
it('restores seed and turn, including the return context on the decision link', async () => {
  vi.spyOn(researchApi, 'pair').mockResolvedValue({ data: pair(8) } as never)
  const { wrapper } = await mountReplay('&seed=8&turn=1&report_id=rev&evidence=cited-origin')
  expect(researchApi.pair).toHaveBeenCalledWith('cmp', 8, undefined)
  expect(wrapper.findComponent(RouterLink).props('to')).toMatchObject({
    query: {
      decision_id: 'a-8-1',
      compare_seed: '8',
      compare_turn: '1',
      report_id: 'rev',
      evidence: 'cited-origin',
    },
  })
})
it('ignores the late response from the previous deal', async () => {
  let complete!: (value: never) => void
  vi.spyOn(researchApi, 'pair')
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          complete = resolve
        }),
    )
    .mockResolvedValueOnce({ data: pair(8) } as never)
  const { wrapper } = await mountReplay()
  await wrapper.findAll('select')[1]!.setValue('8')
  await flushPromises()
  complete({ data: pair(7) } as never)
  await flushPromises()
  expect(wrapper.findComponent(DecisionPreview).props('point')).toMatchObject({ id: 'a-8-0' })
  expect(wrapper.attributes('aria-busy')).toBe('false')
})
it('clears previous cards when the next deal cannot be verified and supports retry', async () => {
  vi.spyOn(researchApi, 'pair')
    .mockResolvedValueOnce({ data: pair() } as never)
    .mockRejectedValueOnce({ code: 'RESEARCH_INVALID', message: 'Identity changed' })
    .mockResolvedValueOnce({ data: pair(8) } as never)
  const { wrapper } = await mountReplay()
  await wrapper.findAll('select')[1]!.setValue('8')
  await flushPromises()
  expect(wrapper.find('[role="alert"]').text()).toContain('Identity changed')
  expect(wrapper.findComponent(DecisionPreview).exists()).toBe(false)
  await wrapper.findComponent(UiButton).trigger('click')
  await flushPromises()
  expect(wrapper.findComponent(DecisionPreview).props('point')).toMatchObject({ id: 'a-8-0' })
})

function scenarioList(scenario: ExperimentScenarioId) {
  const data: DecisionPairList = {
    comparison_id: 'cmp',
    scenario,
    cutoff: '2026-01-01',
    read_at: '2026-02-01',
    endgame_max_hand: 8,
    cohort_n: 2,
    runs: [
      { id: 'a', name: 'A' },
      { id: 'b', name: 'B' },
    ],
    items: [{ seed: 7, left_game_id: 'a', right_game_id: 'b', left_n: 1, right_n: 0 }],
    groups: [{ scenario, left_n: 1, right_n: 0, left_game_n: 1, right_game_n: 0, pair_n: 1 }],
  }
  return { code: 0, message: '', data }
}
function scenarioPair(scenario: ExperimentScenarioId) {
  const data = pair()
  data.scenario = scenario
  data.matching_turns = [1]
  data.frames[1]!.left_scenario = scenario
  return { code: 0, message: '', data }
}
it.each(['zh-CN', 'en'])(
  'locates a one-sided scenario while retaining context and return provenance in %s',
  async (locale) => {
    vi.mocked(researchApi.pairs).mockImplementation(async (_id, scenario) =>
      scenarioList(scenario!),
    )
    vi.spyOn(researchApi, 'pair').mockImplementation(async (_id, _seed, scenario) =>
      scenarioPair(scenario!),
    )
    const { wrapper, router } = await mountReplay(
      '&scenario=bomb&report_id=rev&evidence=original',
      locale,
    )
    expect(router.currentRoute.value.query.turn).toBe('1')
    expect(wrapper.findAllComponents(DecisionPreview)).toHaveLength(2)
    expect(wrapper.text()).toContain(locale === 'en' ? 'Context only' : '上下文记录')
    expect(wrapper.text()).toContain(
      locale === 'en' ? 'Decisions in the selected scope: A 1, B 0' : 'A 1 条决策，B 0 条决策',
    )
    expect(wrapper.findComponent(RouterLink).props('to')).toMatchObject({
      query: {
        compare_scenario: 'bomb',
        compare_turn: '1',
        report_id: 'rev',
        evidence: 'original',
        experiment_id: 'a',
      },
    })
    await wrapper
      .findAllComponents(UiButton)
      .find((b) => b.text() === (locale === 'en' ? 'Previous step' : '上一步'))!
      .trigger('click')
    expect(wrapper.findComponent(DecisionPreview).props('point')).toMatchObject({ id: 'a-7-0' })
    await wrapper
      .findAllComponents(UiButton)
      .find((b) => b.text() === (locale === 'en' ? 'Next matching step' : '下一个匹配步骤'))!
      .trigger('click')
    expect(wrapper.findComponent(DecisionPreview).props('point')).toMatchObject({ id: 'a-7-1' })
  },
)

it('clears the previous selection on a scenario change and ignores late filtered responses', async () => {
  vi.spyOn(researchApi, 'pair').mockImplementation(async (_id, _seed, scenario) =>
    scenario ? scenarioPair(scenario) : { code: 0, message: '', data: pair(_seed) },
  )
  const { wrapper } = await mountReplay('&seed=8&turn=1')
  let finish!: (value: ReturnType<typeof scenarioList>) => void
  vi.mocked(researchApi.pairs).mockImplementation((_id, scenario) =>
    scenario === 'bomb'
      ? new Promise((resolve) => {
          finish = resolve
        })
      : Promise.resolve(scenarioList('bidding')),
  )
  await wrapper.findAll('select')[0]!.setValue('bomb')
  await flushPromises()
  expect(wrapper.findComponent(DecisionPreview).exists()).toBe(false)
  await wrapper.findAll('select')[0]!.setValue('bidding')
  await flushPromises()
  finish(scenarioList('bomb'))
  await flushPromises()
  expect(wrapper.findComponent(RouterLink).props('to')).toMatchObject({
    query: { compare_scenario: 'bidding', compare_seed: '7' },
  })
  expect(wrapper.attributes('aria-busy')).toBe('false')
})

it.each([
  '&scenario=unknown',
  '&scenario=bomb&scenario=bidding',
  '&seed=99',
  '&seed=bad',
  '&turn=1',
  '&seed=7&turn=99',
  '&seed=7&turn=bad',
])('does not substitute another decision for invalid position %s', async (query) => {
  vi.spyOn(researchApi, 'pair').mockResolvedValue({ code: 0, message: '', data: pair() })
  const { wrapper, router } = await mountReplay(query)
  expect(wrapper.find('[role="alert"]').text()).toContain('未自动改选其他记录')
  expect(wrapper.findComponent(DecisionPreview).exists()).toBe(false)
  expect(router.currentRoute.value.fullPath).toContain(query)
  await wrapper
    .findAllComponents(UiButton)
    .find((b) => b.text() === '重新选择对局')!
    .trigger('click')
  await flushPromises()
  expect(wrapper.findComponent(DecisionPreview).exists()).toBe(true)
})

it('shows an empty scenario without loading an unrelated pair', async () => {
  const empty = scenarioList('playing')
  empty.data.items = []
  vi.mocked(researchApi.pairs).mockResolvedValue(empty)
  const load = vi.spyOn(researchApi, 'pair')
  const { wrapper } = await mountReplay('&scenario=playing')
  expect(wrapper.text()).toContain('没有该场景记录，不能据此判断表现')
  expect(load).not.toHaveBeenCalled()
})
