/** @vitest-environment happy-dom */
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, shallowMount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { researchApi, type ResearchPuzzlePreview } from '@/api/researchApi'
import { puzzleApi } from '@/api/puzzleApi'
import zhCN from '@/i18n/locales/zh-CN'
import ComparisonPuzzleEvidence from './ComparisonPuzzleEvidence.vue'
import UiButton from '@/components/ui/Button.vue'
import UiSelect from '@/components/ui/Select.vue'
import PuzzleResultDocument from '@/components/puzzle/PuzzleResultDocument.vue'
import PuzzleCitationPreview from './PuzzleCitationPreview.vue'

enableAutoUnmount(afterEach)
afterEach(() => vi.restoreAllMocks())
const response = <T>(data: T) => ({ code: 0, message: '', data })
function preview(pack = 'pack'): ResearchPuzzlePreview {
  return {
    result: {
      report: {
        pack_id: pack,
        run_id: 'run_12345678',
        metric_version: 'puzzle-scoring-v2',
        baseline_kind: 'first',
        seed: 0,
        created_at: '2026-11-08',
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
            puzzle_id: 'p',
            chosen_action_id: 'a',
            best_action_id: 'b',
            hit: null,
            ev_loss: null,
            truncated: true,
          },
        ],
      },
      report_hash: 'a'.repeat(64),
      source_status: 'matched',
      read_at: '2026-11-08',
    },
    sources: [],
  }
}
beforeEach(() => {
  vi.spyOn(researchApi, 'puzzlePacks').mockResolvedValue(
    response(
      ['pack', 'other'].map((pack_id) => ({
        pack_id,
        created_at: '2026-11-08',
        game_type: 'doudizhu',
        source_experiment_id: 'a',
        puzzle_count: 1,
        extract: {},
        notes: '',
        kind: 'cardlab.puzzle_pack',
        schema_version: 1,
      })),
    ),
  )
  vi.spyOn(puzzleApi, 'results').mockResolvedValue(
    response({
      items: [
        {
          run_id: 'run_12345678',
          kind: 'run',
          status: 'available',
          created_at: '2026-11-08',
          baseline_kind: 'first',
        },
      ],
      page: 1,
      page_size: 20,
      total: 1,
      read_at: '',
    }),
  )
  vi.spyOn(researchApi, 'puzzlePreview').mockImplementation((_id, pack) =>
    Promise.resolve(response(preview(pack))),
  )
})
async function setup() {
  const wrapper = shallowMount(ComparisonPuzzleEvidence, {
    props: { comparisonId: 'cmp', modelValue: [] },
    global: {
      renderStubDefaultSlot: true,
      stubs: { PuzzleCitationPreview: false },
      plugins: [createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })],
    },
  })
  expect(researchApi.puzzlePacks).not.toHaveBeenCalled()
  await wrapper.findComponent(UiButton).trigger('click')
  await flushPromises()
  wrapper.findComponent(UiSelect).vm.$emit('update:modelValue', 'pack')
  await flushPromises()
  return wrapper
}
it('adds only the explicitly previewed identity and content hash, without duplicate references', async () => {
  const wrapper = await setup()
  expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  await wrapper.get('li button').trigger('click')
  await flushPromises()
  expect(researchApi.puzzlePreview).toHaveBeenCalledWith('cmp', 'pack', 'run_12345678')
  const add = () =>
    wrapper
      .findAllComponents(UiButton)
      .find((b) => [zhCN.puzzleCitation.add, zhCN.focus.included].includes(b.text()))!
  await add().trigger('click')
  const refs = wrapper.emitted('update:modelValue')![0]![0]
  expect(refs).toEqual([
    { pack_id: 'pack', run_id: 'run_12345678', expected_report_hash: 'a'.repeat(64), note: '' },
  ])
  await wrapper.setProps({ modelValue: refs as never })
  expect(add().props('disabled')).toBe(true)
  add().vm.$emit('click')
  expect(wrapper.emitted('update:modelValue')).toHaveLength(1)
})
it('keeps existing references when source verification fails', async () => {
  vi.mocked(researchApi.puzzlePreview).mockRejectedValue({
    code: 'RESEARCH_PUZZLE_SCOPE',
    message: 'Out of scope',
  })
  const wrapper = await setup()
  await wrapper.setProps({
    modelValue: [
      {
        pack_id: 'old',
        run_id: 'run_87654321',
        expected_report_hash: 'b'.repeat(64),
        note: 'Keep this note',
      },
    ],
  })
  await wrapper.get('li button').trigger('click')
  await flushPromises()
  expect(wrapper.find('[role="alert"]').exists()).toBe(true)
  expect(wrapper.findComponent(PuzzleResultDocument).exists()).toBe(false)
  expect(wrapper.props('modelValue')[0]!.note).toBe('Keep this note')
  expect(wrapper.emitted('update:modelValue')).toBeUndefined()
})
it('discards a late preview when the selected pack changes', async () => {
  let finish!: (value: ReturnType<typeof response<ResearchPuzzlePreview>>) => void
  vi.mocked(researchApi.puzzlePreview).mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve
      }),
  )
  const wrapper = await setup()
  await wrapper.get('li button').trigger('click')
  wrapper.findComponent(UiSelect).vm.$emit('update:modelValue', 'other')
  await flushPromises()
  finish(response(preview()))
  await flushPromises()
  expect(wrapper.findComponent(PuzzleResultDocument).exists()).toBe(false)
  expect(wrapper.emitted('update:modelValue')).toBeUndefined()
})

it('shows the five-test limit and preserves existing notes', async () => {
  const wrapper = await setup()
  await wrapper.get('li button').trigger('click')
  await flushPromises()
  await wrapper.setProps({
    modelValue: Array.from({ length: 5 }, (_, i) => ({
      pack_id: `old-${i}`,
      run_id: 'run_12345678',
      expected_report_hash: 'b'.repeat(64),
      note: 'Keep',
    })),
  })
  expect(wrapper.findComponent(PuzzleCitationPreview).text()).toContain(zhCN.puzzleCitation.limit)
  const add = wrapper.findAllComponents(UiButton).find((b) => b.text() === zhCN.puzzleCitation.add)!
  expect(add.props('disabled')).toBe(true)
  add.vm.$emit('click')
  expect(wrapper.emitted('update:modelValue')).toBeUndefined()
})
