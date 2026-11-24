/** @vitest-environment happy-dom */
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter } from 'vue-router'
import { puzzleApi, type PuzzleResult } from '@/api/puzzleApi'
import { downloadJson } from '@/utils/jsonFile'
import { downloadText } from '@/utils/exportFile'
import { reportHtml } from '@/utils/researchReport'
import zhCN from '@/i18n/locales/zh-CN'
import en from '@/i18n/locales/en'
import PuzzleResults from './PuzzleResults.vue'
import PuzzleResultDocument from './PuzzleResultDocument.vue'

vi.mock('@/utils/jsonFile', () => ({ downloadJson: vi.fn().mockResolvedValue(true) }))
vi.mock('@/utils/exportFile', () => ({ downloadText: vi.fn().mockResolvedValue(true) }))
enableAutoUnmount(afterEach)
afterEach(() => vi.restoreAllMocks())
function fixture(runId = 'run_12345678', packId = 'pack'): PuzzleResult {
  return {
    report: {
      run_id: runId,
      pack_id: packId,
      metric_version: 'puzzle-scoring-v2',
      baseline_kind: 'first',
      seed: 7,
      created_at: '2026-11-08T00:00:00+00:00',
      summary: {
        n: 1,
        evaluated_n: 0,
        unevaluated_n: 1,
        accuracy: null,
        mean_ev_loss: null,
        truncated_n: 1,
      },
      puzzles: [
        {
          puzzle_id: 'position',
          chosen_action_id: 'unscored',
          best_action_id: 'a',
          hit: null,
          ev_loss: null,
          truncated: true,
        },
      ],
    },
    source_status: 'unrecorded',
    read_at: '2026-11-08T01:00:00+00:00',
    report_hash: 'f'.repeat(64),
  }
}
const response = <T>(data: T) => ({ code: 0, message: '', data })
const list = () =>
  response({
    items: [
      {
        run_id: 'run_12345678',
        kind: 'run' as const,
        status: 'available' as const,
        created_at: '2026-11-08T00:00:00+00:00',
        baseline_kind: 'first' as const,
      },
    ],
    page: 1,
    page_size: 20,
    total: 1,
    read_at: '',
  })
beforeEach(() => {
  vi.spyOn(puzzleApi, 'results').mockResolvedValue(list())
  vi.spyOn(puzzleApi, 'result').mockResolvedValue(response(fixture()))
  vi.spyOn(puzzleApi, 'run')
  vi.spyOn(puzzleApi, 'probe')
})
async function setup(query = '?pack_id=pack&result_id=run_12345678&result_page=2') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/pipeline/puzzles', component: { template: '<div />' } },
      { path: '/pipeline/decisions', component: { template: '<div />' } },
    ],
  })
  await router.push('/pipeline/puzzles' + query)
  const wrapper = mount(PuzzleResults, {
    props: { packId: 'pack' },
    global: {
      plugins: [
        router,
        createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } }),
      ],
      stubs: {
        UiButton: {
          props: ['disabled'],
          template: '<button :disabled="disabled"><slot /></button>',
        },
        UiPagination: true,
      },
    },
  })
  await flushPromises()
  return { wrapper, router }
}

it.each(['zh-CN', 'en'])(
  'renders unscored historical results and source limits in %s',
  async (locale) => {
    const wrapper = mount(PuzzleResultDocument, {
      props: { result: fixture(), page: 2 },
      global: {
        plugins: [createI18n({ legacy: false, locale, messages: { 'zh-CN': zhCN, en } })],
        stubs: { RouterLink: true },
      },
    })
    const messages = locale === 'zh-CN' ? zhCN : en
    expect(wrapper.text()).toContain('0/1')
    expect(wrapper.text()).toContain(messages.puzzle.unevaluated)
    expect(wrapper.text()).toContain(messages.puzzleHistory.sourceStatus.unrecorded)
    expect(wrapper.text()).toContain(messages.puzzleHistory.scope)
    expect(wrapper.text()).not.toContain('0.000')
  },
)

it('reads a deep-linked record and exports the displayed result without rerunning policies', async () => {
  const { wrapper, router } = await setup()
  expect(puzzleApi.results).toHaveBeenCalledWith('pack', 2)
  expect(puzzleApi.result).toHaveBeenCalledWith('pack', 'run_12345678')
  expect(wrapper.findComponent(PuzzleResultDocument).props('result')).toEqual(fixture())
  await wrapper
    .findAll('button')
    .find((b) => b.text() === zhCN.report.json)!
    .trigger('click')
  await flushPromises()
  expect(downloadJson).toHaveBeenCalledWith('position-test-run_12345678.json', fixture())
  await wrapper
    .findAll('button')
    .find((b) => b.text() === zhCN.report.html)!
    .trigger('click')
  await flushPromises()
  const html = vi.mocked(downloadText).mock.calls.at(-1)![1]
  expect(html).toContain(zhCN.puzzleHistory.sourceStatus.unrecorded)
  expect(html).toContain('0/1')
  expect(html).not.toContain('/pipeline/decisions')
  expect(router.currentRoute.value.query.result_id).toBe('run_12345678')
  expect(puzzleApi.run).not.toHaveBeenCalled()
  expect(puzzleApi.probe).not.toHaveBeenCalled()
})

