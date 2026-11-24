/** @vitest-environment happy-dom */
import { afterEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createI18n } from 'vue-i18n'
import { createPinia } from 'pinia'
import { studyApi } from '@/api/studyApi'
import { promptDesignApi, type PromptDesignPreview } from '@/api/promptDesignApi'
import { systemApi } from '@/api/systemApi'
import { experimentApi, type Experiment } from '@/api/experimentApi'
import zhCN from '@/i18n/locales/zh-CN'
import PromptDesignView from './PromptDesignView.vue'
import * as confirm from '@/components/ui/confirm'

vi.mock('@/utils/error', () => ({ showApiError: vi.fn() }))
enableAutoUnmount(afterEach)
afterEach(() => vi.restoreAllMocks())
const preview: PromptDesignPreview = {
  baseline: {
    id: 'a',
    name: 'A',
    study_id: 's',
    target_games: 2,
    player_ids: ['p1', 'p2'],
    protocol: {
      schema_version: 2,
      frozen_at: 'now',
      dataset: {
        deal_seeds: [1, 2],
        pair_deals: false,
        source_experiment_id: null,
        collect_mode: 'benchmark',
      },
      solver: {
        players: ['p1', 'p2'].map((id) => ({
          id,
          name: id,
          notes: '',
          policy_kind: 'llm',
          model_config: { provider: 'sample', model_name: 'm' },
        })),
        prompt_version: 'v3',
        prompts: {
          doudizhu_playing: { version: 'v3', content: 'original', content_hash: 'hash-a' },
        },
      },
      engine: {
        game_type: 'doudizhu',
        engine_version: '1',
        decision_schema_version: 1,
        rules_ref: null,
        phases: ['playing'],
        roles: [],
        prompt_keys: { playing: 'doudizhu_playing' },
        supports_deal_seed: true,
        benchmark_seed_count: 2,
      },
      scorer: { eval_metric_ids: [] },
    },
  },
  affected_player_ids: ['p1', 'p2'],
  fingerprint: 'fingerprint',
  issues: [],
  options: [
    { template_key: 'doudizhu_playing', version: 'B', content: 'revised', content_hash: 'hash-b' },
  ],
}
async function setup(query = '') {
  vi.spyOn(studyApi, 'get').mockResolvedValue({
    code: 0,
    message: '',
    data: {
      id: 's',
      title: 'Research',
      question: 'Question?',
      created_at: '',
      updated_at: '',
      runs: [preview.baseline as Experiment],
      comparisons: [],
    },
  })
  vi.spyOn(systemApi, 'preflight').mockResolvedValue({
    code: 0,
    message: '',
    data: {
      ok: false,
      can_collect: false,
      can_train: false,
      providers: [],
      checks: [],
      warnings: [],
    },
  })
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/research/:id/prompt-ab', component: PromptDesignView },
      { path: '/experiments/:id', component: { template: '<div />' } },
      {
        path: '/research-reports/:id',
        name: 'research-report',
        component: { template: '<div />' },
      },
      { path: '/:pathMatch(.*)*', component: { template: '<div />' } },
    ],
  })
  await router.push(`/research/s/prompt-ab${query}`)
  const wrapper = mount(
    { template: '<router-view />' },
    {
      global: {
        plugins: [
          createPinia(),
          router,
          createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } }),
        ],
      },
    },
  )
  await flushPromises()
  return { wrapper, router }
}
type Wrapper = Awaited<ReturnType<typeof setup>>['wrapper']
async function button(wrapper: Wrapper, text: string) {
  await wrapper
    .findAll('button')
    .find((b) => b.text() === text)!
    .trigger('click')
  await flushPromises()
}
it('reviews a single change and creates only on explicit submit, without collecting', async () => {
  vi.spyOn(promptDesignApi, 'preview').mockResolvedValue({ code: 0, message: '', data: preview })
  const create = vi
    .spyOn(promptDesignApi, 'create')
    .mockResolvedValue({ code: 0, message: '', data: { id: 'b' } as Experiment })
  const collect = vi.spyOn(experimentApi, 'collect')
  const { wrapper, router } = await setup()
  await wrapper.get('#baseline').setValue('a')
  await flushPromises()
  await button(wrapper, '下一步')
  expect(wrapper.get('#hypothesis').element).toHaveProperty('value', 'Question?')
  expect(
    wrapper
      .findAll('button')
      .find((b) => b.text() === '下一步')!
      .attributes('disabled'),
  ).toBeDefined()
  await wrapper.get('#version').setValue('B')
  const metric = wrapper.get<HTMLSelectElement>('#primary-metric')
  metric.element.selectedIndex = 1
  await metric.trigger('change')
  await button(wrapper, '下一步')
  expect(wrapper.text()).toContain('通过不代表远端连接')
  expect(wrapper.text()).toContain('每组 2 局')
  expect(wrapper.text()).toContain('#1 p1 所在阵营胜率')
  expect(wrapper.text()).toContain('#1 p1, #2 p2')
  expect(create).not.toHaveBeenCalled()
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(create).toHaveBeenCalledWith('a', {
    study_id: 's',
    primary_metric: { kind: 'seat_team_win_rate', player_id: 'p1' },
    baseline_fingerprint: 'fingerprint',
    template_key: 'doudizhu_playing',
    version: 'B',
    content_hash: 'hash-b',
    name: 'A · B',
    hypothesis: 'Question?',
  })
  expect(collect).not.toHaveBeenCalled()
  expect(router.currentRoute.value.path).toBe('/experiments/b')
})
it('explains ineligible baselines and prevents advancing', async () => {
  vi.spyOn(promptDesignApi, 'preview').mockResolvedValue({
    code: 0,
    message: '',
    data: { ...preview, issues: ['model_player_required'] },
  })
  const { wrapper } = await setup()
  await wrapper.get('#baseline').setValue('a')
  await flushPromises()
  expect(wrapper.text()).toContain('离线策略不使用提示词')
  expect(
    wrapper
      .findAll('button')
      .find((b) => b.text() === '下一步')!
      .attributes('disabled'),
  ).toBeDefined()
})
it('protects edits when navigating away or refreshing', async () => {
  vi.spyOn(promptDesignApi, 'preview').mockResolvedValue({ code: 0, message: '', data: preview })
  const leave = vi.spyOn(confirm, 'confirmDialog').mockResolvedValue(false)
  const { wrapper, router } = await setup()
  await wrapper.get('#baseline').setValue('a')
  await flushPromises()
  await button(wrapper, '下一步')
  await wrapper.get('#hypothesis').setValue('Keep this')
  await router.push('/research/s')
  expect(leave).toHaveBeenCalledOnce()
  expect(router.currentRoute.value.path).toBe('/research/s/prompt-ab')
  expect(wrapper.get('#hypothesis').element).toHaveProperty('value', 'Keep this')
  const event = new Event('beforeunload', { cancelable: true })
  window.dispatchEvent(event)
  expect(event.defaultPrevented).toBe(true)
})
it('keeps hypothesis and name after a conflict but requires a fresh review', async () => {
  vi.spyOn(promptDesignApi, 'preview').mockResolvedValue({ code: 0, message: '', data: preview })
  vi.spyOn(promptDesignApi, 'create').mockRejectedValue(new Error('conflict'))
  const { wrapper } = await setup()
  await wrapper.get('#baseline').setValue('a')
  await flushPromises()
  await button(wrapper, '下一步')
  await wrapper.get('#hypothesis').setValue('My careful hypothesis')
  await wrapper.get('#variant-name').setValue('My variant')
  await wrapper.get('#version').setValue('B')
  const metric = wrapper.get<HTMLSelectElement>('#primary-metric')
  metric.element.selectedIndex = 1
  await metric.trigger('change')
  await button(wrapper, '下一步')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.find('[role="alert"]').exists()).toBe(true)
  expect(
    wrapper
      .findAll('button')
      .find((b) => b.text() === '下一步')!
      .attributes('disabled'),
  ).toBeDefined()
  await button(wrapper, '重试')
  await button(wrapper, '下一步')
  expect(wrapper.get('#hypothesis').element).toHaveProperty('value', 'My careful hypothesis')
  expect(wrapper.get('#variant-name').element).toHaveProperty('value', 'My variant')
  expect(wrapper.get('#version').element).toHaveProperty('value', '')
})

