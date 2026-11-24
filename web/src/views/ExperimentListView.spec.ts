/** @vitest-environment happy-dom */
import { afterEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, shallowMount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createI18n } from 'vue-i18n'
import { studyApi, type StudyDetail } from '@/api/studyApi'
import { experimentApi } from '@/api/experimentApi'
import { experimentConfigApi } from '@/api/experimentConfigApi'
import { systemApi } from '@/api/systemApi'
import type { ApiResponse } from '@/api/types'
import zhCN from '@/i18n/locales/zh-CN'
import ExperimentListView from './ExperimentListView.vue'

enableAutoUnmount(afterEach)
afterEach(() => vi.restoreAllMocks())
it('ignores a late study response and clears scope when returning to all runs', async () => {
  vi.spyOn(experimentApi, 'list').mockResolvedValue({ code: 0, message: '', data: [] })
  vi.spyOn(experimentConfigApi, 'list').mockResolvedValue({ code: 0, message: '', data: [] })
  vi.spyOn(systemApi, 'listEngines').mockResolvedValue({ code: 0, message: '', data: [] })
  let resolveFirst!: (value: ApiResponse<StudyDetail>) => void
  const first = new Promise<ApiResponse<StudyDetail>>((resolve) => {
    resolveFirst = resolve
  })
  const study: StudyDetail = {
    id: 'b',
    title: 'Research B',
    question: '',
    created_at: '',
    updated_at: '',
    runs: [],
    comparisons: [],
  }
  vi.spyOn(studyApi, 'get').mockImplementation((id) =>
    id === 'a' ? first : Promise.resolve({ code: 0, message: '', data: study }),
  )
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/experiments', component: { template: '<div />' } }],
  })
  await router.push('/experiments?study=a')
  await router.isReady()
  const wrapper = shallowMount(ExperimentListView, {
    global: {
      renderStubDefaultSlot: true,
      plugins: [
        router,
        createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } }),
      ],
    },
  })
  await router.push('/experiments?study=b')
  await flushPromises()
  expect(wrapper.text()).toContain('当前研究：Research B')
  resolveFirst({ code: 0, message: '', data: { ...study, id: 'a', title: 'Research A' } })
  await flushPromises()
  expect(wrapper.text()).not.toContain('Research A')
  await router.push('/experiments')
  await flushPromises()
  expect(wrapper.text()).not.toContain('当前研究：')
})
