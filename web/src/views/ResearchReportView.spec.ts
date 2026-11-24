/** @vitest-environment happy-dom */
import { afterEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, shallowMount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter } from 'vue-router'
import { researchApi, type ResearchReport } from '@/api/researchApi'
import zhCN from '@/i18n/locales/zh-CN'
import ResearchReportView from './ResearchReportView.vue'
import ResearchReportDocument from '@/components/experiment/ResearchReportDocument.vue'
import UiButton from '@/components/ui/Button.vue'

enableAutoUnmount(afterEach)
afterEach(() => vi.restoreAllMocks())
function response(id: string) {
  return {
    code: 0,
    message: '',
    data: {
      kind: 'cardlab.research_report',
      exported_at: '2026-11-06',
      scope: 'frozen',
      evidence_status: {},
      record: {
        id,
        comparison_id: 'cmp',
        evidence: [],
        revision: 1,
        created_at: '2026-11-05',
        observations: '',
        interpretation: '',
        limitations: '',
      },
      comparison: { id: 'cmp', title: id, created_at: '2026-11-05', result: { experiments: [] } },
    } as ResearchReport,
  }
}
async function setup() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/research-reports/:id', component: { template: '<div />' } }],
  })
  await router.push('/research-reports/a')
  const wrapper = shallowMount(ResearchReportView, {
    global: {
      renderStubDefaultSlot: true,
      plugins: [
        router,
        createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } }),
      ],
    },
  })
  return { router, wrapper }
}
it('ignores a late previous revision response', async () => {
  let finish!: (value: ReturnType<typeof response>) => void
  vi.spyOn(researchApi, 'export').mockImplementation((id) =>
    id === 'a'
      ? new Promise((resolve) => {
          finish = resolve
        })
      : Promise.resolve(response(id)),
  )
  const { wrapper, router } = await setup()
  await router.push('/research-reports/b')
  await flushPromises()
  finish(response('a'))
  await flushPromises()
  expect(wrapper.findComponent(ResearchReportDocument).props('report').record.id).toBe('b')
})
it('rejects mismatched identities and supports retry without inventing a report', async () => {
  vi.spyOn(researchApi, 'export')
    .mockResolvedValueOnce(response('wrong'))
    .mockResolvedValue(response('a'))
  const { wrapper } = await setup()
  await flushPromises()
  expect(wrapper.find('[role="alert"]').text()).toContain('无法读取')
  expect(wrapper.findComponent(ResearchReportDocument).exists()).toBe(false)
  wrapper.findComponent(UiButton).vm.$emit('click')
  await flushPromises()
  expect(wrapper.findComponent(ResearchReportDocument).props('report').record.id).toBe('a')
})

it('repositions the same trace citation when its directory link is clicked again', async () => {
  const data = response('a')
  data.data.record.trace_evidence = [{ trace: { id: 'tr' } }] as NonNullable<
    ResearchReport['record']['trace_evidence']
  >
  vi.spyOn(researchApi, 'export').mockResolvedValue(data)
  const scroll = vi.spyOn(HTMLElement.prototype, 'scrollIntoView').mockImplementation(() => {})
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/research-reports/:id', component: { template: '<div />' } }],
  })
  await router.push('/research-reports/a?trace_evidence=tr')
  const wrapper = shallowMount(ResearchReportView, {
    global: {
      plugins: [
        router,
        createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } }),
      ],
      stubs: {
        ResearchReportDocument: {
          template:
            '<article><button @click="$emit(\'locate-trace\', \'tr\')">Locate trace</button><section id="report-trace-1" tabindex="-1" /></article>',
        },
      },
    },
  })
  await flushPromises()
  scroll.mockClear()
  await wrapper.get('button').trigger('click')
  await flushPromises()
  expect(router.currentRoute.value.query).toEqual({ trace_evidence: 'tr' })
  expect(scroll).toHaveBeenCalledOnce()
})
