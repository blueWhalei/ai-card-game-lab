/** @vitest-environment happy-dom */
import { afterEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, shallowMount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createRouter, createMemoryHistory } from 'vue-router'
import { studyApi } from '@/api/studyApi'
import zhCN from '@/i18n/locales/zh-CN'
import UiButton from '@/components/ui/Button.vue'
import UiDialog from '@/components/ui/Dialog.vue'
import ResearchOperations from '@/components/experiment/ResearchOperations.vue'
import StudyWorkspaceView from './StudyWorkspaceView.vue'

enableAutoUnmount(afterEach)
afterEach(() => vi.restoreAllMocks())
it('opens tasks only on demand and restores the selected task location without starting work', async () => {
  vi.spyOn(studyApi, 'get').mockImplementation(async (id) => ({
    code: 0,
    message: '',
    data: {
      id,
      title: 'Research',
      question: '',
      created_at: '',
      updated_at: '',
      runs: [],
      comparisons: [],
    },
  }))
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/research/:id', component: { template: '<div />' } }],
  })
  await router.push('/research/s')
  const wrapper = shallowMount(StudyWorkspaceView, {
    global: {
      renderStubDefaultSlot: true,
      plugins: [
        router,
        createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } }),
      ],
    },
  })
  await flushPromises()
  expect(wrapper.findComponent(ResearchOperations).exists()).toBe(false)
  wrapper
    .findAllComponents(UiButton)
    .find((button) => button.text() === zhCN.operations.title)!
    .vm.$emit('click')
  await flushPromises()
  expect(wrapper.findComponent(ResearchOperations).props('studyId')).toBe('s')
  await router.replace('/research/next?panel=operations&task_state=attention&task_page=2')
  await flushPromises()
  expect(wrapper.findComponent(ResearchOperations).props('studyId')).toBe('next')
  wrapper
    .findAllComponents(UiDialog)
    .find((dialog) => dialog.props('title') === zhCN.operations.title)!
    .vm.$emit('update:open', false)
  await flushPromises()
  expect(wrapper.findComponent(ResearchOperations).exists()).toBe(false)
  expect(router.currentRoute.value.query).toEqual({ task_state: 'attention', task_page: '2' })
})
