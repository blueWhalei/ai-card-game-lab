/**
 * @vitest-environment happy-dom
 */
import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { ref } from 'vue'
import type { ExperimentDelta } from '@/api/experimentApi'
import zhCN from '@/i18n/locales/zh-CN'
import StageVerdict from './StageVerdict.vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('@/composables/useLocale', () => ({
  useLocale: () => ({ locale: ref('zh-CN') }),
}))

vi.mock('@/api/experimentApi', async () => {
  const actual = await vi.importActual<typeof import('@/api/experimentApi')>('@/api/experimentApi')
  return {
    ...actual,
    experimentApi: {
      conclusionDraft: vi.fn(),
      update: vi.fn(),
    },
  }
})

function makeDelta(overrides: Partial<ExperimentDelta> = {}): ExperimentDelta {
  return {
    peer_id: 'exp-2',
    peer_name: 'control',
    relation: 'vs_control',
    peer_ready: true,
    this_landlord_win_rate: 0.6,
    peer_landlord_win_rate: 0.4,
    landlord_win_rate_diff: 0.2,
    this_landlord_win_rate_ci: null,
    peer_landlord_win_rate_ci: null,
    this_decisive_n: 40,
    peer_decisive_n: 40,
    paired_n: 40,
    paired_landlord_win_rate_diff: 0.2,
    low_power: false,
    can_conclude: true,
    inconclusive_reason: null,
    verdict_key: 'stronger',
    ...overrides,
  }
}

function mountVerdict(delta: ExperimentDelta) {
  const i18n = createI18n({
    legacy: false,
    locale: 'zh-CN',
    missingWarn: false,
    fallbackWarn: false,
    messages: { 'zh-CN': zhCN },
  })
  return mount(StageVerdict, {
    props: {
      experimentId: 'exp-1',
      delta,
      verdictKey: delta.verdict_key ?? 'stronger',
      gamesNeeded: 0,
    },
    global: {
      plugins: [i18n],
      stubs: {
        ExperimentScenarioBars: true,
        MetricHint: true,
        UiDialog: true,
        UiTextarea: true,
        UiButton: true,
      },
    },
  })
}

const GOOD_BAD_CLASS = /ink-success|ink-danger|text-success|text-danger|text-green|text-red/

describe('StageVerdict delta presentation', () => {
  it('does not color a positive Δ as success/good', () => {
    const wrapper = mountVerdict(makeDelta({ landlord_win_rate_diff: 0.2 }))
    const number = wrapper.get('.ink-verdict-number')
    expect(number.text()).toContain('+')
    expect(number.classes().join(' ')).not.toMatch(GOOD_BAD_CLASS)
    expect(number.attributes('class') ?? '').not.toMatch(GOOD_BAD_CLASS)
  })

  it('does not color a negative Δ as danger/bad', () => {
    const wrapper = mountVerdict(
      makeDelta({
        landlord_win_rate_diff: -0.15,
        verdict_key: 'weaker',
        this_landlord_win_rate: 0.35,
        peer_landlord_win_rate: 0.5,
      }),
    )
    const number = wrapper.get('.ink-verdict-number')
    expect(number.text()).toMatch(/[−-]/)
    expect(number.classes().join(' ')).not.toMatch(GOOD_BAD_CLASS)
  })

  it('keeps a weak-sample Δ muted rather than causal-colored', () => {
    const wrapper = mountVerdict(
      makeDelta({
        can_conclude: false,
        inconclusive_reason: 'low_power',
        landlord_win_rate_diff: 0.2,
        verdict_key: 'stronger',
        paired_n: 3,
        this_decisive_n: 3,
        peer_decisive_n: 3,
      }),
    )
    // Weak path uses muted title styling, not ink-verdict-number.
    expect(wrapper.find('.ink-verdict-number').exists()).toBe(false)
    const muted = wrapper.findAll('p').find((node) => node.text().includes('+'))
    expect(muted).toBeTruthy()
    expect(muted!.classes().join(' ')).toContain('text-ink-text-muted')
    expect(muted!.classes().join(' ')).not.toMatch(GOOD_BAD_CLASS)
  })
})
