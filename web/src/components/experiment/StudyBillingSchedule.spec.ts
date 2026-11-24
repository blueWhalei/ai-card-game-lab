/** @vitest-environment happy-dom */
import { afterEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { computed } from 'vue'
import { createMemoryHistory, createRouter, matchedRouteKey } from 'vue-router'
import { createPinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import {
  studyBillingApi,
  type BillingScheduleOverview,
  type BillingSchedulePlan,
} from '@/api/studyBillingApi'
import StudyBillingSchedule from './StudyBillingSchedule.vue'
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
      config: {
        study_id: id,
        revision: 2,
        organization_id: 'org-test',
        project_id: 'proj_test',
        start_date: '2026-11-01',
        limit_amount: '1',
        enforcement_enabled: true,
        max_age_hours: 6,
        reason: 'Fixture',
        created_at: '2026-11-19T00:00:00Z',
      },
      plan: null,
      state: 'not_configured',
      checked_at: null,
      worker_enabled: true,
      worker_recent: false,
      history: [],
      read_at: '2026-11-19T00:00:02Z',
    } satisfies BillingScheduleOverview,
  }
}
function plan(): BillingSchedulePlan {
  return {
    study_id: 's',
    revision: 1,
    config_revision: 2,
    enabled: true,
    interval_minutes: 60,
    reason: 'Reviewed scope',
    created_at: '2026-11-19T00:00:00Z',
    next_due_at: '2026-11-19T01:00:00Z',
    last_attempt_id: null,
    consecutive_failures: 0,
    error_code: null,
    updated_at: '2026-11-19T00:00:00Z',
  }
}
async function setup(locale = 'zh-CN') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:pathMatch(.*)*', component: StudyBillingSchedule }],
  })
  await router.push('/research/s?task_kind=finance')
  const wrapper = mount(StudyBillingSchedule, {
    props: { studyId: 's', configRevision: 2, disabled: false },
    global: {
      provide: {
        [matchedRouteKey as symbol]: computed(() => router.currentRoute.value.matched[0]),
      },
      plugins: [
        router,
        createPinia(),
        createI18n({ legacy: false, locale, messages: { 'zh-CN': zh, en } }),
      ],
      stubs: { Icon: true },
    },
  })
  await flushPromises()
  return { wrapper, router }
}
type Wrapper = Awaited<ReturnType<typeof setup>>['wrapper']
async function click(wrapper: Wrapper, text: string) {
  const button = wrapper.findAll('button').find((button) => button.text() === text)
  expect(button, text).toBeDefined()
  await button!.trigger('click')
  await flushPromises()
}

