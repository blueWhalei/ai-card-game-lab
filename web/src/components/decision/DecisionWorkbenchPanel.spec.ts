/** @vitest-environment happy-dom */
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, shallowMount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter } from 'vue-router'
import { decisionApi, type DecisionPoint, type DecisionStats } from '@/api/decision'
import { experimentConfigApi } from '@/api/experimentConfigApi'
import { systemApi } from '@/api/systemApi'
import zhCN from '@/i18n/locales/zh-CN'
import DecisionWorkbenchPanel from './DecisionWorkbenchPanel.vue'
import CompactRecordList from '@/components/common/CompactRecordList.vue'
import { restoredWorkspaceRoute, workspaceRoute } from '@/utils/workspaceRoute'

enableAutoUnmount(afterEach)
afterEach(() => vi.restoreAllMocks())
const point = (id: string, game = 'g'): DecisionPoint => ({
  id,
  game_id: game,
  player_id: 'p',
  round_number: 0,
  hand_cards: [],
  opponent_hands: null,
  last_action: null,
  game_phase: 'playing',
  chosen_action: { action_type: 'PASS', cards: [] },
  thinking: null,
  outcome: null,
  train_usable: false,
  ev_loss: null,
  created_at: '2026-11-07',
})
const list = (id: string, game = 'g') => ({
  code: 0,
  message: '',
  data: { items: [point(id, game)], total: 1, page: 1, page_size: 20 },
})
const stats = (total: number) => ({
  code: 0,
  message: '',
  data: { total, outcome_counts: {}, phase_counts: {}, evaluated_count: 0 } as DecisionStats,
})
beforeEach(() => {
  vi.spyOn(experimentConfigApi, 'list').mockResolvedValue({ code: 0, message: '', data: [] })
  vi.spyOn(systemApi, 'listEngines').mockResolvedValue({ code: 0, message: '', data: [] })
  vi.spyOn(decisionApi, 'list').mockResolvedValue(list('d'))
  vi.spyOn(decisionApi, 'stats').mockResolvedValue(stats(10))
})
async function setup(extra = '&decision_id=d') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/pipeline/decisions', name: 'decisions', component: { template: '<div />' } },
      { path: '/experiments/:id', name: 'experiment-detail', component: { template: '<div />' } },
      {
        path: '/research-reports/:id',
        name: 'research-report',
        component: { template: '<div />' },
      },
      { path: '/experiments/compare', component: { template: '<div />' } },
      { path: '/pipeline/puzzles', component: { template: '<div />' } },
    ],
  })
  await router.push(`/pipeline/decisions?experiment_id=a&game_id=g${extra}`)
  const wrapper = shallowMount(DecisionWorkbenchPanel, {
    global: {
      stubs: { RouterLink: false },
      plugins: [
        router,
        createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } }),
      ],
    },
  })
  await flushPromises()
  return { router, wrapper }
}

it('labels whole-run statistics explicitly even when the decision list is game-scoped', async () => {
  const { wrapper } = await setup()
  expect(decisionApi.stats).toHaveBeenCalledWith({ experiment_id: 'a' })
  expect(decisionApi.list).toHaveBeenCalledWith(
    expect.objectContaining({ experiment_id: 'a', game_id: 'g' }),
  )
  expect(wrapper.text()).toContain('运行整体统计（未应用列表筛选）')
})

it('returns to the original comparison scenario and step with report provenance', async () => {
  const { wrapper } = await setup(
    '&decision_id=d&comparison_id=cmp&compare_seed=7&compare_turn=3&compare_scenario=bomb&report_id=rev&evidence=original',
  )
  const link = wrapper
    .findAll('a')
    .find((item) => item.attributes('href')?.includes('/experiments/compare'))!
  expect(link.attributes('href')).toContain('scenario=bomb')
  expect(link.attributes('href')).toContain('turn=3')
  expect(link.attributes('href')).toContain('evidence=original')
})

