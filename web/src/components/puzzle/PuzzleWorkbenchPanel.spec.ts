/** @vitest-environment happy-dom */
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { puzzleApi, type PuzzlePackSummary, type PuzzleProbeReport } from '@/api/puzzleApi'
import zhCN from '@/i18n/locales/zh-CN'
import PuzzleWorkbenchPanel from './PuzzleWorkbenchPanel.vue'
import CompactRecordList from '@/components/common/CompactRecordList.vue'
import UiSelect from '@/components/ui/Select.vue'
import PuzzleResults from './PuzzleResults.vue'

const route = vi.hoisted(() => ({
  path: '/pipeline/puzzles',
  fullPath: '/pipeline/puzzles?pack_id=pack',
  query: { pack_id: 'pack' },
}))
beforeEach(() => {
  route.fullPath = '/pipeline/puzzles?pack_id=pack'
})
vi.mock('vue-router', () => ({
  useRoute: () => route,
  useRouter: () => ({ replace: vi.fn() }),
  RouterLink: { name: 'RouterLink', props: ['to'], template: '<a><slot /></a>' },
}))
vi.mock('@/components/ui/toast', () => ({ toast: { success: vi.fn(), warning: vi.fn() } }))
afterEach(() => vi.restoreAllMocks())

const pack = (id: string): PuzzlePackSummary => ({
  pack_id: id,
  created_at: '',
  game_type: 'doudizhu',
  source_experiment_id: 'exp',
  puzzle_count: 1,
  extract: {},
  notes: '',
  kind: 'cardlab.puzzle_pack',
  schema_version: 1,
})
const result = (id: string) => ({ code: 0, message: '', data: { manifest: pack(id), preview: [] } })
const probeResult = {
  code: 0,
  message: '',
  data: {
    metric_version: 'puzzle-scoring-v2',
    run_id: 'probe',
    pack_id: 'pack',
    baseline_kind: 'first',
    seed: 0,
    created_at: '',
    summary: {
      n: 1,
      n_trials: 3,
      kinds: ['shuffle_legal_actions'],
      comparisons_n: 3,
      repeat_consistency: 1,
      consistency: 0,
      base_evaluated_n: 0,
      base_unevaluated_n: 3,
      pert_evaluated_n: 0,
      pert_unevaluated_n: 3,
      base_accuracy: null,
      pert_accuracy: null,
      base_mean_ev_loss: null,
      pert_mean_ev_loss: null,
    },
  } satisfies PuzzleProbeReport,
}
function mountPanel() {
  return shallowMount(PuzzleWorkbenchPanel, {
    global: {
      plugins: [createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })],
      stubs: { RouterLink: false, UiButton: { template: '<button><slot /></button>' } },
    },
  })
}

it('does not replace an explicitly missing pack with the first available pack', async () => {
  vi.spyOn(puzzleApi, 'listPacks').mockResolvedValue({
    code: 0,
    message: '',
    data: [pack('other')],
  })
  vi.spyOn(puzzleApi, 'getPack').mockRejectedValue({ code: 'PUZZLE_PACK_NOT_FOUND' })
  const wrapper = mountPanel()
  await flushPromises()
  expect(puzzleApi.getPack).toHaveBeenCalledWith('pack', 5)
  expect(puzzleApi.getPack).not.toHaveBeenCalledWith('other', 5)
  expect(wrapper.get('[role="alert"]').text()).toBe(zhCN.puzzle.packMissing)
  wrapper.unmount()
})

it('ignores a detail response that arrives after another pack was selected', async () => {
  let finish!: (value: ReturnType<typeof result>) => void
  vi.spyOn(puzzleApi, 'listPacks').mockResolvedValue({
    code: 0,
    message: '',
    data: [pack('pack'), pack('other')],
  })
  vi.spyOn(puzzleApi, 'getPack').mockImplementation((id) =>
    id === 'pack'
      ? new Promise((resolve) => {
          finish = resolve
        })
      : Promise.resolve(result(id)),
  )
  const wrapper = mountPanel()
  await flushPromises()
  wrapper.findComponent(CompactRecordList).vm.$emit('select', 'other')
  await flushPromises()
  finish(result('pack'))
  await flushPromises()
  expect(wrapper.get('h2').text()).toBe('other')
  wrapper.unmount()
})

