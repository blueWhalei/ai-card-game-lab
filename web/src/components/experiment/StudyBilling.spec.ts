/** @vitest-environment happy-dom */
import { afterEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter, matchedRouteKey } from 'vue-router'
import { computed } from 'vue'
import { createPinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import { studyBillingApi, type BillingOverview, type BillingEvidence } from '@/api/studyBillingApi'
import StudyBilling from './StudyBilling.vue'
import UiPagination from '@/components/ui/Pagination.vue'
import * as confirm from '@/components/ui/confirm'
import zh from '@/i18n/locales/zh-CN'
import en from '@/i18n/locales/en'

enableAutoUnmount(afterEach)
afterEach(() => {
  vi.restoreAllMocks()
  vi.useRealTimers()
})
function response(id = 's') {
  return {
    code: 0,
    message: '',
    data: {
      study_id: id,
      provider: 'openai',
      source_url: 'https://api.openai.com/v1/organization/costs',
      currency: 'USD',
      organization_id: 'org-test',
      credential_configured: true,
      can_sync: true,
      config: {
        study_id: id,
        revision: 2,
        organization_id: 'org-test',
        project_id: 'proj_test',
        start_date: '2026-11-01',
        limit_amount: '0.1',
        enforcement_enabled: true,
        max_age_hours: 6,
        reason: 'Fixture',
        created_at: '2026-11-19T00:00:00Z',
      },
      snapshot: {
        id: 'attempt',
        start_time: 1793491200,
        end_time: 1795046400,
        finished_at: '2026-11-19T00:00:01Z',
        amount: '0.1000000000001',
      },
      latest_attempt: null,
      snapshot_valid_until: '2026-11-19T06:00:00Z',
      state: 'reached',
      admission_blocked: true,
      cost_admission_blocked: true,
      reconciliation_blocked: false,
      history: [],
      config_history: [],
      read_at: '2026-11-19T00:00:02Z',
    } satisfies BillingOverview,
  }
}
function evidenceResponse(page = 1) {
  return {
    code: 0,
    message: '',
    data: {
      ...response().data.config!,
      id: 'attempt',
      status: 'succeeded',
      trigger: 'manual',
      schedule_revision: null,
      start_time: 1793491200,
      end_time: 1795046400,
      started_at: '2026-11-19T00:00:00Z',
      finished_at: '2026-11-19T00:00:01Z',
      error_code: null,
      amount: '0.1000000000001',
      source_url: 'https://api.openai.com/v1/organization/costs',
      currency: 'USD',
      page,
      page_size: 20,
      total: 21,
      items: [
        {
          start_time: 1793491200,
          end_time: 1793577600,
          amount: '0.0000000000001',
          currency: 'USD',
          project_id: 'proj_test',
          line_item: '<script>source</script>',
        },
      ],
    } satisfies BillingEvidence,
  }
}
async function setup(locale = 'zh-CN') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:pathMatch(.*)*', component: StudyBilling }],
  })
  await router.push('/research/s?task_kind=finance')
  const wrapper = mount(StudyBilling, {
    props: { studyId: 's' },
    global: {
      provide: {
        [matchedRouteKey as symbol]: computed(() => router.currentRoute.value.matched[0]),
      },
      plugins: [
        router,
        createPinia(),
        createI18n({ legacy: false, locale, messages: { 'zh-CN': zh, en } }),
      ],
      stubs: {
        UiPagination: true,
        Icon: true,
        StudyBillingSchedule: true,
        StudyBillingReconciliation: true,
      },
    },
  })
  await flushPromises()
  return { wrapper, router }
}
type Wrapper = Awaited<ReturnType<typeof setup>>['wrapper']
async function click(wrapper: Wrapper, label: string) {
  const button = wrapper.findAll('button').find((button) => button.text() === label)
  expect(button, label).toBeDefined()
  await button!.trigger('click')
  await flushPromises()
}
it.each(['zh-CN', 'en'])(
  'shows exact scoped amount and limitations in %s without syncing automatically',
  async (locale) => {
    vi.spyOn(studyBillingApi, 'get').mockResolvedValue(response())
    const sync = vi.spyOn(studyBillingApi, 'sync')
    const { wrapper } = await setup(locale)
    const copy = locale === 'en' ? en.billing : zh.billing
    expect(wrapper.text()).toContain(copy.scope)
    expect(wrapper.text()).toContain(copy.coverage)
    expect(wrapper.text()).toContain(copy.limits)
    expect(wrapper.text()).toContain('0.1000000000001')
    expect(wrapper.text()).toContain('org-test')
    expect(wrapper.text()).toContain('proj_test')
    expect(wrapper.text()).toContain(copy.gateBlocked)
    expect(sync).not.toHaveBeenCalled()
  },
)
it('preserves config input after a conflict and sends exact zero with the original version', async () => {
  vi.spyOn(studyBillingApi, 'get').mockResolvedValue(response())
  const save = vi
    .spyOn(studyBillingApi, 'configure')
    .mockRejectedValue({ code: 'BILLING_CONFLICT', message: 'conflict' })
  const { wrapper } = await setup()
  await click(wrapper, zh.billing.configure)
  const inputs = wrapper.findAll('input')
  await inputs[2]!.setValue('0')
  await wrapper.find('textarea').setValue('Review shared project scope')
  await wrapper.find('form').trigger('submit')
  await flushPromises()
  expect(save).toHaveBeenCalledWith(
    's',
    expect.objectContaining({
      expected_revision: 2,
      limit: '0',
      max_age_hours: 6,
      enforcement_enabled: true,
    }),
  )
  expect((wrapper.findAll('input')[2]!.element as HTMLInputElement).value).toBe('0')
  expect(wrapper.text()).toContain(zh.error.BILLING_CONFLICT)
  expect(wrapper.find('form').exists()).toBe(true)
})
it('refreshes failure status and retains the last successful snapshot after a failed sync', async () => {
  const failed = response()
  const api = vi.spyOn(studyBillingApi, 'get').mockResolvedValue(response())
  const sync = vi
    .spyOn(studyBillingApi, 'sync')
    .mockRejectedValue({ code: 'BILLING_NETWORK', message: 'network' })
  const { wrapper } = await setup()
  api.mockResolvedValue({ ...failed, data: { ...failed.data, state: 'failed' } })
  await click(wrapper, zh.billing.sync)
  expect(sync).toHaveBeenCalledWith('s', 2)
  expect(wrapper.text()).toContain(zh.billing.states.failed)
  expect(wrapper.text()).toContain('0.1000000000001')
  expect(wrapper.text()).toContain(zh.error.BILLING_NETWORK)
})
it('paginates immutable source lines and rejects a mismatched response', async () => {
  vi.spyOn(studyBillingApi, 'get').mockResolvedValue(response())
  const source = vi.spyOn(studyBillingApi, 'evidence').mockResolvedValue(evidenceResponse())
  const { wrapper } = await setup()
  await click(wrapper, zh.billing.evidence)
  expect(wrapper.text()).toContain('<script>source</script>')
  expect(wrapper.find('script').exists()).toBe(false)
  const next = evidenceResponse(2)
  source.mockResolvedValue(next)
  wrapper.findComponent(UiPagination).vm.$emit('update:page', 2)
  await flushPromises()
  expect(source).toHaveBeenLastCalledWith('s', 'attempt', 2)
  source.mockResolvedValue({ ...next, data: { ...next.data, study_id: 'other' } })
  wrapper.findComponent(UiPagination).vm.$emit('update:page', 1)
  await flushPromises()
  expect(wrapper.text()).toContain(zh.billing.evidenceFailed)
  expect(wrapper.text()).not.toContain('<script>source</script>')
})
it('discards late responses after the research scope changes and never presents a missing snapshot as zero', async () => {
  let finish!: (value: ReturnType<typeof response>) => void
  const pending = new Promise<ReturnType<typeof response>>((resolve) => {
    finish = resolve
  })
  const api = vi.spyOn(studyBillingApi, 'get').mockReturnValueOnce(pending)
  const { wrapper } = await setup()
  const empty = response('other')
  api.mockResolvedValue({ ...empty, data: { ...empty.data, snapshot: null, state: 'missing' } })
  await wrapper.setProps({ studyId: 'other' })
  await flushPromises()
  finish(response())
  await flushPromises()
  expect(wrapper.text()).toContain(zh.billing.unknown)
  expect(wrapper.text()).not.toContain('0.1000000000001')
})
it('protects unsaved configuration when navigating away', async () => {
  vi.spyOn(studyBillingApi, 'get').mockResolvedValue(response())
  const { wrapper, router } = await setup()
  await click(wrapper, zh.billing.configure)
  const confirmLeave = vi.spyOn(confirm, 'confirmDialog').mockResolvedValue(false)
  await router.push('/research/other')
  expect(confirmLeave).toHaveBeenCalled()
  expect(router.currentRoute.value.path).toBe('/research/s')
  expect(wrapper.find('form').exists()).toBe(true)
})

it('refreshes stale admission status without issuing a sync and pauses while editing', async () => {
  vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })
  vi.spyOn(document, 'hidden', 'get').mockReturnValue(false)
  const api = vi.spyOn(studyBillingApi, 'get').mockResolvedValue(response())
  const sync = vi.spyOn(studyBillingApi, 'sync')
  const { wrapper } = await setup()
  api.mockResolvedValue({ ...response(), data: { ...response().data, state: 'stale' } })
  await vi.advanceTimersByTimeAsync(30_000)
  await flushPromises()
  expect(wrapper.text()).toContain(zh.billing.states.stale)
  expect(wrapper.text()).toContain(zh.billing.gateBlocked)
  expect(sync).not.toHaveBeenCalled()
  await click(wrapper, zh.billing.configure)
  const calls = api.mock.calls.length
  await vi.advanceTimersByTimeAsync(30_000)
  expect(api).toHaveBeenCalledTimes(calls)
})
