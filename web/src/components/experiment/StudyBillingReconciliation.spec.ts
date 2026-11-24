/** @vitest-environment happy-dom */
import { afterEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { computed } from 'vue'
import { createMemoryHistory, createRouter, matchedRouteKey } from 'vue-router'
import { createPinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import {
  billingReconciliationApi as api,
  type ReconciliationOverview,
  type ReconciliationResult,
  type ReconciliationRecord,
  type ReconciliationSnapshot,
} from '@/api/billingReconciliationApi'
import { studyBillingApi } from '@/api/studyBillingApi'
import StudyBillingReconciliation from './StudyBillingReconciliation.vue'
import BillingReconciliationResult from './BillingReconciliationResult.vue'
import * as confirm from '@/components/ui/confirm'
import zh from '@/i18n/locales/zh-CN'
import en from '@/i18n/locales/en'

enableAutoUnmount(afterEach)
afterEach(() => vi.restoreAllMocks())
const copy = zh.billing.reconciliation
const snapshot: ReconciliationSnapshot = {
  id: 'attempt',
  revision: 2,
  organization_id: 'org-test',
  project_id: 'proj_test',
  start_time: Date.parse('2026-11-17T00:00:00Z') / 1000,
  end_time: Date.parse('2026-11-19T00:01:00Z') / 1000,
  finished_at: '2026-11-19T00:01:01Z',
}
function response(id = 's', records: ReconciliationRecord[] = []) {
  return {
    code: 0,
    message: '',
    data: {
      study_id: id,
      policy: null,
      policy_history: [],
      pending_count: records.filter((r) => r.pending).length,
      admission_blocked: false,
      records,
      page: 1,
      page_size: 10,
      total: records.length,
      read_at: '2026-11-19T00:01:10Z',
    } satisfies ReconciliationOverview,
  }
}
function comparison(): ReconciliationResult {
  return {
    calculation_version: 'project-cost-reconciliation-v1',
    input: {
      attempt_id: 'attempt',
      source_type: 'cost_export',
      source_reference: 'Export fixture',
      organization_id: 'org-test',
      project_id: 'proj_test',
      currency: 'USD',
      source_amount: '0.2',
      period_start: '2026-11-17',
      period_end: '2026-11-19',
      scope_note: 'Project costs only',
    },
    result: 'difference',
    reasons: [],
    interface_amount: '0.1',
    difference: '-0.1',
    included_line_count: 2,
    snapshot: { ...snapshot, amount: '0.1', trigger: 'scheduled', schedule_revision: 1 },
    source_url: 'https://api.openai.com/v1/organization/costs',
    preview_hash: 'a'.repeat(64),
  }
}
function record(): ReconciliationRecord {
  return {
    id: 'r',
    study_id: 's',
    created_at: '2026-11-19T00:02:00Z',
    comparison: comparison(),
    review_revision: 3,
    review_action: 'reopen',
    review_reason: 'Further verification',
    reviewed_at: '2026-11-19T00:03:00Z',
    pending: true,
  }
}
async function setup(locale = 'zh-CN') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:pathMatch(.*)*', component: StudyBillingReconciliation }],
  })
  await router.push('/research/s?task_kind=finance')
  const wrapper = mount(StudyBillingReconciliation, {
    props: { studyId: 's', snapshots: [snapshot], readAt: '1', disabled: false },
    global: {
      provide: {
        [matchedRouteKey as symbol]: computed(() => router.currentRoute.value.matched[0]),
      },
      plugins: [
        router,
        createPinia(),
        createI18n({ legacy: false, locale, messages: { 'zh-CN': zh, en } }),
      ],
      stubs: { Icon: true },
    },
  })
  await flushPromises()
  return { wrapper, router }
}
type Wrapper = Awaited<ReturnType<typeof setup>>['wrapper']
async function click(wrapper: Wrapper, label: string) {
  const button = wrapper.findAll('button').find((b) => b.text() === label)
  expect(button, label).toBeDefined()
  await button!.trigger('click')
  await flushPromises()
}
async function enter(wrapper: Wrapper) {
  await click(wrapper, copy.create)
  const field = (label: string) =>
    wrapper
      .findAll('label')
      .find((l) => l.text().startsWith(label))!
      .find('input')
  await field(copy.reference).setValue('Export fixture')
  await field(copy.amount).setValue('0.2')
  await wrapper.find('textarea').setValue('Project costs only')
}

