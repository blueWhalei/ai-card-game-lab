/** @vitest-environment happy-dom */
import { afterEach, expect, it } from 'vitest'
import { mount, enableAutoUnmount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter } from 'vue-router'
import type { ResearchReport } from '@/api/researchApi'
import type { ExperimentProtocolRaw } from '@/api/experimentApi'
import zhCN from '@/i18n/locales/zh-CN'
import en from '@/i18n/locales/en'
import { evidenceOrigin, reportDecisionLink, reportHtml } from '@/utils/researchReport'
import ResearchReportDocument from './ResearchReportDocument.vue'

enableAutoUnmount(afterEach)
function run(id: string, name: string) {
  return {
    id,
    name,
    hypothesis: id === 'a' ? 'Frozen A' : '',
    game_type: 'doudizhu',
    player_ids: ['p'],
    game_ids: [`g-${id}`, `g-${id}-2`],
    notes: '',
    finished_games: 2,
    games_with_winner: 2,
    avg_rounds: 4,
    avg_response_time_ms: 0,
    total_tokens: 0,
    avg_tokens_per_round: 0,
    train_usable_rate: 1,
    train_usable_n: 2,
    decision_count: 2,
    parser_success_rate: 1,
    parser_n: 2,
    player_stats: [],
    paired_seat_wins: null,
  }
}
function fixture(): ResearchReport {
  return {
    kind: 'cardlab.research_report',
    exported_at: '2026-11-06T00:00:00Z',
    scope: 'frozen',
    record: {
      id: 'revision-1',
      comparison_id: 'comparison-1',
      revision: 1,
      created_at: '2026-11-05',
      observations: '<img src=x onerror="alert(1)">',
      interpretation: 'Possibility, not proof',
      limitations: 'Selected examples',
      evidence: [
        {
          note: 'Example only',
          decision: {
            id: 'd1',
            game_id: 'g-a',
            player_id: 'p',
            round_number: 0,
            action_id: 'PASS||',
            ev_loss: null,
            outcome: 'win',
            annotation: null,
            hand_cards: ['S3'],
            chosen_action: { action_type: 'PASS', cards: [] },
            evaluator_params: {},
          },
        },
        {
          note: 'Missing source',
          decision: {
            id: 'd2',
            game_id: 'g-b',
            player_id: 'p',
            round_number: 0,
            action_id: 'PLAY|S3|',
            ev_loss: 0,
            annotation: null,
          },
        },
      ],
    },
    evidence_status: { d1: 'changed', d2: 'missing' },
    comparison: {
      id: 'comparison-1',
      title: 'Frozen question',
      created_at: '2026-11-05',
      result: {
        metric_version: 'paired-cohort-v5',
        computed_at: '2026-11-04',
        experiments: [run('a', 'Baseline'), run('b', 'Variant')],
        coverage: {
          planned_shared: 3,
          effective_n: 2,
          effective_seeds: [42, 44],
          excluded_n: 1,
          deal_purpose: 'development',
          members: [
            { seed: 42, game_ids: { a: 'g-a', b: 'g-b' } },
            { seed: 44, game_ids: { a: 'g-a-2', b: 'g-b-2' } },
          ],
          experiments: [],
          excluded_pairs: [{ seed: 43, reasons: { b: 'unfinished' } }],
        },
        paired_summary: {
          primary_metric: { kind: 'landlord_win_rate' },
          affected_player_ids: [],
          shared_seeds: 2,
          source_id: 'a',
          control_id: 'b',
          win_rate_diff: -0.5,
          paired_ci: [-1, 0.5],
          paired_p: 1,
          ci_method: 'clopper_pearson_bonferroni',
          low_power: true,
          outcome_counts: { both_won: 1, a_only_won: 1, b_only_won: 0, both_lost: 0 },
        },
      },
    },
  }
}
async function render(data = fixture(), locale = 'zh-CN') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/research-reports/:id',
        name: 'research-report',
        component: { template: '<div />' },
      },
      { path: '/:pathMatch(.*)*', component: { template: '<div />' } },
    ],
  })
  await router.push('/')
  return mount(ResearchReportDocument, {
    props: { report: data },
    global: {
      plugins: [router, createI18n({ legacy: false, locale, messages: { 'zh-CN': zhCN, en } })],
    },
  })
}

it.each(['zh-CN', 'en'])(
  'renders frozen statistics, nulls, source states and evidence navigation in %s',
  async (locale) => {
    const report = fixture()
    const wrapper = await render(report, locale)
    expect(wrapper.text()).toContain('B (Variant) − A (Baseline)')
    expect(wrapper.text()).toContain('-50.0')
    expect(wrapper.text()).toContain('[-100.0, 50.0]')
    expect(wrapper.find('#report-evidence-1').text()).toContain('♠3')
    expect(wrapper.find('#report-evidence-1').text()).toContain(locale === 'en' ? 'Win' : '胜利')
    expect(wrapper.text()).not.toMatch(/report\.[a-zA-Z]|filter\.win/)
    const links = wrapper.findAll('a').map((a) => a.attributes('href'))
    expect(links).toContain('#report-evidence-2')
    expect(
      links.some(
        (href) =>
          href?.includes('decision_id=d1') &&
          href.includes('report_id=revision-1') &&
          href.includes('compare_seed=42'),
      ),
    ).toBe(true)
    expect(links.some((href) => href?.includes('decision_id=d2'))).toBe(false)
    expect(wrapper.find('#report-evidence-1').text()).toContain(
      locale === 'en' ? 'Not recorded' : '未记录',
    )
    expect(wrapper.find('#report-evidence-2').text()).toContain(
      locale === 'en' ? 'deleted' : '已删除',
    )
    expect(wrapper.findAll('img,script')).toHaveLength(0)
    const html = reportHtml(wrapper.element as HTMLElement, '<script>title</script>', locale)
    const document = new DOMParser().parseFromString(html, 'text/html')
    expect(document.querySelectorAll('script,img,[data-report-local]')).toHaveLength(0)
    expect(document.querySelectorAll('a[href^="/pipeline"]')).toHaveLength(0)
    expect(document.querySelector('a[href="#report-evidence-2"]')).not.toBeNull()
    expect([...document.querySelectorAll('details')].every((d) => d.open)).toBe(true)
    expect(document.body.textContent).toContain(report.record.observations)
    expect(document.querySelector('meta[http-equiv="Content-Security-Policy"]')).not.toBeNull()
  },
)

