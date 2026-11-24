/** @vitest-environment happy-dom */
import { afterEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, shallowMount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter, RouterLink } from 'vue-router'
import zhCN from '@/i18n/locales/zh-CN'
import { researchApi, type ResearchPuzzlePreview } from '@/api/researchApi'
import PuzzleEvidenceReview from './PuzzleEvidenceReview.vue'
import PuzzleCitationPreview from './PuzzleCitationPreview.vue'

enableAutoUnmount(afterEach)
afterEach(() => vi.restoreAllMocks())
const hash = 'a'.repeat(64)
const reference = { pack_id: 'pack', run_id: 'run_12345678', expected_report_hash: hash, note: '' }
const response = (pack = 'pack', reportHash = hash) => ({
  code: 0,
  message: '',
  data: {
    result: { report: { pack_id: pack, run_id: reference.run_id }, report_hash: reportHash },
    sources: [],
  } as unknown as ResearchPuzzlePreview,
})
async function setup() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: { template: '<div />' } }],
  })
  await router.push({
    path: '/',
    query: {
      snapshot: 'cmp',
      review_pack: 'pack',
      review_result: reference.run_id,
      review_hash: hash,
      review_page: '3',
      report_id: 'rev',
      puzzle_evidence: 'original',
    },
  })
  const wrapper = shallowMount(PuzzleEvidenceReview, {
    props: { comparisonId: 'cmp', included: [], disabled: false },
    global: {
      renderStubDefaultSlot: true,
      plugins: [
        router,
        createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } }),
      ],
    },
  })
  await flushPromises()
  return { wrapper, router }
}
it('adds only after explicit review and preserves the exact report return', async () => {
  vi.spyOn(researchApi, 'puzzlePreview').mockResolvedValue(response())
  const { wrapper, router } = await setup()
  expect(wrapper.emitted('cite')).toBeUndefined()
  expect(wrapper.findComponent(RouterLink).props('to')).toMatchObject({
    query: {
      pack_id: 'pack',
      result_id: reference.run_id,
      result_page: '3',
      report_id: 'rev',
      puzzle_evidence: 'original',
    },
  })
  wrapper.findComponent(PuzzleCitationPreview).vm.$emit('cite', reference)
  await flushPromises()
  expect(wrapper.emitted('cite')).toEqual([[reference]])
  expect(router.currentRoute.value.query).toEqual({
    snapshot: 'cmp',
    report_id: 'rev',
    puzzle_evidence: 'original',
  })
})
it.each(['identity', 'hash', 'scope'])(
  'blocks %s changes without modifying the draft',
  async (change) => {
    const spy = vi.spyOn(researchApi, 'puzzlePreview')
    if (change === 'scope') spy.mockRejectedValue(new Error('Source no longer eligible'))
    else
      spy.mockResolvedValue(
        response(
          change === 'identity' ? 'other' : 'pack',
          change === 'hash' ? 'b'.repeat(64) : hash,
        ),
      )
    const { wrapper } = await setup()
    expect(wrapper.findComponent(PuzzleCitationPreview).exists()).toBe(false)
    expect(wrapper.find('[role="alert"]').exists()).toBe(true)
    expect(wrapper.emitted('cite')).toBeUndefined()
  },
)
it('ignores late responses after close and blocks unavailable or full drafts', async () => {
  vi.spyOn(researchApi, 'puzzlePreview').mockResolvedValue(response())
  const { wrapper, router } = await setup()
  await wrapper.setProps({ disabled: true })
  wrapper.findComponent(PuzzleCitationPreview).vm.$emit('cite', reference)
  expect(wrapper.emitted('cite')).toBeUndefined()
  await wrapper.setProps({
    disabled: false,
    included: Array.from({ length: 5 }, (_, i) => ({ ...reference, pack_id: `old-${i}` })),
  })
  wrapper.findComponent(PuzzleCitationPreview).vm.$emit('cite', reference)
  expect(wrapper.emitted('cite')).toBeUndefined()
  let finish!: (value: ReturnType<typeof response>) => void
  vi.mocked(researchApi.puzzlePreview).mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve
      }),
  )
  await wrapper.setProps({ comparisonId: 'next' })
  await router.replace('/')
  finish(response())
  await flushPromises()
  expect(wrapper.findComponent(PuzzleCitationPreview).exists()).toBe(false)
})
