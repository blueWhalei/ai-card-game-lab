/** @vitest-environment happy-dom */
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { shallowMount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { draftApi } from '@/api/draftApi'
import { createI18n } from 'vue-i18n'
import { routeLocationKey } from 'vue-router'
import { researchApi } from '@/api/researchApi'
import UiButton from '@/components/ui/Button.vue'
import UiTextarea from '@/components/ui/Textarea.vue'
import UiDialog from '@/components/ui/Dialog.vue'
import zhCN from '@/i18n/locales/zh-CN'
import ComparisonResearch from './ComparisonResearch.vue'
import ComparisonReplay from './ComparisonReplay.vue'
import ComparisonPuzzleEvidence from './ComparisonPuzzleEvidence.vue'
import EvidenceCiteButton from './EvidenceCiteButton.vue'
import PuzzleEvidenceReview from './PuzzleEvidenceReview.vue'
import TraceEvidenceReview from './TraceEvidenceReview.vue'

enableAutoUnmount(afterEach)
beforeEach(() => {
  setActivePinia(createPinia())
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
  vi.spyOn(draftApi, 'get').mockResolvedValue({
    code: 0,
    message: 'success',
    data: {
      revision: 0,
      updated_at: null,
      content: {
        kind: 'comparison',
        expected_revision: 0,
        observations: '',
        interpretation: '',
        limitations: '',
        evidence: [],
      },
    },
  })
  vi.spyOn(draftApi, 'save').mockImplementation(async (_kind, _id, revision, content) => ({
    code: 0,
    message: 'success',
    data: { revision: revision + 1, updated_at: '2026', content },
  }))
})
afterEach(async () => {
  await vi.runOnlyPendingTimersAsync()
  vi.useRealTimers()
  vi.restoreAllMocks()
})

it('persists a reviewed invocation and preserves its note when its fingerprint changes', async () => {
  vi.spyOn(researchApi, 'versions').mockResolvedValue({ data: [] } as never)
  const wrapper = shallowMount(ComparisonResearch, {
    props: { paired: true, comparisonId: 'trace-cmp' },
    global: {
      renderStubDefaultSlot: true,
      provide: { [routeLocationKey as symbol]: { query: {} } },
      plugins: [createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })],
    },
  })
  await flushPromises()
  const review = wrapper.findComponent(TraceEvidenceReview)
  review.vm.$emit('cite', { trace_id: 'tr', expected_source_hash: 'a'.repeat(64), note: '' })
  await flushPromises()
  wrapper
    .findAllComponents(UiTextarea)
    .at(-1)!
    .vm.$emit('update:modelValue', 'Source interpretation')
  await flushPromises()
  review.vm.$emit('cite', {
    trace_id: 'tr',
    expected_source_hash: 'b'.repeat(64),
    note: 'must not overwrite',
  })
  await flushPromises()
  await vi.advanceTimersByTimeAsync(1000)
  await flushPromises()
  expect(draftApi.save).toHaveBeenLastCalledWith(
    'comparison',
    'trace-cmp',
    expect.any(Number),
    expect.objectContaining({
      trace_evidence: [
        { trace_id: 'tr', expected_source_hash: 'b'.repeat(64), note: 'Source interpretation' },
      ],
    }),
  )
})
it('cites the selected real decision once and retains observations across panel closure', async () => {
  vi.spyOn(researchApi, 'versions').mockResolvedValue({ data: [] } as never)
  vi.spyOn(researchApi, 'candidates').mockResolvedValue({
    data: {
      total: 2,
      items: [
        {
          id: 'decision-a',
          game_id: 'game-a',
          player_id: 'seat-a',
          round_number: 4,
          action_id: 'play',
        },
        {
          id: 'decision-b',
          game_id: 'game-b',
          player_id: 'seat-b',
          round_number: 8,
          action_id: 'pass',
        },
      ],
    },
  } as never)
  const publish = vi.spyOn(researchApi, 'save')
  const wrapper = shallowMount(ComparisonResearch, {
    props: { paired: false, comparisonId: 'selection-cmp' },
    global: {
      renderStubDefaultSlot: true,
      provide: {
        [routeLocationKey as symbol]: {
          query: { report_id: 'rev', evidence: 'original-citation' },
        },
      },
      plugins: [createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })],
    },
  })
  await flushPromises()
  await wrapper
    .findAll('button')
    .find((b) => b.text().includes('seat-b'))!
    .trigger('click')
  expect(wrapper.find('article').text()).toContain('game-b')
  expect(wrapper.findComponent({ name: 'RouterLink' }).props('to')).toMatchObject({
    query: { decision_id: 'decision-b', report_id: 'rev', evidence: 'original-citation' },
  })
  expect(wrapper.findComponent({ name: 'ComparisonDecision' }).props('candidate').id).toBe(
    'decision-b',
  )
  const cite = () => wrapper.findComponent(EvidenceCiteButton)
  cite().vm.$emit('cite', ['decision-b'])
  await flushPromises()
  const observations = wrapper.findAllComponents(UiTextarea)[0]!
  observations.vm.$emit('update:modelValue', 'Selected the pass action')
  await flushPromises()
  wrapper.findAllComponents(UiDialog)[0]!.vm.$emit('update:open', false)
  await flushPromises()
  cite().vm.$emit('cite', ['decision-b'])
  await flushPromises()
  expect(wrapper.findAllComponents(UiTextarea)[0]!.props('modelValue')).toBe(
    'Selected the pass action',
  )
  await vi.advanceTimersByTimeAsync(1000)
  await flushPromises()
  expect(draftApi.save).toHaveBeenLastCalledWith(
    'comparison',
    'selection-cmp',
    expect.any(Number),
    expect.objectContaining({
      observations: 'Selected the pass action',
      evidence: [{ decision_id: 'decision-b', note: '' }],
    }),
  )
  expect(publish).not.toHaveBeenCalled()
})
it('cites both sides once and rejects an overflowing pair atomically', async () => {
  vi.spyOn(researchApi, 'versions').mockResolvedValue({ data: [] } as never)
  const candidates = vi.spyOn(researchApi, 'candidates')
  const publish = vi.spyOn(researchApi, 'save')
  const wrapper = shallowMount(ComparisonResearch, {
    props: { paired: true, comparisonId: 'paired-cmp' },
    global: {
      renderStubDefaultSlot: true,
      provide: { [routeLocationKey as symbol]: { query: {} } },
      plugins: [createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })],
    },
  })
  await flushPromises()
  const replay = wrapper.findComponent(ComparisonReplay)
  replay.vm.$emit('cite', ['a', 'b', 'a'])
  replay.vm.$emit('cite', ['a', 'b'])
  await flushPromises()
  expect(wrapper.findAllComponents(UiTextarea)).toHaveLength(5)
  replay.vm.$emit(
    'cite',
    Array.from({ length: 27 }, (_, n) => `e-${n}`),
  )
  await flushPromises()
  replay.vm.$emit('cite', ['overflow-a', 'overflow-b'])
  await flushPromises()
  expect(wrapper.find('[role="alert"]').text()).toContain('未添加任何新条目')
  expect(wrapper.findAllComponents(UiTextarea)).toHaveLength(32)
  expect(candidates).not.toHaveBeenCalled()
  expect(publish).not.toHaveBeenCalled()
})

