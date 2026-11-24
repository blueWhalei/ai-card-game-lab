/** @vitest-environment happy-dom */
import { afterEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter, matchedRouteKey } from 'vue-router'
import { computed } from 'vue'
import { createPinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import { studyFinanceApi, type StudyFinance as Finance } from '@/api/studyFinanceApi'
import StudyFinance from './StudyFinance.vue'
import UiPagination from '@/components/ui/Pagination.vue'
import * as confirm from '@/components/ui/confirm'
import zh from '@/i18n/locales/zh-CN'
import en from '@/i18n/locales/en'

enableAutoUnmount(afterEach)
afterEach(() => vi.restoreAllMocks())
function response(study = 's', page = 1) {
  return {
    code: 0,
    message: '',
    data: {
      study_id: study,
      page,
      page_size: 20,
      total: 21,
      active_count: 20,
      voided_count: 1,
      recorded_amount: '0.300001',
      budget_difference: '-0.000001',
      admission_blocked: true,
      budget: {
        study_id: study,
        revision: 2,
        currency: 'CNY',
        limit: '0.300000',
        enforcement_enabled: true,
        reason: 'Allocation review',
        created_at: '2026-11-19T00:00:00Z',
      },
      budget_history: [],
      read_at: '2026-11-19T00:00:00Z',
      items: [
        {
          id: 'e',
          study_id: study,
          request_id: 'q',
          currency: 'CNY',
          amount: '0.300001',
          incurred_on: '2026-11-19',
          source_type: 'provider_statement',
          source_reference: 'Provider / line 1',
          scope_description: '<script>source</script>',
          created_at: '2026-11-19T00:00:00Z',
          voided_at: null,
          void_reason: null,
        },
      ],
    } satisfies Finance,
  }
}
async function setup(locale = 'zh-CN', path = '/research/s?task_kind=finance&task_page=1') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:pathMatch(.*)*', component: StudyFinance }],
  })
  await router.push(path)
  const pinia = createPinia()
  const wrapper = mount(StudyFinance, {
    props: { studyId: 's' },
    global: {
      provide: {
        [matchedRouteKey as symbol]: computed(() => router.currentRoute.value.matched[0]),
      },
      plugins: [
        router,
        pinia,
        createI18n({ legacy: false, locale, messages: { 'zh-CN': zh, en } }),
      ],
      stubs: { UiPagination: true, Icon: true, StudyBilling: true },
    },
  })
  await flushPromises()
  return { wrapper, router, pinia }
}
type Wrapper = Awaited<ReturnType<typeof setup>>['wrapper']
async function click(wrapper: Wrapper, text: string) {
  await wrapper
    .findAll('button')
    .find((b) => b.text() === text)!
    .trigger('click')
  await flushPromises()
}

it.each(['zh-CN', 'en'])('shows exact amounts, provenance and limits in %s', async (locale) => {
  const api = vi.spyOn(studyFinanceApi, 'get').mockResolvedValue(response())
  const { wrapper } = await setup(locale)
  const copy = locale === 'en' ? en.finance : zh.finance
  expect(wrapper.text()).toContain('0.300001 CNY')
  expect(wrapper.text()).toContain('-0.000001 CNY')
  expect(wrapper.text()).toContain(copy.blocked)
  expect(wrapper.text()).toContain(copy.limits)
  expect(wrapper.text()).toContain('<script>source</script>')
  expect(wrapper.find('script').exists()).toBe(false)
  api.mockResolvedValueOnce(response('s', 2))
  wrapper.findComponent(UiPagination).vm.$emit('update:page', 2)
  await flushPromises()
  expect(api).toHaveBeenLastCalledWith('s', 2)
})

it('distinguishes absent entries from zero and rejects stale or mismatched scopes', async () => {
  let resolveOld!: (value: ReturnType<typeof response>) => void
  const oldPromise = new Promise<ReturnType<typeof response>>((resolve) => {
    resolveOld = resolve
  })
  const api = vi
    .spyOn(studyFinanceApi, 'get')
    .mockReturnValueOnce(oldPromise)
    .mockResolvedValue(response('new'))
  const { wrapper } = await setup()
  await wrapper.setProps({ studyId: 'new' })
  await flushPromises()
  resolveOld(response())
  await flushPromises()
  expect(wrapper.text()).toContain('0.300001')
  const empty = response('new')
  empty.data.recorded_amount = null as unknown as string
  empty.data.items = []
  empty.data.total = empty.data.active_count = empty.data.voided_count = 0
  api.mockResolvedValueOnce(empty)
  await click(wrapper, zh.study.refresh)
  expect(wrapper.text()).toContain(zh.finance.noAmount)
  api.mockResolvedValueOnce(response('wrong'))
  await click(wrapper, zh.study.refresh)
  expect(wrapper.text()).toContain(zh.finance.loadFailed)
  expect(wrapper.text()).not.toContain('0.300001')
  api.mockResolvedValueOnce({
    ...response('new'),
    data: { ...response('new').data, recorded_amount: '0.000000' },
  })
  await click(wrapper, zh.common.retry)
  expect(wrapper.text()).toContain('0.000000 CNY')
})

