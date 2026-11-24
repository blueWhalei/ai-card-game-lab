/** @vitest-environment happy-dom */
import { afterEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, shallowMount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createI18n } from 'vue-i18n'
import { studyApi, type StudySummary } from '@/api/studyApi'
import zhCN from '@/i18n/locales/zh-CN'
import UiInput from '@/components/ui/Input.vue'
import UiTextarea from '@/components/ui/Textarea.vue'
import UiButton from '@/components/ui/Button.vue'
import StudyHomeView from './StudyHomeView.vue'

enableAutoUnmount(afterEach)
afterEach(() => vi.restoreAllMocks())
const record: StudySummary = {
  id: 'study-a',
  title: 'Prompt research',
  question: 'Does wording matter?',
  created_at: '2026',
  updated_at: '2026',
  last_activity_at: '2026',
  run_count: 2,
}
async function mountHome() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }],
  })
  await router.push('/')
  await router.isReady()
  const wrapper = shallowMount(StudyHomeView, {
    global: {
      renderStubDefaultSlot: true,
      plugins: [
        router,
        createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } }),
      ],
    },
  })
  await flushPromises()
  return { wrapper, router }
}
it('searches research questions and opens the selected research', async () => {
  vi.spyOn(studyApi, 'list').mockResolvedValue({
    code: 0,
    message: '',
    data: [record, { ...record, id: 'study-b', title: 'Baseline', question: 'Determinism' }],
  })
  const { wrapper, router } = await mountHome()
  wrapper.findAllComponents(UiInput)[0]!.vm.$emit('update:modelValue', 'determinism')
  await flushPromises()
  expect(wrapper.findAll('button[aria-pressed]')).toHaveLength(1)
  expect(wrapper.find('h2').text()).toBe('Baseline')
  wrapper
    .findAllComponents(UiButton)
    .find((b) => b.text().includes('进入研究'))!
    .vm.$emit('click')
  await flushPromises()
  expect(router.currentRoute.value.path).toBe('/research/study-b')
})
it('shows load failures as errors, retries, and creates research only on submit', async () => {
  vi.spyOn(studyApi, 'list')
    .mockRejectedValueOnce(new Error('offline'))
    .mockResolvedValue({ code: 0, message: '', data: [] })
  const create = vi
    .spyOn(studyApi, 'create')
    .mockResolvedValue({ code: 0, message: '', data: record })
  const { wrapper, router } = await mountHome()
  expect(wrapper.find('[role="alert"]').exists()).toBe(true)
  expect(wrapper.text()).not.toContain('从一个值得验证的问题开始')
  wrapper
    .findAllComponents(UiButton)
    .find((b) => b.text().includes('重试'))!
    .vm.$emit('click')
  await flushPromises()
  expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  expect(wrapper.text()).toContain('从一个值得验证的问题开始')
  wrapper.findComponent(UiInput).vm.$emit('update:modelValue', ' New question ')
  wrapper.findComponent(UiTextarea).vm.$emit('update:modelValue', ' Why? ')
  await flushPromises()
  expect(create).not.toHaveBeenCalled()
  await wrapper.find('form').trigger('submit')
  await flushPromises()
  expect(create).toHaveBeenCalledWith('New question', 'Why?')
  expect(router.currentRoute.value.path).toBe('/research/study-a')
})