const conclusion = (id: string) => ({
  id,
  comparison_id: 'cmp',
  revision: 1,
  created_at: '2026-11-07',
  observations: `Observed ${id}`,
  interpretation: 'Possible reason',
  limitations: 'Selected data',
})
it('restores the report baseline, requires a new hypothesis, and submits the exact source', async () => {
  vi.spyOn(promptDesignApi, 'preview').mockResolvedValue({
    code: 0,
    message: '',
    data: { ...preview, source_conclusion: conclusion('r1') },
  })
  const create = vi
    .spyOn(promptDesignApi, 'create')
    .mockResolvedValue({ code: 0, message: '', data: { id: 'b' } as Experiment })
  const { wrapper } = await setup('?baseline=a&source_revision=r1')
  expect(promptDesignApi.preview).toHaveBeenCalledWith('a', 'r1')
  expect(wrapper.text()).toContain('Observed r1')
  expect(wrapper.get('#baseline').element).toHaveProperty('value', 'a')
  expect(wrapper.get('#baseline').attributes('disabled')).toBeDefined()
  await button(wrapper, '下一步')
  expect(wrapper.get('#hypothesis').element).toHaveProperty('value', '')
  await wrapper.get('#hypothesis').setValue('New hypothesis')
  await wrapper.get('#version').setValue('B')
  const metric = wrapper.get<HTMLSelectElement>('#primary-metric')
  metric.element.selectedIndex = 1
  await metric.trigger('change')
  await button(wrapper, '下一步')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(create).toHaveBeenCalledWith(
    'a',
    expect.objectContaining({ source_revision_id: 'r1', hypothesis: 'New hypothesis' }),
  )
})
it('ignores a late response after changing the source version in the same research', async () => {
  let finish!: (value: Awaited<ReturnType<typeof promptDesignApi.preview>>) => void
  vi.spyOn(promptDesignApi, 'preview').mockImplementation((_id, source) =>
    source === 'r1'
      ? new Promise((resolve) => {
          finish = resolve
        })
      : Promise.resolve({
          code: 0,
          message: '',
          data: { ...preview, source_conclusion: conclusion('r2') },
        }),
  )
  const { wrapper, router } = await setup('?baseline=a&source_revision=r1')
  await router.push('/research/s/prompt-ab?baseline=a&source_revision=r2')
  await flushPromises()
  finish({ code: 0, message: '', data: { ...preview, source_conclusion: conclusion('r1') } })
  await flushPromises()
  expect(wrapper.text()).toContain('Observed r2')
  expect(wrapper.text()).not.toContain('Observed r1')
  expect(wrapper.find('[role="status"]').exists()).toBe(false)
})
it.each([
  '?source_revision=r1',
  '?baseline=a&source_revision',
  '?baseline=a&source_revision=',
  '?baseline=a&source_revision=r1&source_revision=r2',
])('blocks an incomplete or ambiguous source URL: %s', async (query) => {
  const previewCall = vi.spyOn(promptDesignApi, 'preview')
  const { wrapper } = await setup(query)
  expect(wrapper.find('[role="alert"]').exists()).toBe(true)
  expect(wrapper.find('form').exists()).toBe(false)
  await button(wrapper, '重试')
  expect(previewCall).not.toHaveBeenCalled()
})
