/** @vitest-environment happy-dom */
import { afterEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, shallowMount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createRouter, createMemoryHistory, RouterLink } from 'vue-router'
import { studyApi, type StudyOperations as Operations, type OperationFilter } from '@/api/studyApi'
import zhCN from '@/i18n/locales/zh-CN'
import en from '@/i18n/locales/en'
import StudyOperations from './StudyOperations.vue'
import UiPagination from '@/components/ui/Pagination.vue'

enableAutoUnmount(afterEach)
afterEach(() => vi.restoreAllMocks())
const response = (state: OperationFilter = 'all', page = 1, studyId = 's') => ({
  code: 0,
  message: '',
  data: {
    study_id: studyId,
    state,
    page,
    page_size: 20,
    total: 21,
    read_at: '2026-11-09T00:00:00Z',
    items: [
      {
        id: 'run',
        name: 'Observed run',
        target_games: 2,
        game_count: 3,
        states: {
          waiting: 0,
          running: 1,
          paused: 0,
          finished: 1,
          failed: 1,
          interrupted: 0,
          cancelled: 0,
          unknown: 0,
        },
        no_bid_count: 1,
        trace_count: 3,
        usage: {
          prompt_tokens: {
            value: 0,
            recorded_count: 1,
            missing_count: 1,
            invalid_count: 1,
            overflow: false,
          },
          completion_tokens: {
            value: null,
            recorded_count: 0,
            missing_count: 3,
            invalid_count: 0,
            overflow: false,
          },
          total_tokens: {
            value: null,
            recorded_count: 3,
            missing_count: 0,
            invalid_count: 0,
            overflow: true,
          },
        },
      },
    ],
  } satisfies Operations,
})
async function setup(locale = 'zh-CN', query = '') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }],
  })
  await router.push(`/research/s?panel=operations${query}`)
  const wrapper = shallowMount(StudyOperations, {
    props: { studyId: 's' },
    global: {
      plugins: [router, createI18n({ legacy: false, locale, messages: { 'zh-CN': zhCN, en } })],
      stubs: { UiButton: false },
    },
  })
  await flushPromises()
  return { router, wrapper }
}
it.each(['zh-CN', 'en'])(
  'separates missing values, zero, overflow and completeness in %s',
  async (locale) => {
    vi.spyOn(studyApi, 'operations').mockResolvedValue(response())
    const { wrapper } = await setup(locale)
    const copy = locale === 'en' ? en.operations : zhCN.operations
    expect(wrapper.text()).toContain(copy.scope)
    expect(wrapper.text()).toContain(copy.usageScope)
    expect(wrapper.text()).toContain(copy.missing)
    expect(wrapper.text()).toContain(copy.overflow)
    expect(wrapper.findAll('dd').some((cell) => cell.text() === '0')).toBe(true)
    expect(wrapper.findComponent(RouterLink).props('to')).toEqual({
      path: '/experiments/run',
      query: { task_study: 's', task_state: 'all', task_page: '1' },
    })
    expect(studyApi.operations).toHaveBeenCalledOnce()
  },
)
it('pages within the selected scope and resets the page when switching filters', async () => {
  vi.spyOn(studyApi, 'operations').mockImplementation(async (id, state, page) =>
    response(state, page, id),
  )
  const { wrapper, router } = await setup()
  wrapper.findComponent(UiPagination).vm.$emit('update:page', 2)
  await flushPromises()
  expect(studyApi.operations).toHaveBeenLastCalledWith('s', 'all', 2)
  await wrapper
    .findAll('button')
    .find((b) => b.text() === zhCN.operations.filters.attention)!
    .trigger('click')
  await flushPromises()
  expect(router.currentRoute.value.query).toEqual({
    panel: 'operations',
    task_state: 'attention',
    task_page: '1',
  })
  expect(studyApi.operations).toHaveBeenLastCalledWith('s', 'attention', 1)
})
it('clears old results, rejects wrong identity, retries, and ignores late reads', async () => {
  vi.spyOn(studyApi, 'operations').mockResolvedValue(response())
  const { wrapper } = await setup()
  let finish!: (value: ReturnType<typeof response>) => void
  vi.mocked(studyApi.operations).mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve
      }),
  )
  await wrapper.setProps({ studyId: 'slow' })
  expect(wrapper.find('article').exists()).toBe(false)
  vi.mocked(studyApi.operations).mockResolvedValueOnce(response('all', 1, 'new'))
  await wrapper.setProps({ studyId: 'new' })
  await flushPromises()
  finish(response('all', 1, 'slow'))
  await flushPromises()
  expect(wrapper.findComponent(RouterLink).props('to')).toMatchObject({
    query: { task_study: 'new' },
  })
  await wrapper.setProps({ studyId: 'wrong' })
  await flushPromises()
  expect(wrapper.find('article').exists()).toBe(false)
  expect(wrapper.get('[role="alert"]').text()).toContain(zhCN.operations.failed)
  vi.mocked(studyApi.operations).mockResolvedValueOnce(response('all', 1, 'wrong'))
  await wrapper
    .findAll('button')
    .find((b) => b.text() === zhCN.common.retry)!
    .trigger('click')
  await flushPromises()
  expect(wrapper.find('[role="alert"]').exists()).toBe(false)
})
it('does not read an invalid position and distinguishes empty pages from empty results', async () => {
  const spy = vi
    .spyOn(studyApi, 'operations')
    .mockResolvedValue({ ...response(), data: { ...response().data, items: [] } })
  const { wrapper, router } = await setup('zh-CN', '&task_page=0')
  expect(spy).not.toHaveBeenCalled()
  expect(wrapper.get('[role="alert"]').text()).toBe(zhCN.operations.invalidPosition)
  await router.replace('/research/s?panel=operations')
  await flushPromises()
  expect(wrapper.text()).toContain(zhCN.operations.pageEmpty)
  spy.mockResolvedValueOnce({
    ...response('attention'),
    data: { ...response('attention').data, total: 0, items: [] },
  })
  await router.replace('/research/s?panel=operations&task_state=attention')
  await flushPromises()
  expect(wrapper.text()).toContain(zhCN.operations.empty)
})
