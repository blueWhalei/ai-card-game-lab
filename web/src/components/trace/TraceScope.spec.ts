/** @vitest-environment happy-dom */
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, shallowMount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter, RouterLink } from 'vue-router'
import VChart from 'vue-echarts'
import { tracesApi, type AggregatedMetrics, type Trace } from '@/api/traces'
import zhCN from '@/i18n/locales/zh-CN'
import ResponseTimeChart from './ResponseTimeChart.vue'
import TraceWorkbenchPanel from './TraceWorkbenchPanel.vue'
import TraceMetrics from './TraceMetrics.vue'
import TraceDetail from './TraceDetail.vue'
import { traceLatency, traceParserStatus } from '@/utils/traceMetrics'

enableAutoUnmount(afterEach)
afterEach(() => vi.restoreAllMocks())
const i18n = () => createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
const record = (id: string, latency: unknown = 0, parsed: unknown = null): Trace => ({
  id,
  game_id: 'g',
  round_number: 1,
  player_id: 'p',
  model: 'fixture',
  prompt_version: 'v1',
  input_snapshot: {},
  output_data: {},
  metrics: { response_time_ms: latency, parser_ok: parsed },
  created_at: '2026-11-09T00:00:00Z',
})
const list = (items: Trace[], total = items.length) => ({
  code: 0,
  message: '',
  data: { items, total, page: 1, page_size: 200 },
})
const metrics = (overrides: Partial<AggregatedMetrics> = {}) => ({
  code: 0,
  message: '',
  data: {
    total_traces: 3,
    response_time_count: 2,
    avg_response_time_ms: 10,
    min_response_time_ms: 0,
    max_response_time_ms: 20,
    parser_success_count: 1,
    parser_evaluated_count: 2,
    ...overrides,
  },
})
beforeEach(() => {
  vi.spyOn(Date, 'now').mockReturnValue(Date.parse('2026-11-09T01:00:00Z'))
  vi.spyOn(tracesApi, 'list').mockResolvedValue(
    list([record('a'), record('b', '20'), record('c', -1)], 212),
  )
  vi.spyOn(tracesApi, 'metrics').mockResolvedValue(metrics())
  vi.spyOn(tracesApi, 'get').mockImplementation(async (id) => ({
    code: 0,
    message: '',
    data: record(id),
  }))
})
function chart() {
  return shallowMount(ResponseTimeChart, {
    props: { gameId: 'g', experimentId: 'run', parserOk: false },
    global: {
      plugins: [i18n()],
      stubs: { UiButton: false, TraceMetrics: false },
    },
  })
}
it('uses identical AND filters and timezone-aware bounds for points and aggregates, then refetches ranges', async () => {
  const wrapper = chart()
  await flushPromises()
  const params = {
    game_id: 'g',
    experiment_id: 'run',
    parser_ok: false,
    player_id: undefined,
    model: undefined,
    start_time: '2026-11-08T01:00:00.000Z',
    end_time: '2026-11-09T01:00:00.000Z',
  }
  expect(tracesApi.metrics).toHaveBeenLastCalledWith(params)
  expect(tracesApi.list).toHaveBeenLastCalledWith({ ...params, page: 1, page_size: 200 })
  expect(wrapper.text()).toContain('此窗口共 212 条')
  expect(wrapper.text()).toContain('绘制 1 个有效时间与耗时点')
  expect(wrapper.text()).toContain('最多显示最新 200 条')
  const option = wrapper.findComponent(VChart).props('option')
  // The rendered metrics use explicit status counts, not the total invocation count.
  expect(wrapper.text()).toContain('50.0%')
  expect(option).toMatchObject({
    xAxis: { type: 'time' },
    series: [
      {
        type: 'scatter',
        data: [
          {
            value: [Date.parse('2026-11-09T00:00:00Z'), 0],
          },
        ],
      },
    ],
  })
  await wrapper
    .findAll('button')
    .find((button) => button.text() === '1小时')!
    .trigger('click')
  await flushPromises()
  expect(tracesApi.metrics).toHaveBeenLastCalledWith({
    ...params,
    start_time: '2026-11-09T00:00:00.000Z',
  })
})
it('clears old chart data while reading and ignores a late response from another scope', async () => {
  let finish: ((value: ReturnType<typeof list>) => void) | undefined
  vi.mocked(tracesApi.list).mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve
      }),
  )
  const wrapper = chart()
  await wrapper.setProps({ gameId: 'next' })
  await flushPromises()
  expect(wrapper.text()).toContain('此窗口共 212 条')
  finish!(list([record('obsolete')], 999))
  await flushPromises()
  expect(wrapper.text()).not.toContain('999')
  vi.mocked(tracesApi.list).mockRejectedValueOnce(new Error('offline'))
  await wrapper.setProps({ gameId: 'failed' })
  await flushPromises()
  expect(wrapper.find('[role="alert"]').text()).toContain('无法读取')
  expect(wrapper.findComponent(TraceMetrics).exists()).toBe(false)
  expect(wrapper.text()).not.toContain('此窗口共 212 条')
  await wrapper
    .findAll('button')
    .find((button) => button.text() === '重试')!
    .trigger('click')
  await flushPromises()
  expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  expect(wrapper.findComponent(TraceMetrics).exists()).toBe(true)
})
it('preserves zero, rejects coerced values, and displays missing denominators without 0%', () => {
  for (const invalid of [undefined, null, true, '12', -1, NaN, Infinity])
    expect(traceLatency(invalid)).toBeNull()
  expect(traceLatency(0)).toBe(0)
  expect(traceParserStatus(false)).toBe(false)
  for (const invalid of [undefined, null, 'false', 0, 1])
    expect(traceParserStatus(invalid)).toBeNull()
  const wrapper = shallowMount(TraceMetrics, {
    props: {
      metrics: metrics({
        response_time_count: 0,
        avg_response_time_ms: null,
        min_response_time_ms: null,
        max_response_time_ms: null,
        parser_evaluated_count: 0,
        parser_success_count: 0,
      }).data,
    },
    global: { plugins: [i18n()] },
  })
  expect(wrapper.text()).not.toContain('0%')
  expect(wrapper.text()).toContain('未记录有效值')
  expect(wrapper.text()).toContain('排除 3 条')
})
it('does not call an absent parse status a failure or a rule fallback in the detail', () => {
  const wrapper = shallowMount(TraceDetail, {
    props: { trace: record('unknown', undefined) },
    global: {
      plugins: [i18n()],
      renderStubDefaultSlot: true,
    },
  })
  expect(wrapper.text()).toContain('解析状态未记录')
  expect(wrapper.text()).not.toContain('规则接管')
  expect(wrapper.text()).toContain('不能视为真实内部推理过程')
})
it('keeps run and game constraints together, clears stale details and ignores late list results', async () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/pipeline/traces', component: { template: '<div />' } }],
  })
  await router.push('/pipeline/traces?experiment_id=run&game_id=g')
  const wrapper = shallowMount(TraceWorkbenchPanel, {
    global: { plugins: [i18n(), router], stubs: { UiButton: false } },
  })
  await flushPromises()
  expect(tracesApi.metrics).toHaveBeenLastCalledWith({ experiment_id: 'run', game_id: 'g' })
  expect(wrapper.findComponent(TraceDetail).props('trace').id).toBe('a')
  let finish: ((value: ReturnType<typeof list>) => void) | undefined
  vi.mocked(tracesApi.list).mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve
      }),
  )
  await router.replace('/pipeline/traces?experiment_id=run&game_id=slow')
  await flushPromises()
  expect(wrapper.findComponent(TraceDetail).exists()).toBe(false)
  await router.replace('/pipeline/traces?experiment_id=run&game_id=fast')
  await flushPromises()
  finish!(list([record('obsolete')]))
  await flushPromises()
  expect(wrapper.findComponent(TraceDetail).props('trace').id).toBe('a')
  vi.mocked(tracesApi.list).mockRejectedValueOnce(new Error('offline'))
  await router.replace('/pipeline/traces?game_id=failed')
  await flushPromises()
  expect(wrapper.findComponent(TraceDetail).exists()).toBe(false)
  expect(wrapper.find('[role="alert"]').exists()).toBe(true)
})