it('retains conflicting budget input and reloads only explicitly, with close protection', async () => {
  vi.spyOn(studyFinanceApi, 'get').mockResolvedValue(response())
  const save = vi
    .spyOn(studyFinanceApi, 'setBudget')
    .mockRejectedValue({ code: 'BUDGET_CONFLICT', message: 'Conflict' })
  const { wrapper } = await setup()
  await click(wrapper, zh.finance.editBudget)
  await wrapper.find('input').setValue('0')
  await wrapper.find('textarea').setValue('Pause new admissions')
  await wrapper.find('form').trigger('submit')
  await flushPromises()
  expect(save).toHaveBeenCalledWith(
    's',
    expect.objectContaining({ expected_revision: 2, limit: '0', reason: 'Pause new admissions' }),
  )
  expect((wrapper.find('input').element as HTMLInputElement).value).toBe('0')
  expect(wrapper.text()).toContain(zh.error.BUDGET_CONFLICT)
  const event = new Event('beforeunload', { cancelable: true })
  window.dispatchEvent(event)
  expect(event.defaultPrevented).toBe(true)
  vi.spyOn(confirm, 'confirmDialog').mockResolvedValue(true)
  await click(wrapper, zh.finance.reloadBudget)
  expect((wrapper.find('input').element as HTMLInputElement).value).toBe('0.300000')
})

it('retains expense inputs after failure and reuses the request ID on unchanged retry', async () => {
  vi.spyOn(studyFinanceApi, 'get').mockResolvedValue(response())
  const add = vi
    .spyOn(studyFinanceApi, 'addExpense')
    .mockRejectedValue({ code: 'NETWORK_ERROR', message: 'Lost response' })
  const { wrapper } = await setup()
  await click(wrapper, zh.finance.addExpense)
  const inputs = wrapper.findAll('input')
  await inputs[0]!.setValue('0.000001')
  await inputs[1]!.setValue('2026-11-19')
  await inputs[2]!.setValue('Provider / line 2')
  await wrapper.find('textarea').setValue('One billed line assigned once')
  for (let i = 0; i < 2; i++) {
    await wrapper.find('form').trigger('submit')
    await flushPromises()
  }
  expect(add).toHaveBeenCalledTimes(2)
  expect(add.mock.calls[0]![1]).toEqual(add.mock.calls[1]![1])
  expect(add.mock.calls[0]![1].amount).toBe('0.000001')
  await inputs[0]!.setValue('1e6')
  await wrapper.find('form').trigger('submit')
  await flushPromises()
  expect(add).toHaveBeenCalledTimes(2)
  expect(wrapper.text()).toContain(zh.finance.invalidAmount)
})

it('requires a reason and explicit confirmation before voiding an expense', async () => {
  vi.spyOn(studyFinanceApi, 'get').mockResolvedValue(response())
  const mutation = vi
    .spyOn(studyFinanceApi, 'voidExpense')
    .mockResolvedValue({ code: 0, message: '', data: response().data.items[0]! })
  const { wrapper } = await setup()
  await click(wrapper, zh.finance.void)
  expect(mutation).not.toHaveBeenCalled()
  await wrapper.find('form').trigger('submit')
  expect(mutation).not.toHaveBeenCalled()
  await wrapper.find('textarea').setValue('Duplicate statement and receipt')
  await wrapper.find('form').trigger('submit')
  await flushPromises()
  expect(mutation).toHaveBeenCalledWith('s', 'e', 'Duplicate statement and receipt')
  expect(wrapper.text()).toContain(zh.finance.saved)
})

it('does not widen an invalid page into the first page', async () => {
  const api = vi.spyOn(studyFinanceApi, 'get')
  const { wrapper } = await setup('zh-CN', '/research/s?task_kind=finance&task_page=0')
  expect(api).not.toHaveBeenCalled()
  expect(wrapper.text()).toContain(zh.operations.invalidPosition)
})