it('preserves the draft after a revision conflict and never saves on mount', async () => {
  vi.spyOn(researchApi, 'versions').mockResolvedValue({ data: [] } as never)
  vi.spyOn(researchApi, 'candidates').mockResolvedValue({ data: { total: 0, items: [] } } as never)
  const save = vi
    .spyOn(researchApi, 'save')
    .mockRejectedValue({ code: 'RESEARCH_CONFLICT', message: '研究结论已有新版本' })
  const wrapper = shallowMount(ComparisonResearch, {
    props: { paired: false, comparisonId: 'cmp' },
    global: {
      renderStubDefaultSlot: true,
      provide: { [routeLocationKey as symbol]: { query: {} } },
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
    puzzle_evidence: [],
    trace_evidence: [],
  })
  expect(wrapper.find('[role="alert"]').text()).toContain('研究结论已有新版本')
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
    props: { paired: false, comparisonId: 'cmp' },
    global: {
      renderStubDefaultSlot: true,
      provide: { [routeLocationKey as symbol]: { query: {} } },
      plugins: [createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })],
    },
  })
  await flushPromises()
  expect(wrapper.text()).toContain('原始决策已删除')
  expect(wrapper.text()).toContain('Evidence note')
  expect(
    wrapper
      .findAllComponents({ name: 'RouterLink' })
      .some((link) => link.props('to')?.path === '/pipeline/decisions'),
  ).toBe(false)
  expect(
    wrapper
      .findAllComponents({ name: 'RouterLink' })
      .some((link) => link.props('to')?.name === 'research-report'),
  ).toBe(true)
  wrapper
    .findAllComponents(UiButton)
    .find((b) => b.text() === '基于此版修订')!
    .vm.$emit('click')
  await flushPromises()
  expect(wrapper.findAllComponents(UiTextarea)[0]!.props('modelValue')).toBe('Saved observation')
})

