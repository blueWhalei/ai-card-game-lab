/** @vitest-environment happy-dom */
import { afterEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, shallowMount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter, RouterLink } from 'vue-router'
import zhCN from '@/i18n/locales/zh-CN'
import { researchApi, type ResearchTracePreview } from '@/api/researchApi'
import TraceEvidenceReview from './TraceEvidenceReview.vue'
import TraceRecordDocument from '@/components/trace/TraceRecordDocument.vue'
import UiButton from '@/components/ui/Button.vue'

enableAutoUnmount(afterEach)
afterEach(() => vi.restoreAllMocks())
const hash = 'a'.repeat(64)
const reference = { trace_id: 'tr', expected_source_hash: hash, note: '' }
const response = (id = 'tr', sourceHash = hash) => ({
  code: 0,
  message: '',
  data: {
    comparison_id: 'cmp',
    source_hash: sourceHash,
    trace: { id, game_id: 'game' },
    source: { experiment_id: 'run' },
  } as ResearchTracePreview,
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
      review_trace: 'tr',
      review_trace_hash: hash,
      report_id: 'rev',
      trace_evidence: 'tr',
    },
  })
  const wrapper = shallowMount(TraceEvidenceReview, {
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
it('requires explicit citation and preserves the exact report return', async () => {
  vi.spyOn(researchApi, 'tracePreview').mockResolvedValue(response())
  const { wrapper, router } = await setup()
  expect(wrapper.emitted('cite')).toBeUndefined()
  expect(wrapper.findComponent(RouterLink).props('to')).toMatchObject({
    query: {
      trace_id: 'tr',
      game_id: 'game',
      experiment_id: 'run',
      report_id: 'rev',
      trace_evidence: 'tr',
    },
  })
  wrapper.findComponent(UiButton).vm.$emit('click')
  await flushPromises()
  expect(wrapper.emitted('cite')).toEqual([[reference]])
  expect(router.currentRoute.value.query).toEqual({
    snapshot: 'cmp',
    report_id: 'rev',
    trace_evidence: 'tr',
  })
})
it.each(['identity', 'hash', 'scope'])(
  'rejects %s changes without emitting a citation',
  async (change) => {
    const spy = vi.spyOn(researchApi, 'tracePreview')
    if (change === 'scope') spy.mockRejectedValue(new Error('Outside cohort'))
    else
      spy.mockResolvedValue(
        response(change === 'identity' ? 'other' : 'tr', change === 'hash' ? 'b'.repeat(64) : hash),
      )
    const { wrapper } = await setup()
    expect(wrapper.findComponent(TraceRecordDocument).exists()).toBe(false)
    expect(wrapper.find('[role="alert"]').exists()).toBe(true)
    expect(wrapper.emitted('cite')).toBeUndefined()
  },
)
it('updates a reviewed source explicitly without losing its note, even at the five-record limit', async () => {
  vi.spyOn(researchApi, 'tracePreview').mockResolvedValue(response())
  const { wrapper } = await setup()
  await wrapper.setProps({
    included: [
      { ...reference, expected_source_hash: 'b'.repeat(64), note: 'My interpretation remains' },
      ...Array.from({ length: 4 }, (_, i) => ({ ...reference, trace_id: `other-${i}` })),
    ],
  })
  expect(wrapper.findComponent(UiButton).text()).toBe(zhCN.traceCitation.update)
  wrapper.findComponent(UiButton).vm.$emit('click')
  expect(wrapper.emitted('cite')).toEqual([[{ ...reference, note: 'My interpretation remains' }]])
})
it('blocks duplicates, unavailable drafts and new citations at the limit, then ignores late responses', async () => {
  vi.spyOn(researchApi, 'tracePreview').mockResolvedValue(response())
  const { wrapper, router } = await setup()
  for (const props of [
    { included: [reference], disabled: false },
    { included: [], disabled: true },
    {
      included: Array.from({ length: 5 }, (_, i) => ({ ...reference, trace_id: `old-${i}` })),
      disabled: false,
    },
  ]) {
    await wrapper.setProps(props)
    wrapper.findComponent(UiButton).vm.$emit('click')
    expect(wrapper.emitted('cite')).toBeUndefined()
  }
  let finish!: (value: ReturnType<typeof response>) => void
  vi.mocked(researchApi.tracePreview).mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve
      }),
  )
  await wrapper.setProps({ comparisonId: 'next' })
  await router.replace('/')
  finish(response())
  await flushPromises()
  expect(wrapper.findComponent(TraceRecordDocument).exists()).toBe(false)
})
