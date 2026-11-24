/** @vitest-environment happy-dom */
import { afterEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, shallowMount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createRouter, createMemoryHistory, RouterLink } from 'vue-router'
import { createI18n } from 'vue-i18n'
import { trainingApi, type TrainingTaskPage, type TrainingTask } from '@/api/trainingApi'
import { systemApi } from '@/api/systemApi'
import { dataApi } from '@/api/dataApi'
import zh from '@/i18n/locales/zh-CN'
import UiButton from '@/components/ui/Button.vue'
import UiInput from '@/components/ui/Input.vue'
import UiSelect from '@/components/ui/Select.vue'
import TrainingView from './TrainingView.vue'
import { confirmDialog } from '@/components/ui/confirm'

vi.mock('@/components/ui/confirm', () => ({ confirmDialog: vi.fn(async () => true) }))
enableAutoUnmount(afterEach)
afterEach(() => {
  vi.restoreAllMocks()
  vi.clearAllMocks()
})
const response = (items: TrainingTask[] = []) => ({
  code: 0,
  message: '',
  data: {
    items,
    total: items.length,
    page: 1,
    page_size: 100,
    read_at: '2026-11-19T00:00:00Z',
    filters: { study_id: 's', experiment_id: 'run', task_id: 'target', state: 'all', status: null },
  } satisfies TrainingTaskPage,
})
async function setup(
  path = '/pipeline/training?study_id=s&experiment_id=run&task_id=target&task_study=s&task_kind=training&task_state=attention&task_page=2',
  pendingConfig = false,
) {
  vi.spyOn(systemApi, 'getConfig').mockResolvedValue({
    code: 0,
    message: '',
    data: {
      app_name: 'Test',
      version: 'test',
      debug: false,
      data_dir: 'test',
      config_file: 'test',
      sqlite_path: 'test',
      models_dir: 'test',
      training_deps_available: true,
      default_base_models: [],
    },
  } as Awaited<ReturnType<typeof systemApi.getConfig>>)
  if (pendingConfig) vi.mocked(systemApi.getConfig).mockImplementation(() => new Promise(() => {}))
  vi.spyOn(systemApi, 'preflight').mockResolvedValue({
    code: 0,
    message: '',
    data: { can_train: true, checks: [] },
  } as unknown as Awaited<ReturnType<typeof systemApi.preflight>>)
  vi.spyOn(trainingApi, 'listModels').mockResolvedValue({ code: 0, message: '', data: [] })
  vi.spyOn(dataApi, 'listDatasets').mockResolvedValue({ code: 0, message: '', data: [] })
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }],
  })
  await router.push(path)
  const wrapper = shallowMount(TrainingView, {
    global: {
      renderStubDefaultSlot: true,
      plugins: [
        createPinia(),
        router,
        createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zh } }),
      ],
      stubs: {
        UiDialog: {
          props: ['open'],
          template: '<div v-if="open"><slot/><slot name="footer"/></div>',
        },
      },
    },
  })
  await flushPromises()
  return { wrapper, router }
}
it('keeps exact task scope, shows unavailable and failure states, and retains research return', async () => {
  const list = vi.spyOn(trainingApi, 'listTasks').mockResolvedValue(response())
  const { wrapper, router } = await setup()
  expect(list).toHaveBeenCalledWith({
    page_size: 100,
    study_id: 's',
    experiment_id: 'run',
    task_id: 'target',
  })
  expect(wrapper.text()).toContain(zh.operations.trainingUnavailable)
  expect(wrapper.findComponent(RouterLink).props('to')).toMatchObject({
    path: '/research/s',
    query: { task_kind: 'training', task_state: 'attention', task_page: '2' },
  })
  list.mockRejectedValueOnce(new Error('offline'))
  await router.replace('/pipeline/training?study_id=s&task_id=next')
  await flushPromises()
  expect(wrapper.text()).toContain(zh.operations.trainingFailed)
  expect(wrapper.text()).not.toContain(zh.operations.trainingUnavailable)
  list.mockClear()
  await router.replace('/pipeline/training?task_id=a&task_id=b')
  await flushPromises()
  expect(list).not.toHaveBeenCalled()
  expect(wrapper.text()).toContain(zh.operations.invalidTrainingQuery)
})
it('preserves run ownership when creating and refreshes the original filter after confirmation', async () => {
  const list = vi.spyOn(trainingApi, 'listTasks').mockResolvedValue({
    ...response(),
    data: {
      ...response().data,
      filters: { ...response().data.filters, task_id: null, study_id: null },
    },
  })
  const create = vi
    .spyOn(trainingApi, 'createTask')
    .mockResolvedValue({ code: 0, message: '', data: { id: 'created' } as TrainingTask })
  const { wrapper } = await setup('/pipeline/training?experiment_id=run')
  const button = (text: string) =>
    wrapper.findAllComponents(UiButton).find((item) => item.text() === text)!
  button(zh.training.createTask).vm.$emit('click')
  await flushPromises()
  wrapper.findComponent(UiInput).vm.$emit('update:modelValue', 'New training')
  wrapper
    .findAllComponents(UiSelect)
    .find((item) => item.attributes('aria-label') === zh.training.dataset)!
    .vm.$emit('update:modelValue', 'dataset')
  await flushPromises()
  button(zh.common.create).vm.$emit('click')
  await flushPromises()
  expect(confirmDialog).toHaveBeenCalled()
  expect(create).toHaveBeenCalledWith(
    expect.objectContaining({ name: 'New training', dataset_id: 'dataset', experiment_id: 'run' }),
  )
  expect(list).toHaveBeenLastCalledWith({ page_size: 100, experiment_id: 'run' })
})

it('reads the selected task before environment checks finish, without a premature missing-task claim', async () => {
  const list = vi
    .spyOn(trainingApi, 'listTasks')
    .mockResolvedValue(
      response([{ id: 'target', name: 'Saved training', status: 'completed' } as TrainingTask]),
    )
  const { wrapper } = await setup(undefined, true)
  expect(list).toHaveBeenCalledWith({
    page_size: 100,
    study_id: 's',
    experiment_id: 'run',
    task_id: 'target',
  })
  expect(wrapper.text()).not.toContain(zh.operations.trainingUnavailable)
  expect(wrapper.text()).toContain('符合筛选的训练任务共 1 个')
})