it('shows the frozen question and a source decision link', async () => {
  const manifest = pack('pack')
  manifest.extract = {
    method: 'decision_record',
    question: 'Order diagnostic',
    source: {
      experiment_id: 'exp',
      experiment_name: 'Source',
      game_id: 'game',
      decision_point_id: 'dp',
      round_num: 4,
      read_at: '',
      evaluator_params: {},
    },
  }
  vi.spyOn(puzzleApi, 'listPacks').mockResolvedValue({ code: 0, message: '', data: [manifest] })
  vi.spyOn(puzzleApi, 'getPack').mockResolvedValue({
    code: 0,
    message: '',
    data: { manifest, preview: [] },
  })
  const wrapper = mountPanel()
  await flushPromises()
  expect(wrapper.text()).toContain('Order diagnostic')
  expect(wrapper.text()).toContain(zhCN.puzzle.targetScope)
  const link = wrapper
    .findAllComponents({ name: 'RouterLink' })
    .find((l) => l.text() === zhCN.puzzle.sourceDecision)
  expect(link?.props('to')).toEqual({
    path: '/pipeline/decisions',
    query: { experiment_id: 'exp', game_id: 'game', decision_id: 'dp', puzzle_pack: 'pack' },
  })
  wrapper.unmount()
})

it('sends the selected perturbation and displays returned conditions after controls change', async () => {
  vi.spyOn(puzzleApi, 'listPacks').mockResolvedValue({ code: 0, message: '', data: [pack('pack')] })
  vi.spyOn(puzzleApi, 'getPack').mockResolvedValue(result('pack'))
  vi.spyOn(puzzleApi, 'probe').mockResolvedValue(probeResult)
  const wrapper = mountPanel()
  await flushPromises()
  wrapper.findAllComponents(UiSelect)[1]!.vm.$emit('update:modelValue', 'shuffle_legal_actions')
  await flushPromises()
  await wrapper
    .findAll('button')
    .find((b) => b.text() === zhCN.puzzle.probe)!
    .trigger('click')
  await flushPromises()
  expect(puzzleApi.probe).toHaveBeenCalledWith('pack', {
    baseline_kind: 'heuristic',
    seed: 0,
    n_trials: 3,
    kinds: ['shuffle_legal_actions'],
  })
  wrapper.findAllComponents(UiSelect)[1]!.vm.$emit('update:modelValue', 'shuffle_hand_cards')
  await flushPromises()
  expect(wrapper.findComponent(PuzzleResults).props('latest')).toEqual(probeResult.data)
  wrapper.unmount()
})

it('does not attach a late probe result to a different pack', async () => {
  let finish!: (value: typeof probeResult) => void
  vi.spyOn(puzzleApi, 'listPacks').mockResolvedValue({
    code: 0,
    message: '',
    data: [pack('pack'), pack('other')],
  })
  vi.spyOn(puzzleApi, 'getPack').mockImplementation((id) => Promise.resolve(result(id)))
  vi.spyOn(puzzleApi, 'probe').mockReturnValue(
    new Promise((resolve) => {
      finish = resolve
    }),
  )
  const wrapper = mountPanel()
  await flushPromises()
  await wrapper
    .findAll('button')
    .find((b) => b.text() === zhCN.puzzle.probe)!
    .trigger('click')
  wrapper.findComponent(CompactRecordList).vm.$emit('select', 'other')
  await flushPromises()
  finish(probeResult)
  await flushPromises()
  expect(wrapper.get('h2').text()).toBe('other')
  expect(wrapper.findComponent(PuzzleResults).props('latest')).toBeNull()
  wrapper.unmount()
})

it('keeps the selected history record when a pending probe finishes', async () => {
  let finish!: (value: typeof probeResult) => void
  vi.spyOn(puzzleApi, 'listPacks').mockResolvedValue({ code: 0, message: '', data: [pack('pack')] })
  vi.spyOn(puzzleApi, 'getPack').mockResolvedValue(result('pack'))
  vi.spyOn(puzzleApi, 'probe').mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve
      }),
  )
  const wrapper = mountPanel()
  await flushPromises()
  await wrapper
    .findAll('button')
    .find((button) => button.text() === zhCN.puzzle.probe)!
    .trigger('click')
  route.fullPath = '/pipeline/puzzles?pack_id=pack&result_id=run_12345678'
  finish(probeResult)
  await flushPromises()
  expect(wrapper.findComponent(PuzzleResults).props('latest')).toBeNull()
  wrapper.unmount()
})
