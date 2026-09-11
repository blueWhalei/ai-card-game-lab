/** @vitest-environment happy-dom */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createI18n } from 'vue-i18n'
import { experimentApi, type Experiment } from '@/api/experimentApi'
import { experimentConfigApi, type ExperimentConfig } from '@/api/experimentConfigApi'
import { systemApi } from '@/api/systemApi'
import { trainingApi } from '@/api/trainingApi'
import zhCN from '@/i18n/locales/zh-CN'
import { useExperimentDetail } from './useExperimentDetail'

const experiment: Experiment = {
  id: 'source',
  name: 'Baseline',
  notes: '',
  tags: [],
  created_at: '',
  updated_at: '',
  player_ids: ['a', 'b', 'c'],
  target_games: 5,
  game_type: 'doudizhu',
  hypothesis: '',
  conclusion: '',
  games: [],
  summary: {
    status: 'pending_collect',
    total_games: 0,
    finished_games: 0,
    target_games: 5,
    active_games: 0,
    games_with_winner: 0,
    train_usable_decisions: 0,
    avg_rounds: 0,
    wins_by_config: {},
    player_stats: [],
    latest_game_id: null,
  },
}

beforeEach(() => {
  vi.spyOn(experimentApi, 'get').mockResolvedValue({ data: experiment } as never)
  vi.spyOn(experimentConfigApi, 'list').mockResolvedValue({
    data: ['a', 'b', 'c', 'lora_other'].map(
      (id) => ({ id, name: id, model_config: {} }) as ExperimentConfig,
    ),
  } as never)
  vi.spyOn(systemApi, 'preflight').mockResolvedValue({ data: { checks: [] } } as never)
  vi.spyOn(systemApi, 'getConfig').mockRejectedValue(new Error('training unavailable'))
  vi.spyOn(trainingApi, 'listModels').mockRejectedValue(new Error('training unavailable'))
  vi.spyOn(experimentApi, 'collect').mockResolvedValue({ data: { count: 1 } } as never)
  vi.spyOn(experimentApi, 'create').mockResolvedValue({ data: { id: 'control' } } as never)
})
afterEach(() => vi.restoreAllMocks())

async function setup(query = '') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/experiments/:id', component: { template: '<div />' } },
      { path: '/pipeline/decisions', component: { template: '<div />' } },
    ],
  })
  await router.push(`/experiments/source${query}`)
  let state!: ReturnType<typeof useExperimentDetail>
  const wrapper = mount(
    defineComponent({
      setup() {
        state = useExperimentDetail()
        return () => null
      },
    }),
    {
      global: {
        plugins: [
          router,
          createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } }),
        ],
      },
    },
  )
  await flushPromises()
  return { state, router, wrapper }
}

describe('research workflow without training', () => {
  it('consumes collect links, opens confirmation, and only runs after submission', async () => {
    const { state, router, wrapper } = await setup('?collect=1&from=source')
    expect(state.collectOpen.value).toBe(true)
    expect(router.currentRoute.value.query).toEqual({ from: 'source' })
    expect(experimentApi.collect).not.toHaveBeenCalled()
    state.collectOpen.value = false
    await state.load()
    expect(state.collectOpen.value).toBe(false)
    await state.submitCollect()
    expect(experimentApi.collect).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('preserves source seats and offers all configs despite a registered LoRA player', async () => {
    const { state, router, wrapper } = await setup('?open_control=1')
    expect(state.controlOpen.value).toBe(true)
    expect(state.controlPlayerIds.value).toEqual(['a', 'b', 'c'])
    expect(state.challengerOptions.value).toHaveLength(4)
    expect(state.controlOpenCollectAfter.value).toBe(false)
    expect(router.currentRoute.value.query).toEqual({})
    expect(experimentApi.create).not.toHaveBeenCalled()
    expect(experimentApi.collect).not.toHaveBeenCalled()
    await state.submitControl()
    expect(experimentApi.create).toHaveBeenCalledWith(
      expect.objectContaining({
        player_ids: ['a', 'b', 'c'],
        source_experiment_id: 'source',
        pair_deals: true,
      }),
    )
    expect(experimentApi.collect).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('opens decision review with excluded records included', async () => {
    const { state, router, wrapper } = await setup()
    state.onStageAction('review-decisions')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/pipeline/decisions')
    expect(router.currentRoute.value.query).toEqual({
      experiment_id: 'source',
      train_usable: 'all',
    })
    wrapper.unmount()
  })
})
