/** @vitest-environment happy-dom */
import { afterEach, expect, it } from 'vitest'
import { enableAutoUnmount, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter, RouterLink } from 'vue-router'
import zhCN from '@/i18n/locales/zh-CN'
import en from '@/i18n/locales/en'
import type { ResearchReport, ResearchTracePreview } from '@/api/researchApi'
import { reportComparisonLink, reportHtml } from '@/utils/researchReport'
import ResearchTraceEvidence from './ResearchTraceEvidence.vue'

enableAutoUnmount(afterEach)
it.each(['zh-CN', 'en'])(
  'keeps frozen text in %s exports while removing current-source routes and active markup',
  async (locale) => {
    const preview: ResearchTracePreview = {
      comparison_id: 'cmp',
      cutoff: '2026-11-09T00:00:00Z',
      read_at: '2026-11-09T00:00:00Z',
      source_hash: 'a'.repeat(64),
      source: {
        experiment_id: 'run',
        game_id: 'g',
        game_type: 'doudizhu',
        player_ids: ['p'],
        deal_seed: 42,
        created_at: '2026-11-08T00:00:00Z',
        status: 'finished',
      },
      trace: {
        id: 'tr',
        game_id: 'g',
        player_id: 'p',
        round_number: 1,
        model: 'fixture',
        prompt_version: 'v1',
        created_at: '2026-11-08T00:00:00Z',
        input_snapshot: { message: '<script>alert(1)</script>' },
        output_data: { text: 'Frozen output' },
        metrics: { response_time_ms: 0 },
        spans: [],
      },
    }
    const report = {
      record: {
        id: 'rev',
        comparison_id: 'cmp',
        trace_evidence: [{ ...preview, note: 'Diagnostic interpretation' }],
      },
      trace_evidence_status: { tr: 'changed' },
    } as unknown as ResearchReport
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/pipeline/traces', component: { template: '<div />' } },
      ],
    })
    await router.push('/')
    const wrapper = mount(ResearchTraceEvidence, {
      props: { report },
      global: {
        plugins: [router, createI18n({ legacy: false, locale, messages: { 'zh-CN': zhCN, en } })],
      },
    })
    expect(wrapper.findComponent(RouterLink).props('to')).toMatchObject({
      query: { trace_id: 'tr', game_id: 'g', report_id: 'rev', trace_evidence: 'tr' },
    })
    expect(reportComparisonLink(report, undefined, 'tr').query.trace_evidence).toBe('tr')
    expect(reportComparisonLink(report, undefined, 'wrong').query.trace_evidence).toBeUndefined()
    const html = reportHtml(wrapper.element as HTMLElement, 'Evidence', locale)
    expect(html).toContain('Frozen output')
    expect(html).toContain('Diagnostic interpretation')
    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;')
    expect(html).not.toContain('/pipeline/traces')
    expect(html).not.toContain('<script>')
    expect(html).toContain('<details open="">')
    for (const status of ['missing', 'invalid', 'identity_mismatch'] as const) {
      await wrapper.setProps({ report: { ...report, trace_evidence_status: { tr: status } } })
      expect(wrapper.findComponent(RouterLink).exists()).toBe(false)
      expect(wrapper.text()).toContain('Frozen output')
    }
  },
)
