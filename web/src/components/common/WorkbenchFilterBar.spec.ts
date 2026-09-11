/** @vitest-environment happy-dom */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createI18n } from 'vue-i18n'
import { experimentConfigApi } from '@/api/experimentConfigApi'
import zhCN from '@/i18n/locales/zh-CN'
import UiSelect from '@/components/ui/Select.vue'
import WorkbenchFilterBar from './WorkbenchFilterBar.vue'

afterEach(() => vi.restoreAllMocks())

describe('decision trainability filter', () => {
  it('shows all records for explicit all links and preserves that choice on remount', async () => {
    vi.spyOn(experimentConfigApi, 'list').mockResolvedValue({ data: [] } as never)
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/decisions', component: { template: '<div />' } }],
    })
    await router.push('/decisions?train_usable=all')
    const options = {
      props: { mode: 'decision' as const },
      global: {
        plugins: [
          router,
          createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } }),
        ],
      },
    }
    let wrapper = shallowMount(WorkbenchFilterBar, options)
    await flushPromises()
    const select = () =>
      wrapper.findAllComponents(UiSelect).find((c) => c.props('placeholder') === '可训练')!
    expect(select().props('modelValue')).toBe('__all__')
    select().vm.$emit('update:modelValue', 'false')
    await flushPromises()
    expect(router.currentRoute.value.query.train_usable).toBe('false')
    select().vm.$emit('update:modelValue', '__all__')
    await flushPromises()
    expect(router.currentRoute.value.query.train_usable).toBe('all')
    const savedUrl = router.currentRoute.value.fullPath
    wrapper.unmount()
    await router.push(savedUrl)
    wrapper = shallowMount(WorkbenchFilterBar, options)
    await flushPromises()
    expect(select().props('modelValue')).toBe('__all__')
    expect(router.currentRoute.value.query.train_usable).toBe('all')
    wrapper.unmount()
  })
})