it.each(['zh-CN', 'en'])(
  'shows default-off plans and cost limits in %s without starting a sync',
  async (locale) => {
    vi.spyOn(studyBillingApi, 'schedule').mockResolvedValue(response())
    const save = vi.spyOn(studyBillingApi, 'setSchedule'),
      sync = vi.spyOn(studyBillingApi, 'sync')
    const { wrapper } = await setup(locale)
    const copy = locale === 'en' ? en.billing.schedule : zh.billing.schedule
    expect(wrapper.text()).toContain(copy.scope)
    expect(wrapper.text()).toContain(copy.budget)
    expect(wrapper.text()).toContain(copy.workerUnknown)
    expect(wrapper.text()).toContain(copy.states.not_configured)
    expect(save).not.toHaveBeenCalled()
    expect(sync).not.toHaveBeenCalled()
  },
)
it('saves an explicitly enabled plan against its captured cost version', async () => {
  const read = vi.spyOn(studyBillingApi, 'schedule').mockResolvedValue(response())
  const save = vi
    .spyOn(studyBillingApi, 'setSchedule')
    .mockResolvedValue({ code: 0, message: '', data: plan() })
  const { wrapper } = await setup()
  await click(wrapper, zh.billing.schedule.edit)
  await wrapper.find('[role="checkbox"]').trigger('click')
  await wrapper.find('input').setValue('30')
  await wrapper.find('textarea').setValue('Review period and scope')
  read.mockResolvedValue({
    ...response(),
    data: { ...response().data, plan: plan(), state: 'due' },
  })
  await wrapper.find('form').trigger('submit')
  await flushPromises()
  expect(save).toHaveBeenCalledWith('s', {
    expected_revision: 0,
    expected_config_revision: 2,
    enabled: true,
    interval_minutes: 30,
    reason: 'Review period and scope',
  })
  expect(wrapper.text()).toContain(zh.billing.schedule.saved)
  expect(wrapper.emitted('saved')).toHaveLength(1)
})
it('keeps edits and captured versions on a conflict and refuses silent navigation', async () => {
  vi.spyOn(studyBillingApi, 'schedule').mockResolvedValue(response())
  vi.spyOn(studyBillingApi, 'setSchedule').mockRejectedValue({
    code: 'BILLING_SCHEDULE_CONFLICT',
    message: 'conflict',
  })
  const { wrapper, router } = await setup()
  await click(wrapper, zh.billing.schedule.edit)
  await wrapper.find('input').setValue('45')
  await wrapper.find('textarea').setValue('Keep this reason')
  await wrapper.find('form').trigger('submit')
  await flushPromises()
  expect((wrapper.find('input').element as HTMLInputElement).value).toBe('45')
  expect(wrapper.text()).toContain(zh.error.BILLING_SCHEDULE_CONFLICT)
  vi.spyOn(confirm, 'confirmDialog').mockResolvedValue(false)
  await router.push('/research/other')
  expect(router.currentRoute.value.path).toBe('/research/s')
})
it('polls status without creating jobs and suspends polling while editing', async () => {
  vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })
  vi.spyOn(document, 'hidden', 'get').mockReturnValue(false)
  const read = vi.spyOn(studyBillingApi, 'schedule').mockResolvedValue(response())
  const sync = vi.spyOn(studyBillingApi, 'sync')
  const { wrapper } = await setup()
  read.mockResolvedValue({
    ...response(),
    data: {
      ...response().data,
      plan: { ...plan(), error_code: 'BILLING_NETWORK', consecutive_failures: 1 },
      state: 'retry_wait',
    },
  })
  await vi.advanceTimersByTimeAsync(30_000)
  await flushPromises()
  expect(wrapper.text()).toContain(zh.billing.schedule.states.retry_wait)
  await click(wrapper, zh.billing.schedule.edit)
  const count = read.mock.calls.length
  await vi.advanceTimersByTimeAsync(60_000)
  expect(read).toHaveBeenCalledTimes(count)
  expect(sync).not.toHaveBeenCalled()
})
it('isolates late responses and never turns a read failure into disabled scheduling', async () => {
  let resolve!: (value: ReturnType<typeof response>) => void
  const pending = new Promise<ReturnType<typeof response>>((done) => {
    resolve = done
  })
  const read = vi.spyOn(studyBillingApi, 'schedule').mockReturnValueOnce(pending)
  const { wrapper } = await setup()
  read.mockRejectedValue(new Error('unavailable'))
  await wrapper.setProps({ studyId: 'other' })
  await flushPromises()
  resolve(response())
  await flushPromises()
  expect(wrapper.text()).toContain(zh.billing.schedule.loadFailed)
  expect(wrapper.text()).not.toContain(zh.billing.schedule.states.not_configured)
})
it('refreshes changed cost configuration and requires an explicit plan save', async () => {
  const read = vi.spyOn(studyBillingApi, 'schedule').mockResolvedValue(response())
  const save = vi.spyOn(studyBillingApi, 'setSchedule')
  const { wrapper } = await setup()
  read.mockResolvedValue({
    ...response(),
    data: { ...response().data, plan: plan(), state: 'scope_changed' },
  })
  await wrapper.setProps({ configRevision: 3 })
  await flushPromises()
  expect(wrapper.text()).toContain(zh.billing.schedule.states.scope_changed)
  expect(save).not.toHaveBeenCalled()
})
