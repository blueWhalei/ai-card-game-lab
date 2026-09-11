/** @vitest-environment happy-dom */
import { afterEach, expect, it, vi } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createI18n } from 'vue-i18n'
import { experimentApi } from '@/api/experimentApi'
import { experimentConfigApi } from '@/api/experimentConfigApi'
import { systemApi } from '@/api/systemApi'
import UiButton from '@/components/ui/Button.vue'
import UiInput from '@/components/ui/Input.vue'
import ComparisonAudit from '@/components/experiment/ComparisonAudit.vue'
import zhCN from '@/i18n/locales/zh-CN'
import ExperimentCompareView from './ExperimentCompareView.vue'

const result = {
  experiments: ['a', 'b'].map((id) => ({
    id,
    name: id,
    game_type: 'doudizhu',
    player_ids: [],
    player_stats: [],
    finished_games: 0,
    decisive_games: 0,
    train_usable_rate: 0,
    parser_success_rate: 0,
  })),
  protocol_review: {
    baseline_id: 'a',
    controlled: false,
    allowed_changes: [],
    differences: [],
    unknown: [],
    reasons: ['unknown_protocol'],
  },
  coverage: { effective_n: 0, planned_shared: 0, effective_seeds: [], experiments: [] },
}
afterEach(() => vi.restoreAllMocks())

it('requires recomparison after a declaration and restores a saved snapshot without recomputing it', async () => {
  vi.spyOn(experimentApi, 'list').mockResolvedValue({
    data: result.experiments.map((r) => ({
      ...r,
      summary: { finished_games: 0, target_games: 5 },
    })),
  } as never)
  vi.spyOn(experimentConfigApi, 'list').mockResolvedValue({ data: [] } as never)
  vi.spyOn(systemApi, 'listEngines').mockResolvedValue({ data: [] } as never)
  vi.spyOn(experimentApi, 'listComparisons').mockResolvedValue({ data: [] } as never)
  const compare = vi
    .spyOn(experimentApi, 'compare')
    .mockImplementation(
      async (_ids, changes) =>
        ({
          data: {
            ...result,
            protocol_review: { ...result.protocol_review, allowed_changes: changes ?? [] },
          },
        }) as never,
    )
  const saved = { id: 'cmp-1', title: 'saved', created_at: '2026-09-11', result }
  const save = vi.spyOn(experimentApi, 'saveComparison').mockResolvedValue({ data: saved } as never)
  vi.spyOn(experimentApi, 'getComparison').mockResolvedValue({ data: saved } as never)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/experiments/compare', component: { template: '<div />' } }],
  })
  await router.push('/experiments/compare?ids=a,b')
  const options = {
    global: {
      renderStubDefaultSlot: true,
      plugins: [
        router,
        createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } }),
      ],
    },
  }
  let wrapper = shallowMount(ExperimentCompareView, options)
  await flushPromises()
  wrapper.findComponent(UiInput).vm.$emit('update:modelValue', 'saved')
  wrapper
    .findComponent(ComparisonAudit)
    .vm.$emit('update:allowed', ['solver.players.0.model_config.temperature'])
  await flushPromises()
  const saveButton = () =>
    wrapper.findAllComponents(UiButton).find((b) => b.text() === '重新计算并保存快照')!
  expect(saveButton().props('disabled')).toBe(true)
  expect(wrapper.text()).toContain('选择或变量声明已改变')
  await wrapper
    .findAllComponents(UiButton)
    .find((b) => b.text() === '对比所选')!
    .trigger('click')
  await flushPromises()
  expect(compare).toHaveBeenLastCalledWith(
    ['a', 'b'],
    ['solver.players.0.model_config.temperature'],
  )
  expect(saveButton().props('disabled')).toBe(false)
  await saveButton().trigger('click')
  await flushPromises()
  expect(save).toHaveBeenCalledTimes(1)
  expect(router.currentRoute.value.query.snapshot).toBe('cmp-1')
  wrapper.unmount()
  await router.push('/experiments/compare?snapshot=cmp-1')
  compare.mockClear()
  wrapper = shallowMount(ExperimentCompareView, options)
  await flushPromises()
  expect(compare).not.toHaveBeenCalled()
  expect(wrapper.text()).toContain('已保存快照')
  wrapper.unmount()
})
