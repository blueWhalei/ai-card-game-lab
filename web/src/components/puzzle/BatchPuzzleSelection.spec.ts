/** @vitest-environment happy-dom */
import { afterEach, expect, it } from 'vitest'
import { enableAutoUnmount, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import zhCN from '@/i18n/locales/zh-CN'
import en from '@/i18n/locales/en'
import type { PuzzlePackSummary } from '@/api/puzzleApi'
import { reportHtml } from '@/utils/researchReport'
import BatchPuzzleSelection from './BatchPuzzleSelection.vue'

enableAutoUnmount(afterEach)
function pack(): PuzzlePackSummary {
  return {
    pack_id: 'batch',
    created_at: '2026-11-08',
    game_type: 'doudizhu',
    source_experiment_id: 'run',
    puzzle_count: 2,
    notes: '',
    kind: 'cardlab.puzzle_pack',
    schema_version: 1,
    extract: {
      method: 'rollout_spread',
      min_spread: 0.5,
      max_per_game: 2,
      max_total: 20,
      evaluator_params: {
        determinizations: 4,
        rollouts_per_world: 1,
        max_candidates: 8,
        max_steps: 400,
        seed: 7,
        opponent_kind_effective: 'heuristic',
      },
      source_checks: {
        p1: { decision_hash: 'a'.repeat(64), puzzle_hash: 'b'.repeat(64) },
        p2: { unverified: true },
      },
      selection: {
        order: 'spread_desc_stable',
        source_game_ids: ['g1', 'g2'],
        selected_game_ids: ['g1'],
        candidates: [
          { puzzle_id: 'p1', game_id: 'g1', spread: 0.8 },
          { puzzle_id: 'p2', game_id: 'g1', spread: 0.7 },
          { puzzle_id: 'p3', game_id: 'g2', spread: 0.1 },
        ],
      },
    },
  }
}
function render(manifest = pack(), locale = 'zh-CN') {
  return mount(BatchPuzzleSelection, {
    props: { manifest },
    global: { plugins: [createI18n({ legacy: false, locale, messages: { 'zh-CN': zhCN, en } })] },
  })
}
it.each(['zh-CN', 'en'])(
  'explains selection, dependence and new estimates in page and export (%s)',
  async (locale) => {
    const wrapper = render(pack(), locale)
    const messages = locale === 'en' ? en : zhCN
    expect(wrapper.text()).toContain(messages.puzzleBatch.estimates)
    expect(wrapper.text()).toContain(messages.puzzleBatch.limits)
    expect(wrapper.text()).toContain('1/2')
    expect(wrapper.text()).toContain(
      locale === 'en' ? 'selected positions: 2, source games: 1' : '入选 2 个局面，来自 1 局',
    )
    expect(wrapper.text()).toContain(
      locale === 'en'
        ? 'candidates with estimates: 3, meeting the threshold: 2'
        : '候选 3 个，达到阈值 2 个',
    )
    const html = reportHtml(wrapper.element as HTMLElement, 'Batch diagnostic', locale)
    expect(html).toContain(messages.puzzleBatch.limits)
    expect(html).toContain(messages.puzzleBatch.heuristic)
    const verified = pack()
    verified.extract.source_checks = {
      p1: { decision_hash: 'a'.repeat(64), puzzle_hash: 'b'.repeat(64) },
      p2: { decision_hash: 'c'.repeat(64), puzzle_hash: 'd'.repeat(64) },
    }
    await wrapper.setProps({ manifest: verified, frozen: true })
    expect(wrapper.text()).toContain(
      locale === 'en' ? 'checked at publication' : '本版发布时已完成',
    )
    expect(wrapper.text()).toContain('2/2')
  },
)
it('does not invent selection counts for legacy or malformed summaries', async () => {
  const manifest = pack()
  manifest.extract = { min_spread: 0.5 }
  const wrapper = render(manifest)
  expect(wrapper.text()).toBe('')
  const broken = pack()
  ;(broken.extract.selection as { candidates: unknown[] }).candidates = [null]
  await wrapper.setProps({ manifest: broken })
  expect(wrapper.text()).toBe('')
})
