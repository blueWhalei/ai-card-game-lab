/**
 * @vitest-environment happy-dom
 */
import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import type { Experiment } from '@/api/experimentApi'
import zhCN from '@/i18n/locales/zh-CN'
import ExperimentStage from './ExperimentStage.vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
}))

function makeExperiment(overrides: Partial<Experiment> = {}): Experiment {
  return {
    id: 'exp-1',
    name: 'run',
    notes: '',
    hypothesis: '',
    conclusion: '',
    tags: [],
    game_type: 'doudizhu',
    player_ids: ['a', 'b', 'c'],
    target_games: 10,
    created_at: '',
    updated_at: '',
    summary: {
      status: 'ready_review',
      target_games: 10,
      total_games: 10,
      active_games: 0,
      finished_games: 10,
      games_with_winner: 10,
      train_usable_decisions: 0,
      not_usable_decisions: 0,
      avg_rounds: 12,
      wins_by_config: {},
      player_stats: [],
      latest_game_id: 'g1',
    },
    ...overrides,
  } as Experiment
}

function mountStage(experiment: Experiment, blockedMessage = '') {
  const i18n = createI18n({
    legacy: false,
    locale: 'zh-CN',
    missingWarn: false,
    fallbackWarn: false,
    messages: { 'zh-CN': zhCN },
  })
  return mount(ExperimentStage, {
    props: {
      experiment,
      blockedMessage,
      remainingCollect: 5,
    },
    global: {
      plugins: [i18n],
      stubs: {
        StageVerdict: true,
        UiInputNumber: true,
        UiButton: { template: '<button v-bind="$attrs"><slot /></button>' },
      },
    },
  })
}

describe('ExperimentStage blocking CTA', () => {
  it('replaces empty-phase collect with settings when blocked', async () => {
    const wrapper = mountStage(
      makeExperiment({
        summary: {
          status: 'pending_collect',
          target_games: 10,
          total_games: 0,
          active_games: 0,
          finished_games: 0,
          games_with_winner: 0,
          train_usable_decisions: 0,
          avg_rounds: 0,
          wins_by_config: {},
          player_stats: [],
          latest_game_id: null,
        } as never,
      }),
      '缺少 API 密钥',
    )
    expect(wrapper.text()).toContain('还差一步才能开始实验')
    expect(wrapper.text()).toContain('缺少 API 密钥')
    expect(wrapper.text()).toContain('去设置')
    expect(wrapper.text()).not.toContain('确认开始')
  })

  it('allows reviewing zero-usable results even when collection is blocked', async () => {
    const wrapper = mountStage(makeExperiment(), '供应商未配置')
    const review = wrapper.findAll('button').find((b) => b.text() === '审查全部决策')!
    expect(review.attributes('disabled')).toBeUndefined()
    await review.trigger('click')
    expect(wrapper.emitted('action')).toEqual([['review-decisions']])
    expect(wrapper.text()).not.toContain('开始训练')
  })
})