it('persists a test citation and retains it when publication detects a changed file', async () => {
  vi.spyOn(researchApi, 'versions').mockResolvedValue({ data: [] } as never)
  vi.spyOn(researchApi, 'candidates').mockResolvedValue({ data: { total: 0, items: [] } } as never)
  const save = vi
    .spyOn(researchApi, 'save')
    .mockRejectedValue({ code: 'RESEARCH_PUZZLE_CHANGED', message: 'Changed' })
  const wrapper = shallowMount(ComparisonResearch, {
    props: { paired: false, comparisonId: 'tests-cmp' },
    global: {
      renderStubDefaultSlot: true,
      provide: { [routeLocationKey as symbol]: { query: {} } },
      plugins: [createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })],
    },
  })
  await flushPromises()
  const references = [
    {
      pack_id: 'pack',
      run_id: 'run_12345678',
      expected_report_hash: 'a'.repeat(64),
      note: 'Exploratory diagnosis',
    },
  ]
  expect(draftApi.save).not.toHaveBeenCalled()
  wrapper.findComponent(PuzzleEvidenceReview).vm.$emit('cite', references[0])
  wrapper
    .findComponent(PuzzleEvidenceReview)
    .vm.$emit('cite', { ...references[0], note: 'Duplicate' })
  await flushPromises()
  expect(wrapper.findComponent(ComparisonPuzzleEvidence).props('modelValue')).toEqual(references)
  wrapper.findAllComponents(UiTextarea)[0]!.vm.$emit('update:modelValue', 'Observation')
  wrapper.findAllComponents(UiTextarea)[2]!.vm.$emit('update:modelValue', 'Selected position only')
  await vi.advanceTimersByTimeAsync(1000)
  await flushPromises()
  expect(draftApi.save).toHaveBeenLastCalledWith(
    'comparison',
    'tests-cmp',
    expect.any(Number),
    expect.objectContaining({ puzzle_evidence: references }),
  )
  expect(save).not.toHaveBeenCalled()
  wrapper
    .findAllComponents(UiButton)
    .find((b) => b.text() === zhCN.researchReport.save)!
    .vm.$emit('click')
  await flushPromises()
  expect(save).toHaveBeenCalledWith(
    'tests-cmp',
    expect.objectContaining({ puzzle_evidence: references }),
  )
  expect(wrapper.findComponent(ComparisonPuzzleEvidence).props('modelValue')).toEqual(references)
  expect(wrapper.findAllComponents(UiTextarea)[0]!.props('modelValue')).toBe('Observation')
  expect(wrapper.find('[role="alert"]').exists()).toBe(true)
})
