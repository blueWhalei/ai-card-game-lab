/** @vitest-environment happy-dom */
import { afterEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, shallowMount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter, RouterLink } from 'vue-router'
import zhCN from '@/i18n/locales/zh-CN'
import en from '@/i18n/locales/en'
import { researchApi, type CitationSource } from '@/api/researchApi'
import EvidenceCitationEntry from './EvidenceCitationEntry.vue'
import UiButton from '@/components/ui/Button.vue'

enableAutoUnmount(afterEach)
afterEach(() => vi.restoreAllMocks())
const hash = 'a'.repeat(64)
const response = (next: number | null = null) => ({
  code: 0,
  message: '',
  data: {
    pack_id: 'pack',
    run_id: 'run_12345678',
    report_hash: hash,
    read_at: '',
    items: [{ id: 'cmp', title: 'Comparison', created_at: '' }],
    next_offset: next,
  },
})
async function setup(
  source: CitationSource = {
    kind: 'puzzle',
    packId: 'pack',
    runId: 'run_12345678',
    reportHash: hash,
    page: 3,
  },
  locale = 'zh-CN',
) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: { template: '<div />' } }],
  })
  await router.push('/?report_id=rev&puzzle_evidence=pack/run_12345678')
  const wrapper = shallowMount(EvidenceCitationEntry, {
    props: { source },
    global: {
      renderStubDefaultSlot: true,
      plugins: [router, createI18n({ legacy: false, locale, messages: { 'zh-CN': zhCN, en } })],
    },
  })
  await wrapper.findComponent(UiButton).trigger('click')
  await flushPromises()
  return { wrapper, router }
}
it.each(['zh-CN', 'en'])(
  'builds an explicit test preview link and preserves source/report context in %s',
  async (locale) => {
    vi.spyOn(researchApi, 'puzzleTargets').mockResolvedValue(response())
    const { wrapper } = await setup(undefined, locale)
    expect(researchApi.puzzleTargets).toHaveBeenCalledWith('pack', 'run_12345678', 0)
    expect(wrapper.findComponent(RouterLink).props('to')).toEqual({
      path: '/experiments/compare',
      query: {
        snapshot: 'cmp',
        review_pack: 'pack',
        review_result: 'run_12345678',
        review_hash: hash,
        review_page: '3',
        report_id: 'rev',
        puzzle_evidence: 'pack/run_12345678',
      },
    })
  },
)
it('refuses a changed test and discards discovery after selection changes', async () => {
  vi.spyOn(researchApi, 'puzzleTargets').mockResolvedValue({
    ...response(),
    data: { ...response().data, report_hash: 'b'.repeat(64) },
  })
  const { wrapper } = await setup()
  expect(wrapper.get('[role="alert"]').text()).toBe(zhCN.puzzleCitation.changedPreview)
  expect(wrapper.findComponent(RouterLink).exists()).toBe(false)
  let finish!: (value: ReturnType<typeof response>) => void
  vi.mocked(researchApi.puzzleTargets).mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve
      }),
  )
  await wrapper.findComponent(UiButton).trigger('click')
  await wrapper.setProps({
    source: { kind: 'puzzle', packId: 'other', runId: 'run_12345678', reportHash: hash, page: 1 },
  })
  finish(response())
  await flushPromises()
  expect(wrapper.findComponent(RouterLink).exists()).toBe(false)
})
it('continues after an empty filtered page and still supports decision destinations', async () => {
  vi.spyOn(researchApi, 'puzzleTargets')
    .mockResolvedValueOnce({ ...response(20), data: { ...response(20).data, items: [] } })
    .mockResolvedValueOnce(response())
  const { wrapper } = await setup()
  await wrapper
    .findAllComponents(UiButton)
    .find((b) => b.text() === zhCN.evidenceEntry.more)!
    .trigger('click')
  await flushPromises()
  expect(researchApi.puzzleTargets).toHaveBeenLastCalledWith('pack', 'run_12345678', 20)
  expect(wrapper.findAllComponents(RouterLink)).toHaveLength(1)
  vi.spyOn(researchApi, 'decisionTargets').mockResolvedValue({
    code: 0,
    message: '',
    data: {
      decision_id: 'd',
      items: [{ id: 'cmp', title: '', created_at: '', seed: 42 }],
      next_offset: null,
    },
  })
  const decision = await setup({ kind: 'decision', id: 'd', turn: 7 })
  expect(decision.wrapper.findComponent(RouterLink).props('to')).toMatchObject({
    query: { snapshot: 'cmp', review_decision: 'd', seed: '42', turn: '7' },
  })
})

it('carries a trace fingerprint to review and clears old destinations when a later page changes', async () => {
  const data = { trace_id: 'tr', source_hash: hash, items: response().data.items, next_offset: 20 }
  vi.spyOn(researchApi, 'traceTargets')
    .mockResolvedValueOnce({ code: 0, message: '', data })
    .mockResolvedValueOnce({ code: 0, message: '', data: { ...data, source_hash: 'b'.repeat(64) } })
  const { wrapper, router } = await setup({ kind: 'trace', id: 'tr' })
  await router.replace('/?report_id=rev&trace_evidence=tr')
  expect(wrapper.findComponent(RouterLink).props('to')).toEqual({
    path: '/experiments/compare',
    query: {
      snapshot: 'cmp',
      review_trace: 'tr',
      review_trace_hash: hash,
      report_id: 'rev',
      trace_evidence: 'tr',
    },
  })
  await wrapper
    .findAllComponents(UiButton)
    .find((button) => button.text() === zhCN.evidenceEntry.more)!
    .trigger('click')
  await flushPromises()
  expect(wrapper.findComponent(RouterLink).exists()).toBe(false)
  expect(wrapper.get('[role="alert"]').text()).toBe(zhCN.traceCitation.changed)
})