it('loads an off-page citation with AND filters and never substitutes the first row on mismatch', async () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/pipeline/traces', component: { template: '<div />' } }],
  })
  await router.push(
    '/pipeline/traces?experiment_id=run&game_id=g&trace_id=off-page&report_id=rev&trace_evidence=off-page',
  )
  const wrapper = shallowMount(TraceWorkbenchPanel, {
    global: { plugins: [i18n(), router], stubs: { UiButton: false } },
  })
  await flushPromises()
  expect(tracesApi.get).toHaveBeenLastCalledWith('off-page', { experiment_id: 'run', game_id: 'g' })
  expect(wrapper.findComponent(TraceDetail).props('trace').id).toBe('off-page')
  expect(wrapper.findComponent(RouterLink).props('to')).toMatchObject({
    name: 'research-report',
    params: { id: 'rev' },
    query: { trace_evidence: 'off-page' },
  })
  vi.mocked(tracesApi.get).mockRejectedValueOnce(new Error('Wrong owner'))
  await router.replace({ query: { ...router.currentRoute.value.query, game_id: 'wrong' } })
  await flushPromises()
  expect(wrapper.findComponent(TraceDetail).exists()).toBe(false)
  expect(wrapper.get('[role="alert"]').text()).toContain(zhCN.traceCitation.selectionFailed)
  await wrapper
    .findAll('button')
    .find((button) => button.text() === zhCN.traceCitation.clearSelection)!
    .trigger('click')
  await flushPromises()
  expect(router.currentRoute.value.query.trace_id).toBeUndefined()
  expect(router.currentRoute.value.query.report_id).toBe('rev')
  expect(wrapper.findComponent(TraceDetail).props('trace').id).toBe('a')
})
