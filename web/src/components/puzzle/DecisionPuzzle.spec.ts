/** @vitest-environment happy-dom */
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, shallowMount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createI18n } from 'vue-i18n'
import { puzzleApi, type DecisionPuzzleSource, type PuzzlePackSummary } from '@/api/puzzleApi'
import zhCN from '@/i18n/locales/zh-CN'
import en from '@/i18n/locales/en'
import DecisionPuzzle from './DecisionPuzzle.vue'

enableAutoUnmount(afterEach)
afterEach(() => vi.restoreAllMocks())
const source: DecisionPuzzleSource = {
  experiment_id: 'run',
  experiment_name: 'Source run',
  game_id: 'game',
  decision_point_id: 'decision',
  decision_created_at: '2026-11-08',
  round_num: 5,
  player_id: 'p1',
  game_phase: 'playing',
  deal_seed: 42,
  read_at: '2026-11-08',
  source_hash: 'a'.repeat(64),
  candidates_evaluated: 2,
  legal_action_count: 8,
  evaluator_params: {},
}
const response = <T>(data: T) => ({ code: 0, message: '', data })
beforeEach(() => {
  vi.spyOn(puzzleApi, 'decisionSource').mockResolvedValue(response(source))
  vi.spyOn(puzzleApi, 'fromDecision').mockResolvedValue(
    response({ pack_id: 'saved' } as PuzzlePackSummary),
  )
})
async function setup(locale = 'zh-CN') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/pipeline/puzzles', component: { template: '<div />' } },
    ],
  })
  await router.push('/')
  const wrapper = shallowMount(DecisionPuzzle, {
    props: { decisionId: 'decision' },
    global: {
      plugins: [router, createI18n({ legacy: false, locale, messages: { 'zh-CN': zhCN, en } })],
      stubs: {
        UiButton: {
          props: ['disabled'],
          template: '<button :disabled="disabled"><slot /></button>',
        },
        UiDialog: { props: ['open'], template: '<div v-if="open"><slot /></div>' },
      },
    },
  })
  return { wrapper, router }
}

it.each(['zh-CN', 'en'])(
  'saves an explicit question with inspected source in %s',
  async (locale) => {
    const { wrapper, router } = await setup(locale)
    expect(puzzleApi.decisionSource).not.toHaveBeenCalled()
    await wrapper.get('button').trigger('click')
    await flushPromises()
    const labels = locale === 'en' ? en.puzzle : zhCN.puzzle
    expect(wrapper.text()).toContain(labels.targetScope)
    expect(wrapper.text()).toContain('2/8')
    const save = () => wrapper.findAll('button').find((b) => b.text() === labels.saveTarget)!
    expect(save().attributes('disabled')).toBeDefined()
    await wrapper.get('textarea').setValue('  Does order matter? ')
    expect(puzzleApi.fromDecision).not.toHaveBeenCalled()
    await save().trigger('click')
    await flushPromises()
    expect(puzzleApi.fromDecision).toHaveBeenCalledWith({
      decision_id: 'decision',
      question: 'Does order matter?',
      expected_source_hash: source.source_hash,
    })
    expect(router.currentRoute.value.fullPath).toBe('/pipeline/puzzles?pack_id=saved')
  },
)

it('requires reinspection after a source change and keeps the question', async () => {
  const { wrapper, router } = await setup()
  await wrapper.get('button').trigger('click')
  await flushPromises()
  await wrapper.get('textarea').setValue('Question')
  vi.mocked(puzzleApi.fromDecision).mockRejectedValue({
    code: 'PUZZLE_SOURCE_CHANGED',
    message: 'changed',
  })
  await wrapper
    .findAll('button')
    .find((b) => b.text() === zhCN.puzzle.saveTarget)!
    .trigger('click')
  await flushPromises()
  expect(wrapper.get('[role="alert"]').text()).toBe(zhCN.puzzle.sourceChanged)
  expect(wrapper.get('textarea').element.value).toBe('Question')
  expect(router.currentRoute.value.path).toBe('/')
  expect(
    wrapper
      .findAll('button')
      .find((b) => b.text() === zhCN.puzzle.saveTarget)!
      .attributes('disabled'),
  ).toBeDefined()
  await wrapper
    .findAll('button')
    .find((b) => b.text() === zhCN.puzzle.recheckSource)!
    .trigger('click')
  await flushPromises()
  expect(puzzleApi.decisionSource).toHaveBeenCalledTimes(2)
})

it('discards a late source when the selected decision changes', async () => {
  let finish!: (value: ReturnType<typeof response<DecisionPuzzleSource>>) => void
  vi.mocked(puzzleApi.decisionSource).mockReturnValue(
    new Promise((resolve) => {
      finish = resolve
    }),
  )
  const { wrapper } = await setup()
  await wrapper.get('button').trigger('click')
  await wrapper.setProps({ decisionId: 'other' })
  finish(response(source))
  await flushPromises()
  expect(wrapper.text()).not.toContain('Source run')
  expect(puzzleApi.fromDecision).not.toHaveBeenCalled()
})

it('shows unavailable evidence without a substitute', async () => {
  vi.mocked(puzzleApi.decisionSource).mockRejectedValue({ code: 'PUZZLE_SOURCE_INVALID' })
  const { wrapper } = await setup()
  await wrapper.get('button').trigger('click')
  await flushPromises()
  expect(wrapper.get('[role="alert"]').text()).toBe(zhCN.puzzle.sourceInvalid)
  expect(puzzleApi.fromDecision).not.toHaveBeenCalled()
})