it.each(['zh-CN', 'en'])(
  'keeps evidence, arithmetic and coverage limitations distinct in %s',
  async (locale) => {
    vi.spyOn(api, 'get').mockResolvedValue(response())
    const write = vi.spyOn(api, 'save'),
      sync = vi.spyOn(studyBillingApi, 'sync')
    const { wrapper } = await setup(locale)
    const c = locale === 'en' ? en.billing.reconciliation : copy
    expect(wrapper.text()).toContain(c.scope)
    expect(wrapper.text()).toContain(c.limitation)
    expect(wrapper.text()).toContain(c.notBlocked)
    expect(write).not.toHaveBeenCalled()
    expect(sync).not.toHaveBeenCalled()
  },
)
it('previews before saving and sends captured evidence/hash with stable retry identity', async () => {
  vi.spyOn(api, 'get').mockResolvedValue(response())
  vi.spyOn(api, 'preview').mockResolvedValue({ code: 0, message: '', data: comparison() })
  const save = vi
    .spyOn(api, 'save')
    .mockRejectedValueOnce({ code: 'NETWORK_ERROR', message: 'unavailable' })
    .mockResolvedValue({ code: 0, message: '', data: record() })
  const { wrapper } = await setup()
  await enter(wrapper)
  expect(save).not.toHaveBeenCalled()
  await wrapper.find('form').trigger('submit')
  await flushPromises()
  expect(wrapper.text()).toContain(copy.previewOnly)
  expect(wrapper.text()).toContain('-0.1')
  await click(wrapper, copy.save)
  expect(wrapper.find('textarea').element.value).toBe('Project costs only')
  await click(wrapper, copy.save)
  expect(save.mock.calls[0]).toEqual(save.mock.calls[1])
  expect(save).toHaveBeenLastCalledWith('s', {
    ...comparison().input,
    expected_preview_hash: 'a'.repeat(64),
    request_id: expect.any(String),
  })
  expect(wrapper.emitted('saved')).toHaveLength(1)
})