it('keeps frozen source text, escapes HTML and preserves exact result in the decision return link', async () => {
  const result = fixture()
  result.source_status = 'changed'
  result.report.pack_fingerprint = 'a'.repeat(64)
  result.report.pack_snapshot = {
    manifest: {
      pack_id: 'pack',
      created_at: '',
      game_type: 'doudizhu',
      source_experiment_id: 'run',
      puzzle_count: 1,
      notes: '',
      kind: 'cardlab.puzzle_pack',
      schema_version: 1,
      extract: { method: 'decision_record', question: '<script>untrusted()</script>', source: {} },
    },
    puzzles: [
      {
        puzzle_id: 'position',
        source: { game_id: 'game', decision_point_id: 'decision' },
        evaluator_params: { determinizations: 4 },
        candidates_evaluated: 2,
        legal_action_count: 4,
      },
    ],
  }
  vi.mocked(puzzleApi.result).mockResolvedValue(response(result))
  const { wrapper } = await setup()
  const document = wrapper.get('.research-report')
  expect(document.text()).toContain(zhCN.puzzleHistory.sourceStatus.changed)
  const link = wrapper.findAll('a').find((a) => a.text() === zhCN.puzzle.sourceDecision)!
  expect(link.attributes('href')).toContain('puzzle_result=run_12345678')
  expect(link.attributes('href')).toContain('puzzle_page=2')
  const html = reportHtml(document.element as HTMLElement, '<unsafe>', 'zh-CN')
  expect(html).toContain('&lt;script&gt;untrusted()&lt;/script&gt;')
  expect(html).not.toContain('<script>')
  expect(html).not.toContain('puzzle_result=')
})

it('does not substitute another record when a selected result is missing', async () => {
  vi.mocked(puzzleApi.result).mockRejectedValue({ code: 'PUZZLE_RESULT_NOT_FOUND' })
  const { wrapper, router } = await setup()
  expect(wrapper.get('[role="alert"]').text()).toBe(zhCN.puzzleHistory.resultFailed)
  expect(wrapper.findComponent(PuzzleResultDocument).exists()).toBe(false)
  expect(router.currentRoute.value.query.result_id).toBe('run_12345678')
  expect(puzzleApi.result).toHaveBeenCalledTimes(1)
})

it('discards a late record after navigation to another test', async () => {
  let finish!: (value: ReturnType<typeof response<PuzzleResult>>) => void
  vi.mocked(puzzleApi.result).mockImplementation((_pack, id) =>
    id === 'run_12345678'
      ? new Promise((resolve) => {
          finish = resolve
        })
      : Promise.resolve(response(fixture(id))),
  )
  const { wrapper, router } = await setup()
  await router.replace({ query: { pack_id: 'pack', result_id: 'run_87654321' } })
  await flushPromises()
  finish(response(fixture()))
  await flushPromises()
  expect(wrapper.findComponent(PuzzleResultDocument).props('result').report.run_id).toBe(
    'run_87654321',
  )
})

it('marks invalid and unsupported entries and does not select a default result', async () => {
  const data = list().data
  vi.mocked(puzzleApi.results).mockResolvedValue(
    response({
      ...data,
      items: [
        { ...data.items[0]!, status: 'unsupported' },
        { ...data.items[0]!, run_id: 'run_87654321', status: 'invalid' },
      ],
    }),
  )
  const { wrapper } = await setup('?pack_id=pack')
  expect(wrapper.text()).toContain(zhCN.puzzleHistory.status.unsupported)
  expect(wrapper.text()).toContain(zhCN.puzzleHistory.status.invalid)
  expect(puzzleApi.result).not.toHaveBeenCalled()
})

it('rejects malformed query values instead of reading an unrelated record', async () => {
  const { wrapper } = await setup('?pack_id=pack&result_id=unknown&result_page=0')
  expect(wrapper.text()).toContain(zhCN.puzzleHistory.invalidPosition)
  expect(puzzleApi.result).not.toHaveBeenCalled()
  expect(puzzleApi.results).not.toHaveBeenCalled()
})

it('opens a newly completed test by its saved identity and refreshes history', async () => {
  vi.mocked(puzzleApi.result).mockImplementation((_pack, id) =>
    Promise.resolve(response(fixture(id))),
  )
  const { wrapper, router } = await setup()
  await wrapper.setProps({ latest: fixture('run_87654321').report })
  await flushPromises()
  expect(router.currentRoute.value.query.result_id).toBe('run_87654321')
  expect(router.currentRoute.value.query.result_page).toBeUndefined()
  expect(wrapper.findComponent(PuzzleResultDocument).props('result').report.run_id).toBe(
    'run_87654321',
  )
})
