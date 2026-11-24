/** @vitest-environment happy-dom */
import { afterEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter } from 'vue-router'
import type { ResearchReport } from '@/api/researchApi'
import { promptDesignApi, type PromptDesignPreview } from '@/api/promptDesignApi'
import zhCN from '@/i18n/locales/zh-CN'
import ReportFollowup from './ReportFollowup.vue'

enableAutoUnmount(afterEach)
afterEach(() => vi.restoreAllMocks())
const report = (id: string) =>
  ({
    record: { id },
    comparison: { result: { experiments: [{ id: 'a', name: 'Frozen A' }] } },
  }) as ResearchReport
const response = (issues: string[] = []) => ({
  code: 0,
  message: '',
  data: {
    baseline: { id: 'a', study_id: 's' },
    source_conclusion: { id: 'r1' },
    issues,
  } as PromptDesignPreview,
})
async function setup() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      {
        path: '/research/:id/prompt-ab',
        name: 'prompt-design',
        component: { template: '<div />' },
      },
    ],
  })
  await router.push('/')
  const wrapper = mount(ReportFollowup, {
    props: { report: report('r1') },
    global: {
      plugins: [
        router,
        createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } }),
      ],
    },
  })
  await wrapper.get('button').trigger('click')
  await wrapper.get('select').setValue('a')
  return { wrapper, router }
}
it('checks the frozen member before navigating and never creates a run', async () => {
  vi.spyOn(promptDesignApi, 'preview').mockResolvedValue(response())
  const create = vi.spyOn(promptDesignApi, 'create')
  const { wrapper, router } = await setup()
  await wrapper.findAll('button')[1]!.trigger('click')
  await flushPromises()
  expect(promptDesignApi.preview).toHaveBeenCalledWith('a', 'r1')
  expect(router.currentRoute.value.query).toEqual({ baseline: 'a', source_revision: 'r1' })
  expect(router.currentRoute.value.params.id).toBe('s')
  expect(create).not.toHaveBeenCalled()
})
it('keeps ineligible conditions visible and permits retry after a read failure', async () => {
  vi.spyOn(promptDesignApi, 'preview')
    .mockRejectedValueOnce(new Error('missing'))
    .mockResolvedValue(response(['source_conditions_changed']))
  const { wrapper, router } = await setup()
  await wrapper.findAll('button')[1]!.trigger('click')
  await flushPromises()
  expect(wrapper.find('[role="alert"]').exists()).toBe(true)
  await wrapper.findAll('button')[1]!.trigger('click')
  await flushPromises()
  expect(wrapper.find('[role="status"]').text()).toContain('当前基线条件已不同于来源报告')
  expect(router.currentRoute.value.path).toBe('/')
})
it('does not navigate using a late response for a previous report', async () => {
  let finish!: (value: ReturnType<typeof response>) => void
  vi.spyOn(promptDesignApi, 'preview').mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve
      }),
  )
  const { wrapper, router } = await setup()
  await wrapper.findAll('button')[1]!.trigger('click')
  await wrapper.setProps({ report: report('r2') })
  finish(response())
  await flushPromises()
  expect(wrapper.find('select').exists()).toBe(false)
  expect(router.currentRoute.value.path).toBe('/')
})