it('preserves comparison filters in the actual desktop route allowlists', async () => {
  const appRouter = (await import('@/router')).default
  for (const path of [
    '/experiments/compare?snapshot=cmp&scenario=bomb&seed=7&turn=3',
    '/pipeline/decisions?comparison_id=cmp&compare_scenario=bomb&compare_seed=7&compare_turn=3&game_id=g&decision_id=d',
    '/pipeline/puzzles?pack_id=pack&result_id=run_12345678&result_page=2&report_id=rev&puzzle_evidence=pack%2Frun_12345678',
    '/pipeline/decisions?game_id=g&decision_id=d&puzzle_pack=pack&puzzle_result=run_12345678&puzzle_page=2&report_id=rev&puzzle_evidence=pack%2Frun_12345678',
    '/research-reports/rev?puzzle_evidence=pack%2Frun_12345678',
  ]) {
    const saved = workspaceRoute(appRouter, appRouter.resolve(path))!
    expect(appRouter.resolve(saved).query).toEqual(appRouter.resolve(path).query)
    expect(restoredWorkspaceRoute(appRouter, saved)).toBe(saved)
  }
})

it('keeps the source test-pack return link while browsing another decision', async () => {
  vi.mocked(decisionApi.list).mockResolvedValue({
    ...list('d'),
    data: { ...list('d').data, items: [point('d'), point('other')] },
  })
  const { wrapper } = await setup(
    '&decision_id=d&puzzle_pack=pack&puzzle_result=run_12345678&puzzle_page=2',
  )
  const link = () => wrapper.findAll('a').find((a) => a.text() === zhCN.puzzle.backToPack)!
  const destination = '/pipeline/puzzles?pack_id=pack&result_id=run_12345678&result_page=2'
  expect(link().attributes('href')).toBe(destination)
  wrapper.findComponent(CompactRecordList).vm.$emit('select', 'other')
  await flushPromises()
  expect(link().attributes('href')).toBe(destination)
})

it('keeps the original scenario return link and never substitutes a missing decision', async () => {
  vi.spyOn(decisionApi, 'get').mockRejectedValue(new Error('deleted'))
  const { wrapper } = await setup(
    '&decision_id=missing&scenario_run=a&scenario=bomb&scenario_game=g&scenario_decision=missing&scenario_games_page=2',
  )
  expect(wrapper.find('[role="alert"]').text()).toContain('未自动改选其他记录')
  expect(wrapper.findComponent(CompactRecordList).props('selectedId')).toBeNull()
  expect(wrapper.get('a').attributes('href')).toContain('scenario_games_page=2')
  expect(wrapper.get('a').attributes('href')).toContain('scenario_decision=missing')
})

it('does not overwrite a new scope with late list or statistics responses', async () => {
  let finishList!: (value: ReturnType<typeof list>) => void
  let finishStats!: (value: ReturnType<typeof stats>) => void
  vi.mocked(decisionApi.list).mockImplementation((params) =>
    params?.experiment_id === 'a'
      ? new Promise((resolve) => {
          finishList = resolve
        })
      : Promise.resolve(list('new', 'new-game')),
  )
  vi.mocked(decisionApi.stats).mockImplementation((params) =>
    params?.experiment_id === 'a'
      ? new Promise((resolve) => {
          finishStats = resolve
        })
      : Promise.resolve(stats(2)),
  )
  const { router, wrapper } = await setup('')
  await router.push('/pipeline/decisions?experiment_id=b&game_id=new-game')
  await flushPromises()
  finishList(list('old'))
  finishStats(stats(999))
  await flushPromises()
  expect(wrapper.findComponent(CompactRecordList).props('selectedId')).toBe('new')
  expect(wrapper.text()).not.toContain('999')
})

it('rejects a detail response for another game instead of showing its evidence', async () => {
  vi.spyOn(decisionApi, 'get').mockResolvedValue({
    code: 0,
    message: '',
    data: point('wanted', 'foreign'),
  })
  const { wrapper } = await setup('&decision_id=wanted')
  expect(wrapper.find('[role="alert"]').exists()).toBe(true)
  expect(wrapper.findComponent(CompactRecordList).props('selectedId')).toBeNull()
})
