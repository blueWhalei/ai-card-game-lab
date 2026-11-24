/** @vitest-environment happy-dom */
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { shallowMount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import { draftApi } from '@/api/draftApi'
import type { Experiment } from '@/api/experimentApi'
import UiTextarea from '@/components/ui/Textarea.vue'
import { useDraftStore } from '@/stores/useDraftStore'
import zhCN from '@/i18n/locales/zh-CN'
import ExperimentNotebookPanel from './ExperimentNotebookPanel.vue'

enableAutoUnmount(afterEach)
beforeEach(() => {
  setActivePinia(createPinia())
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
})
afterEach(async () => {
  await vi.runOnlyPendingTimersAsync()
  vi.useRealTimers()
  vi.restoreAllMocks()
})

it('keeps the draft through polling, dialog unmount and reopening', async () => {
  vi.spyOn(draftApi, 'get').mockResolvedValue({
    code: 0,
    message: 'success',
    data: {
      revision: 3,
      updated_at: '2026',
      content: {
        kind: 'experiment',
        hypothesis: 'restored hypothesis',
        notes: '',
        conclusion: '',
        tags_input: '',
      },
    },
  })
  const save = vi
    .spyOn(draftApi, 'save')
    .mockImplementation(async (_kind, _id, revision, content) => ({
      code: 0,
      message: 'success',
      data: { revision: revision + 1, updated_at: '2026', content },
    }))
  const experiment = {
    id: 'e',
    hypothesis: 'applied hypothesis',
    notes: '',
    conclusion: '',
    tags: [],
    timeline: [],
  } as unknown as Experiment
  const options = {
    props: { experiment, flat: true },
    global: {
      renderStubDefaultSlot: true,
      plugins: [createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })],
    },
  }
  const wrapper = shallowMount(ExperimentNotebookPanel, options)
  await flushPromises()
  expect(wrapper.findAllComponents(UiTextarea)[0]!.props('modelValue')).toBe('restored hypothesis')
  wrapper.findAllComponents(UiTextarea)[0]!.vm.$emit('update:modelValue', 'my unsaved edit')
  await wrapper.setProps({ experiment: { ...experiment, hypothesis: 'polled source text' } })
  expect(wrapper.findAllComponents(UiTextarea)[0]!.props('modelValue')).toBe('my unsaved edit')
  wrapper.unmount()
  expect(await useDraftStore().flushAll()).toBe(true)
  const reopened = shallowMount(ExperimentNotebookPanel, options)
  await flushPromises()
  expect(reopened.findAllComponents(UiTextarea)[0]!.props('modelValue')).toBe('my unsaved edit')
  expect(save).toHaveBeenCalledTimes(1)
})
