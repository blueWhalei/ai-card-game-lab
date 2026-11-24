/** @vitest-environment happy-dom */
import { afterEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, shallowMount } from '@vue/test-utils'
import { createRouter, createMemoryHistory, RouterLink } from 'vue-router'
import { createI18n } from 'vue-i18n'
import { trainingApi, type TrainingTask, type TrainingTaskPage } from '@/api/trainingApi'
import zh from '@/i18n/locales/zh-CN'
import en from '@/i18n/locales/en'
import StudyTrainingOperations from './StudyTrainingOperations.vue'
import ResearchOperations from './ResearchOperations.vue'
import StudyOperations from './StudyOperations.vue'
import UiButton from '@/components/ui/Button.vue'
import UiPagination from '@/components/ui/Pagination.vue'

enableAutoUnmount(afterEach)
afterEach(() => vi.restoreAllMocks())
function response(study = 's', state = 'all', page = 1) {
  return {
    code: 0,
    message: '',
    data: {
      items: [
        {
          id: 'training',
          name: 'Target task',
          study_id: study,
          experiment_id: 'run',
          run_name: 'Run',
          dataset_id: 'ds',
          base_model: 'Base',
          training_type: 'sft',
          status: 'failed',
          progress: null,
          progress_state: 'missing',
          result_state: 'recorded',
          result: { error: '<script>recorded error</script>' },
          created_at: '2026-11-19T00:00:00Z',
          config: {
            learning_rate: 0.00002,
            batch_size: 1,
            num_epochs: 1,
            output_format: 'pytorch',
          },
          model_path: null,
          finished_at: null,
        } as TrainingTask,
        {
          id: 'zero',
          name: 'Zero',
          status: 'completed',
          progress: 0,
          progress_state: 'recorded',
          result: null,
        } as TrainingTask,
        {
          id: 'bad',
          name: 'Invalid',
          status: 'unexpected',
          progress: null,
          progress_state: 'invalid',
          result_state: 'invalid',
          result: null,
        } as TrainingTask,
      ],
      total: 21,
      page,
      page_size: 20,
      read_at: '2026-11-19T00:00:00Z',
      filters: { study_id: study, state, experiment_id: null, task_id: null, status: null },
    } satisfies TrainingTaskPage,
  }
}
async function setup(locale = 'zh-CN', path = '/research/s?panel=operations&task_kind=training') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }],
  })
  await router.push(path)
  const wrapper = shallowMount(StudyTrainingOperations, {
    props: { studyId: 's' },
    global: {
      plugins: [router, createI18n({ legacy: false, locale, messages: { 'zh-CN': zh, en } })],
      stubs: { UiButton: false },
    },
  })
  await flushPromises()
  return { router, wrapper }
}
it.each(['zh-CN', 'en'])(
  'preserves missing, zero and invalid fields and exact task links in %s',
  async (locale) => {
    vi.spyOn(trainingApi, 'listTasks').mockResolvedValue(response())
    const { wrapper } = await setup(locale)
    const copy = locale === 'en' ? en.operations : zh.operations
    expect(wrapper.text()).toContain(copy.missing)
    expect(wrapper.text()).toContain('0%')
    expect(wrapper.text()).toContain(copy.invalidProgress)
    expect(wrapper.text()).toContain(copy.invalidResult)
    expect(wrapper.text()).toContain(copy.trainingLimit)
    expect(wrapper.find('script').exists()).toBe(false)
    expect(wrapper.findAllComponents(RouterLink)[0]!.props('to')).toMatchObject({
      path: '/pipeline/training',
      query: {
        study_id: 's',
        experiment_id: 'run',
        task_id: 'training',
        task_kind: 'training',
        task_page: '1',
      },
    })
  },
)
it('filters before paging, rejects late and mismatched responses and retries failures', async () => {
  let resolveOld!: (value: ReturnType<typeof response>) => void
  const old = new Promise<ReturnType<typeof response>>((resolve) => {
    resolveOld = resolve
  })
  const api = vi
    .spyOn(trainingApi, 'listTasks')
    .mockReturnValueOnce(old)
    .mockImplementation(async (p) =>
      response(String(p?.study_id), String(p?.state), Number(p?.page)),
    )
  const { wrapper, router } = await setup()
  await wrapper.get('button:nth-child(2)').trigger('click')
  await flushPromises()
  expect(router.currentRoute.value.query.task_state).toBe('active')
  resolveOld(response('s', 'all'))
  await flushPromises()
  expect(wrapper.text()).toContain('Target task')
  wrapper.findComponent(UiPagination).vm.$emit('update:page', 2)
  await flushPromises()
  expect(api).toHaveBeenLastCalledWith({ study_id: 's', state: 'active', page: 2, page_size: 20 })
  api.mockResolvedValueOnce(response('wrong'))
  await wrapper.setProps({ studyId: 'next' })
  await flushPromises()
  expect(wrapper.text()).toContain(zh.operations.trainingFailed)
  expect(wrapper.text()).not.toContain('Target task')
  await wrapper
    .findAll('button')
    .find((b) => b.text() === zh.common.retry)!
    .trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('Target task')
})
it('switches task type without keeping another type’s page or mounting both lists', async () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }],
  })
  await router.push('/research/s?task_state=attention&task_page=4')
  const wrapper = shallowMount(ResearchOperations, {
    props: { studyId: 's' },
    global: {
      plugins: [router, createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zh } })],
    },
  })
  expect(wrapper.findComponent(StudyOperations).exists()).toBe(true)
  wrapper.findAllComponents(UiButton)[1]!.vm.$emit('click')
  await flushPromises()
  expect(router.currentRoute.value.query).toEqual({
    task_kind: 'training',
    task_state: 'all',
    task_page: '1',
  })
  expect(wrapper.findComponent(StudyOperations).exists()).toBe(false)
  expect(wrapper.findComponent(StudyTrainingOperations).exists()).toBe(true)
})
