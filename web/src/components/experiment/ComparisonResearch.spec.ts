/** @vitest-environment happy-dom */
import { afterEach, expect, it, vi } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { researchApi } from '@/api/researchApi'
import UiButton from '@/components/ui/Button.vue'
import UiTextarea from '@/components/ui/Textarea.vue'
import zhCN from '@/i18n/locales/zh-CN'
import ComparisonResearch from './ComparisonResearch.vue'

afterEach(() => vi.restoreAllMocks())
it('preserves the draft after a revision conflict and never saves on mount', async () => {
  vi.spyOn(researchApi, 'versions').mockResolvedValue({ data: [] } as never)
  vi.spyOn(researchApi, 'candidates').mockResolvedValue({ data: { total: 0, items: [] } } as never)
  const save = vi.spyOn(researchApi, 'save').mockRejectedValue({ message: '结论已有新版本' })
  const wrapper = shallowMount(ComparisonResearch, {
    props: { comparisonId: 'cmp' },
    global: {
      renderStubDefaultSlot: true,
      plugins: [createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })],
    },
  })
  await flushPromises()
  expect(save).not.toHaveBeenCalled()
  const inputs = wrapper.findAllComponents(UiTextarea)
  inputs[0]!.vm.$emit('update:modelValue', 'Observation')
  inputs[2]!.vm.$emit('update:modelValue', 'Small sample')
  await flushPromises()
  wrapper
    .findAllComponents(UiButton)
    .find((b) => b.text() === '保存新版本')!
    .vm.$emit('click')
  await flushPromises()
  expect(save).toHaveBeenCalledWith('cmp', {
    expected_revision: 0,
    observations: 'Observation',
    interpretation: '',
    limitations: 'Small sample',
    evidence: [],
  })
  expect(wrapper.find('[role="alert"]').text()).toContain('结论已有新版本')
  expect(wrapper.findAllComponents(UiTextarea)[0]!.props('modelValue')).toBe('Observation')
})

it('keeps deleted evidence readable and removes its original decision link', async () => {
  vi.spyOn(researchApi, 'versions').mockResolvedValue({
    data: [{ id: 'rev', revision: 1, created_at: '' }],
  } as never)
  vi.spyOn(researchApi, 'candidates').mockResolvedValue({ data: { total: 0, items: [] } } as never)
  vi.spyOn(researchApi, 'get').mockResolvedValue({
    data: {
      record: {
        id: 'rev',
        revision: 1,
        observations: 'Saved observation',
        interpretation: '',
        limitations: 'Limited',
        evidence: [
          {
            note: 'Evidence note',
            decision: { id: 'd', game_id: 'g', player_id: 'p', round_number: 1, action_id: 'pass' },
          },
        ],
      },
      evidence_status: { d: 'missing' },
    },
  } as never)
  const wrapper = shallowMount(ComparisonResearch, {
    props: { comparisonId: 'cmp' },
    global: {
      renderStubDefaultSlot: true,
      plugins: [createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })],
    },
  })
  await flushPromises()
  expect(wrapper.text()).toContain('原始决策已删除')
  expect(wrapper.text()).toContain('Evidence note')
  expect(wrapper.find('router-link-stub').exists()).toBe(false)
  wrapper
    .findAllComponents(UiButton)
    .find((b) => b.text() === '基于此版修订')!
    .vm.$emit('click')
  await flushPromises()
  expect(wrapper.findAllComponents(UiTextarea)[0]!.props('modelValue')).toBe('Saved observation')
})
