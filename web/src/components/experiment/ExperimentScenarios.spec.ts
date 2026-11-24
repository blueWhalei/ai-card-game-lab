/** @vitest-environment happy-dom */
import { afterEach, expect, it, vi } from 'vitest'
import { mount, enableAutoUnmount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter } from 'vue-router'
import { experimentApi, type ScenarioQuery, type ScenarioRecords } from '@/api/experimentApi'
import zhCN from '@/i18n/locales/zh-CN'
import en from '@/i18n/locales/en'
import ExperimentScenarios from './ExperimentScenarios.vue'

enableAutoUnmount(afterEach)
afterEach(() => vi.restoreAllMocks())
function fixture(id: string, q: ScenarioQuery): ScenarioRecords {
  const game = {
    id: 'g',
    status: 'running',
    created_at: '2026-11-07',
    decision_n: 2,
    evaluated_n: 1,
  }
  return {
    experiment_id: id,
    scope: 'current_records',
    read_at: '2026-11-07',
    endgame_max_hand: 8,
    scenario: q.scenario ?? null,
    totals: { decision_n: 2, game_n: 1, evaluated_n: 1, unrecorded_game_n: 1 },
    groups: ['bidding', 'playing', 'endgame', 'bomb'].map((scenario) => ({
      scenario: scenario as NonNullable<ScenarioQuery['scenario']>,
      decision_n: scenario === 'bomb' ? 2 : 0,
      game_n: scenario === 'bomb' ? 1 : 0,
      evaluated_n: scenario === 'bomb' ? 1 : 0,
    })),
    games: { items: [game], total: 1, page: q.game_page, page_size: 20 },
    selected_game: q.game_id ? game : null,
    decisions: {
      items: q.game_id
        ? ['d1', 'd2'].map((point, index) => ({
            id: point,
            game_id: 'g',
            round_number: index,
            player_id: 'p',
            game_phase: 'playing',
            hand_cards: ['S3'],
            chosen_action: { action_type: 'BOMB', cards: [] },
            action_id: 'BOMB||',
            ev_loss: index === 0 ? null : 0,
            evaluator_params: { candidates_evaluated: 2, legal_action_count: 4 },
            created_at: '2026-11-07',
          }))
        : [],
      total: q.game_id ? 2 : 0,
      page: q.page,
      page_size: 20,
    },
  }
}
const result = (id: string, q: ScenarioQuery) => ({ code: 0, message: '', data: fixture(id, q) })
async function setup(query = '', locale = 'zh-CN') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/experiments/:id', name: 'experiment-detail', component: { template: '<div />' } },
      { path: '/pipeline/decisions', name: 'decisions', component: { template: '<div />' } },
    ],
  })
  await router.push(`/experiments/a?panel=scenarios${query}`)
  const wrapper = mount(ExperimentScenarios, {
    props: { experimentId: 'a', configLabel: (id) => id },
    global: {
      plugins: [router, createI18n({ legacy: false, locale, messages: { 'zh-CN': zhCN, en } })],
    },
  })
  await flushPromises()
  return { wrapper, router }
}
it.each(['zh-CN', 'en'])(
  'shows scope, denominators and null versus zero evaluation in %s',
  async (locale) => {
    vi.spyOn(experimentApi, 'scenarios').mockImplementation(async (id, q) => result(id, q))
    const { wrapper, router } = await setup('&scenario=bomb&scenario_game=g', locale)
    expect(wrapper.text()).toContain(locale === 'en' ? 'not independent samples' : '不是独立样本数')
    expect(wrapper.text()).toContain(locale === 'en' ? 'not interpreted as zero' : '不按 0 解释')
    expect(wrapper.text()).not.toContain('scenarioRecords.')
    await router.replace(
      '/experiments/a?panel=scenarios&scenario=bomb&scenario_game=g&scenario_decision=d2',
    )
    await flushPromises()
    expect(wrapper.text()).toContain('0.00')
    const link = wrapper.get('a').attributes('href')!
    expect(link).toContain('scenario_decision=d2')
    expect(link).toContain('scenario_run=a')
    expect(link).toContain('game_id=g')
  },
)

it('navigates from group to game to decision and resets child selections on group changes', async () => {
  vi.spyOn(experimentApi, 'scenarios').mockImplementation(async (id, q) => result(id, q))
  const { wrapper, router } = await setup()
  await wrapper
    .findAll('button')
    .find((b) => b.text() === '炸弹 / 火箭动作')!
    .trigger('click')
  await flushPromises()
  await wrapper
    .findAll('button')
    .find((b) => b.text().includes('2 条决策'))!
    .trigger('click')
  await flushPromises()
  expect(router.currentRoute.value.query).toMatchObject({ scenario: 'bomb', scenario_game: 'g' })
  expect(wrapper.get('a').attributes('href')).toContain('scenario_decision=d1')
  await wrapper
    .findAll('button')
    .find((b) => b.text() === '叫地主决策')!
    .trigger('click')
  await flushPromises()
  expect(router.currentRoute.value.query).not.toHaveProperty('scenario_game')
  expect(wrapper.find('a').exists()).toBe(false)
})

it('ignores a late response from a previous run', async () => {
  let finish!: (value: ReturnType<typeof result>) => void
  vi.spyOn(experimentApi, 'scenarios').mockImplementation((id, q) =>
    id === 'a'
      ? new Promise((resolve) => {
          finish = resolve
        })
      : Promise.resolve(result(id, q)),
  )
  const { wrapper } = await setup()
  await wrapper.setProps({ experimentId: 'b' })
  await flushPromises()
  const stale = result('a', { game_page: 1, page: 1 })
  stale.data.totals.decision_n = 999
  finish(stale)
  await flushPromises()
  expect(wrapper.text()).not.toContain('999')
  expect(wrapper.find('[role="status"]').exists()).toBe(false)
})

it('reports unavailable selections and restores only after an explicit retry', async () => {
  vi.spyOn(experimentApi, 'scenarios')
    .mockRejectedValueOnce(new Error('deleted'))
    .mockImplementation(async (id, q) => result(id, q))
  const { wrapper } = await setup('&scenario=bomb&scenario_game=g&scenario_decision=d2')
  expect(wrapper.find('[role="alert"]').exists()).toBe(true)
  expect(wrapper.find('a').exists()).toBe(false)
  await wrapper
    .findAll('button')
    .find((b) => b.text() === '刷新当前记录')!
    .trigger('click')
  await flushPromises()
  expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  expect(wrapper.get('a').attributes('href')).toContain('scenario_decision=d2')
})

it('rejects invalid query state without fetching an unfiltered substitute', async () => {
  const call = vi.spyOn(experimentApi, 'scenarios')
  const { wrapper } = await setup('&scenario=invalid')
  expect(wrapper.find('[role="alert"]').exists()).toBe(true)
  expect(call).not.toHaveBeenCalled()
})
