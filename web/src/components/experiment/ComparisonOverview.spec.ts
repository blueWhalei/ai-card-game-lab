/** @vitest-environment happy-dom */
import { expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import type { ExperimentCompareResult } from '@/api/experimentApi'
import zhCN from '@/i18n/locales/zh-CN'
import ComparisonOverview from './ComparisonOverview.vue'

function render(overrides: Partial<ExperimentCompareResult> = {}) {
  const result = {
    experiments: [
      { id: 'a', name: '基线 A' },
      { id: 'b', name: '变体 B' },
    ],
    coverage: {
      planned_shared: 24,
      effective_n: 20,
      excluded_n: 4,
      excluded_pairs: [],
      deal_purpose: 'development',
    },
    protocol_review: { controlled: true },
    paired_summary: {
      primary_metric: { kind: 'landlord_win_rate' },
      affected_player_ids: [],
      ci_method: 'clopper_pearson_bonferroni',
      outcome_counts: { both_won: 3, a_only_won: 4, b_only_won: 6, both_lost: 7 },
      source_id: 'a',
      control_id: 'b',
      shared_seeds: 20,
      low_power: false,
      win_rate_diff: 0.1,
      paired_ci: [-0.18, 0.38],
      paired_p: 0.5,
    },
    ...overrides,
  } as ExperimentCompareResult
  return mount(ComparisonOverview, {
    props: { result },
    global: {
      plugins: [createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })],
    },
  })
}

it('keeps the signed difference, sample size and crossing-zero warning together', () => {
  const wrapper = render()
  expect(wrapper.text()).toContain('变体 B − 基线 A')
  expect(wrapper.text()).toContain('+10pp')
  expect(wrapper.text()).toContain('共同计划 24 · 有效 20 · 未纳入 4')
  expect(wrapper.findAll('dd').map((cell) => cell.text())).toEqual(['3', '4', '6', '7'])
  expect(wrapper.text()).toContain('区间跨零')
  expect(wrapper.text()).toContain('−18pp')
})

it('does not turn an absent paired result into a zero effect', () => {
  const wrapper = render({ paired_summary: undefined })
  expect(wrapper.text()).toContain('还没有共同有效样本')
  expect(wrapper.text()).not.toContain('0pp')
})

it('keeps failed protocol checks visible in the main result', () => {
  const wrapper = render({ protocol_review: { controlled: false } as never })
  expect(wrapper.text()).toContain('当前仅作描述性比较')
})

it('does not rank a multiple-run comparison by a pair summary', () => {
  const wrapper = render({ experiments: [{ id: 'a' }, { id: 'b' }, { id: 'c' }] as never })
  expect(wrapper.text()).toContain('多组探索性比较')
  expect(wrapper.text()).not.toContain('+10pp')
})

it('labels the observed seat and the shared change alongside the estimate', () => {
  const wrapper = render({
    coverage: { planned_shared: 5, effective_n: 5, excluded_n: 0, deal_purpose: 'holdout' } as never,
    paired_summary: {
      primary_metric: { kind: 'seat_team_win_rate', player_id: 'North' },
      affected_player_ids: ['North', 'South'],
      ci_method: 'clopper_pearson_bonferroni',
      outcome_counts: { both_won: 1, a_only_won: 2, b_only_won: 1, both_lost: 1 },
      source_id: 'a',
      control_id: 'b',
      shared_seeds: 5,
      low_power: true,
      win_rate_diff: -0.2,
    },
  })
  expect(wrapper.text()).toContain('North 所在阵营胜率')
  expect(wrapper.text()).toContain('North, South')
  expect(wrapper.text()).toContain('多个席位共同更换提示词')
  expect(wrapper.text()).toContain('−20pp')
  expect(wrapper.text()).toContain('独立验证用牌 · 共同计划 5 · 有效 5 · 未纳入 0')
  expect(wrapper.text()).not.toContain('地主胜率')
})