it('does not turn unavailable or unsupported estimates into zero or current values', async () => {
  const report = fixture()
  report.comparison.result.paired_summary!.shared_seeds = 0
  report.comparison.result.paired_summary!.win_rate_diff = null
  const wrapper = await render(report)
  expect(wrapper.text()).toContain('没有可报告的双组有效配对估计')
  expect(wrapper.text()).not.toContain('-50.0')
  report.comparison.result.metric_version = 'unknown'
  await wrapper.setProps({ report: structuredClone(report) })
  expect(wrapper.text()).toContain('不按当前统计定义解释数值')
})

it('does not invent provenance when frozen membership is missing or ambiguous', () => {
  const report = fixture()
  const decision = report.record.evidence[0]!.decision
  report.comparison.result.coverage!.members = []
  expect(evidenceOrigin(report, decision)).toBeNull()
  expect(reportDecisionLink(report, decision).query).not.toHaveProperty('compare_seed')
  report.comparison.result.coverage!.members = [{ seed: 1, game_ids: { a: 'g-a', b: 'g-a' } }]
  expect(evidenceOrigin(report, decision)).toBeNull()
})

it('retains a follow-up source in offline HTML while keeping its route local to the app', async () => {
  const report = fixture()
  report.comparison.result.experiments[1]!.protocol = {
    solver: { players: [] },
    design: { source_revision_id: 'earlier-revision' },
  } as unknown as ExperimentProtocolRaw
  const wrapper = await render(report)
  expect(wrapper.find('a[href="/research-reports/earlier-revision"]').exists()).toBe(true)
  const document = new DOMParser().parseFromString(
    reportHtml(wrapper.element as HTMLElement, 'Follow-up', 'en'),
    'text/html',
  )
  expect(document.querySelector('#report-conditions')?.textContent).toContain('earlier-revision')
  expect(document.querySelector('a[href="/research-reports/earlier-revision"]')).toBeNull()
})

it.each(['zh-CN', 'en'])(
  'keeps published test evidence readable after its file is deleted (%s)',
  async (locale) => {
    const report = fixture()
    const item = {
      note: 'Exploratory <script>note</script>',
      sources: [],
      result: {
        report: {
          pack_id: 'pack',
          run_id: 'run_12345678',
          metric_version: 'puzzle-scoring-v2',
          baseline_kind: 'first' as const,
          seed: 7,
          created_at: '2026-11-08',
          summary: {
            n: 1,
            evaluated_n: 0,
            unevaluated_n: 1,
            accuracy: null,
            mean_ev_loss: null,
            truncated_n: 1,
          },
          puzzles: [
            {
              puzzle_id: 'p',
              chosen_action_id: 'a',
              best_action_id: 'b',
              hit: null,
              ev_loss: null,
              truncated: true,
            },
          ],
        },
        source_status: 'matched' as const,
        read_at: '2026-11-08',
        report_hash: 'a'.repeat(64),
      },
    }
    report.record.puzzle_evidence = [item]
    report.puzzle_evidence_status = [
      { record_status: 'available', source_status: 'matched', decisions: {} },
    ]
    const wrapper = await render(report, locale)
    const link = wrapper.get('#report-test-1 a').attributes('href')
    const query = new URL(link!, 'http://localhost').searchParams
    expect(query.get('puzzle_evidence')).toBe('pack/run_12345678')
    expect(query.get('report_id')).toBe('revision-1')
    report.puzzle_evidence_status[0]!.record_status = 'missing'
    report.puzzle_evidence_status[0]!.source_status = null
    await wrapper.setProps({ report: structuredClone(report) })
    const messages = locale === 'en' ? en : zhCN
    expect(wrapper.get('#report-test-1').text()).toContain(messages.puzzleCitation.status.missing)
    expect(wrapper.get('#report-test-1').text()).toContain('0/1')
    expect(wrapper.get('#report-test-1').text()).toContain(messages.puzzleCitation.testLimits)
    expect(wrapper.get('#report-test-1').text()).not.toContain(messages.puzzleHistory.scope)
    expect(wrapper.get('#report-puzzle-evidence').text()).toContain(
      messages.puzzleCitation.reportScope,
    )
    expect(wrapper.get('#report-test-1').findAll('a')).toHaveLength(0)
    const html = reportHtml(wrapper.element as HTMLElement, 'Report', locale)
    expect(html).toContain('Exploratory &lt;script&gt;note&lt;/script&gt;')
    expect(html).toContain('href="#report-test-1"')
    expect(html).not.toContain('/pipeline/puzzles')
  },
)