it('reuses the selected CSV bytes when saving and invalidates the preview after column changes', async () => {
  vi.spyOn(api, 'get').mockResolvedValue(response())
  vi.spyOn(api, 'csvColumns').mockResolvedValue({
    code: 0,
    message: '',
    data: ['date', 'amount', 'other'],
  })
  const preview = vi.spyOn(api, 'preview').mockResolvedValue({
    code: 0,
    message: '',
    data: {
      ...comparison(),
      csv_evidence: {
        filename: 'synthetic.csv',
        sha256: 'b'.repeat(64),
        parser_version: 'project-cost-csv-v1',
        columns: {
          amount: 'amount',
          date: 'date',
          organization: null,
          project: null,
          currency: null,
        },
        row_count: 1,
        first_service_date: '2026-11-17',
        last_service_date: '2026-11-17',
      },
    },
  })
  const save = vi.spyOn(api, 'save').mockResolvedValue({ code: 0, message: '', data: record() })
  const { wrapper } = await setup()
  await click(wrapper, copy.csv.create)
  const file = wrapper.get<HTMLInputElement>('input[type="file"]')
  Object.defineProperty(file.element, 'files', {
    value: [new File(['date,amount,other\n2026-11-17,0.2,sample\n'], 'synthetic.csv')],
  })
  await file.trigger('change')
  await flushPromises()
  const select = wrapper.findAll('select')
  await select[0]!.setValue('amount')
  await select[1]!.setValue('date')
  const field = (label: string) =>
    wrapper
      .findAll('label')
      .find((l) => l.text().startsWith(label))!
      .get('input')
  expect(field(copy.organization).element.value).toBe('')
  await field(copy.organization).setValue('org-test')
  await field(copy.csv.project).setValue('proj_test')
  await field(copy.start).setValue('2026-11-17')
  await field(copy.end).setValue('2026-11-19')
  await wrapper.get('textarea').setValue('Project costs only')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.text()).toContain('CSV 来源明细 · synthetic.csv')
  await select[0]!.setValue('other')
  expect(wrapper.findAll('button').some((b) => b.text() === copy.save)).toBe(false)
  await select[0]!.setValue('amount')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  await click(wrapper, copy.save)
  expect(preview).toHaveBeenLastCalledWith('s', expect.objectContaining({ source_amount: null }))
  expect(save).toHaveBeenCalledWith(
    's',
    expect.objectContaining({
      source_amount: null,
      csv: expect.objectContaining({
        filename: 'synthetic.csv',
        content_base64: btoa('date,amount,other\n2026-11-17,0.2,sample\n'),
        amount_column: 'amount',
        date_column: 'date',
      }),
      expected_preview_hash: 'a'.repeat(64),
    }),
  )
})
it('invalidates a preview when input changes and pauses status reads while editing', async () => {
  const get = vi.spyOn(api, 'get').mockResolvedValue(response())
  vi.spyOn(api, 'preview').mockResolvedValue({ code: 0, message: '', data: comparison() })
  const { wrapper } = await setup()
  await enter(wrapper)
  await wrapper.find('form').trigger('submit')
  await flushPromises()
  expect(wrapper.findComponent(BillingReconciliationResult).exists()).toBe(true)
  const count = get.mock.calls.length
  await wrapper.setProps({ readAt: '2' })
  await flushPromises()
  expect(get).toHaveBeenCalledTimes(count)
  await wrapper.find('textarea').setValue('Changed filters')
  expect(wrapper.findComponent(BillingReconciliationResult).exists()).toBe(false)
  expect(wrapper.findAll('button').some((b) => b.text() === copy.save)).toBe(false)
})
it('retains policy inputs and captured revision on conflict and protects navigation', async () => {
  vi.spyOn(api, 'get').mockResolvedValue(response())
  const save = vi
    .spyOn(api, 'policy')
    .mockRejectedValue({ code: 'RECONCILIATION_CONFLICT', message: 'conflict' })
  vi.spyOn(confirm, 'confirmDialog').mockResolvedValue(false)
  const { wrapper, router } = await setup()
  await click(wrapper, copy.policyEdit)
  await wrapper.find('[role="checkbox"]').trigger('click')
  await wrapper.find('textarea').setValue('Hold unresolved differences')
  await wrapper.find('form').trigger('submit')
  await flushPromises()
  expect(save).toHaveBeenCalledWith('s', {
    expected_revision: 0,
    enabled: true,
    reason: 'Hold unresolved differences',
  })
  expect(wrapper.find('textarea').element.value).toBe('Hold unresolved differences')
  expect(wrapper.text()).toContain(zh.error.RECONCILIATION_CONFLICT)
  await router.push('/elsewhere')
  expect(router.currentRoute.value.path).toBe('/research/s')
})
it('records explicit review disposition using its version without changing original arithmetic', async () => {
  const initial = record()
  vi.spyOn(api, 'get').mockResolvedValue(response('s', [initial]))
  const review = vi.spyOn(api, 'review').mockResolvedValue({
    code: 0,
    message: '',
    data: { ...initial, pending: false, review_action: 'resolve', review_revision: 4 },
  })
  const { wrapper } = await setup()
  await click(wrapper, copy.actions.resolve)
  expect(wrapper.text()).toContain(copy.reviewHint)
  await wrapper.find('textarea').setValue('Documented rounding difference; figures retained')
  await wrapper.find('form').trigger('submit')
  await flushPromises()
  expect(review).toHaveBeenCalledWith('s', 'r', {
    expected_revision: 3,
    action: 'resolve',
    reason: 'Documented rounding difference; figures retained',
  })
  expect(initial.comparison.difference).toBe('-0.1')
})
it('renders incomparable amounts as unknown and opens only the captured source snapshot', async () => {
  const initial = record()
  initial.comparison = {
    ...comparison(),
    result: 'not_comparable',
    reasons: ['basis', 'currency'],
    interface_amount: null,
    difference: null,
    included_line_count: null,
  }
  vi.spyOn(api, 'get').mockResolvedValue(response('s', [initial]))
  vi.spyOn(api, 'detail').mockResolvedValue({
    code: 0,
    message: '',
    data: { ...initial, reviews: [] },
  })
  const { wrapper } = await setup()
  expect(wrapper.text()).toContain(copy.reasons.basis)
  expect(wrapper.text()).toContain(copy.unknown)
  expect(wrapper.text()).not.toContain('0.000000')
  await click(wrapper, copy.evidence)
  expect(wrapper.emitted('evidence')).toEqual([['attempt']])
  await click(wrapper, copy.reviewHistory)
  expect(wrapper.text()).toContain(copy.noReviews)
})
it('does not display failed reads as no records or a disabled hold', async () => {
  vi.spyOn(api, 'get').mockRejectedValue(new Error('offline'))
  const { wrapper } = await setup()
  expect(wrapper.text()).toContain(copy.loadFailed)
  expect(wrapper.text()).not.toContain(copy.notBlocked)
  expect(wrapper.text()).not.toContain(copy.noRecords)
})
it('ignores a late preview after changing research', async () => {
  vi.spyOn(api, 'get').mockImplementation(async (id) => response(id))
  let resolve!: (value: { code: number; message: string; data: ReconciliationResult }) => void
  vi.spyOn(api, 'preview').mockImplementation(
    () =>
      new Promise((done) => {
        resolve = done
      }),
  )
  const { wrapper } = await setup()
  await enter(wrapper)
  await wrapper.find('form').trigger('submit')
  await wrapper.setProps({ studyId: 'other', snapshots: [] })
  await flushPromises()
  resolve({ code: 0, message: '', data: comparison() })
  await flushPromises()
  expect(wrapper.text()).not.toContain('Export fixture')
  expect(wrapper.findComponent(BillingReconciliationResult).exists()).toBe(false)
  expect(wrapper.text()).toContain(copy.noSnapshot)
})
