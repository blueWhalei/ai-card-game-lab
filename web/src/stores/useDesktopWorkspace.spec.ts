/** @vitest-environment happy-dom */
import { beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { invoke, isTauri } from '@tauri-apps/api/core'
import { getCurrentWebviewWindow } from '@tauri-apps/api/webviewWindow'
import { useDesktopWorkspace } from './useDesktopWorkspace'
import { toast } from '@/components/ui/toast'
import { restoredWorkspaceRoute, workspaceRoute } from '@/utils/workspaceRoute'
import appRouter from '@/router'

vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn(), isTauri: vi.fn() }))
vi.mock('@tauri-apps/api/webviewWindow', () => ({ getCurrentWebviewWindow: vi.fn() }))
vi.mock('@/components/ui/toast', () => ({ toast: { warning: vi.fn() } }))

beforeEach(() => {
  vi.resetAllMocks()
  setActivePinia(createPinia())
  vi.mocked(isTauri).mockReturnValue(true)
  vi.mocked(getCurrentWebviewWindow).mockReturnValue({ label: 'main' } as ReturnType<
    typeof getCurrentWebviewWindow
  >)
  vi.mocked(invoke).mockResolvedValue(null)
})

async function routerAt(path = '/') {
  const component = { template: '<div />' }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component, meta: { desktopResume: [] } },
      { path: '/research/:id', component, meta: { desktopResume: [] } },
      {
        path: '/experiments/compare',
        component,
        meta: { desktopResume: ['snapshot', 'seed', 'turn'] },
      },
      { path: '/settings', component },
    ],
  })
  await router.push(path)
  return router
}

it('restores comparison position before use and saves the latest location after cancelled close', async () => {
  const saved = '/experiments/compare?snapshot=c1&seed=42&turn=9'
  vi.mocked(invoke).mockResolvedValue(saved)
  const router = await routerAt()
  const store = useDesktopWorkspace()
  const disconnect = await store.initialize(router)
  expect(router.currentRoute.value.fullPath).toBe(saved)
  expect(invoke).toHaveBeenCalledTimes(1)
  expect(await store.flush()).toBe(true)
  expect(invoke).toHaveBeenLastCalledWith('save_workspace', { route: saved })
  await router.push('/research/new')
  await store.flush()
  expect(invoke).toHaveBeenLastCalledWith('save_workspace', { route: '/research/new' })
  disconnect()
  vi.mocked(invoke).mockClear()
  await store.flush()
  expect(invoke).not.toHaveBeenCalled()
})

it('keeps the last research location through settings and honors explicitly returning home', async () => {
  const router = await routerAt('/research/first')
  const store = useDesktopWorkspace()
  await store.initialize(router)
  expect(invoke).not.toHaveBeenCalled()
  await router.push('/settings')
  await store.flush()
  expect(invoke).toHaveBeenLastCalledWith('save_workspace', { route: '/research/first' })
  await router.push('/')
  await store.flush()
  expect(invoke).toHaveBeenLastCalledWith('save_workspace', { route: '/' })
})

it('does not record aborted navigation', async () => {
  const router = await routerAt('/research/kept')
  const store = useDesktopWorkspace()
  await store.initialize(router)
  router.beforeEach(() => false)
  await router.push('/')
  await store.flush()
  expect(invoke).toHaveBeenLastCalledWith('save_workspace', { route: '/research/kept' })
})

it('makes no native calls in a browser or evidence window', async () => {
  const router = await routerAt()
  const store = useDesktopWorkspace()
  vi.mocked(isTauri).mockReturnValue(false)
  await store.initialize(router)
  await store.flush()
  vi.mocked(isTauri).mockReturnValue(true)
  vi.mocked(getCurrentWebviewWindow).mockReturnValue({ label: 'evidence-1' } as ReturnType<
    typeof getCurrentWebviewWindow
  >)
  await store.initialize(router)
  await store.flush()
  expect(invoke).not.toHaveBeenCalled()
})

it('treats a missing record as first launch and reports corrupt reads without blocking startup', async () => {
  const router = await routerAt()
  const store = useDesktopWorkspace()
  const disconnect = await store.initialize(router)
  expect(toast.warning).not.toHaveBeenCalled()
  disconnect()
  vi.mocked(invoke).mockRejectedValue(new Error('corrupt record'))
  await store.initialize(router)
  expect(router.currentRoute.value.path).toBe('/')
  expect(toast.warning).toHaveBeenCalledTimes(1)
  expect(await store.flush()).toBe(false)
  vi.mocked(invoke).mockResolvedValue(undefined)
  expect(await store.flush()).toBe(true)
})

it('rejects unsupported stored routes instead of replaying form actions or external addresses', async () => {
  const router = await routerAt()
  for (const path of [
    'https://example.com',
    '//example.com',
    '/\\example.com',
    '/settings',
    '/research/x#create',
    '/research/x?create=1',
  ]) {
    expect(() => restoredWorkspaceRoute(router, path)).toThrow()
  }
  vi.mocked(invoke).mockResolvedValue('/settings')
  await useDesktopWorkspace().initialize(router)
  expect(router.currentRoute.value.path).toBe('/')
  expect(toast.warning).toHaveBeenCalledTimes(1)
})

it('uses production route declarations to strip form actions and retain decision return context', () => {
  expect(restoredWorkspaceRoute(appRouter, '/experiments/compare?from=exp1')).toBe(
    '/experiments/compare?from=exp1',
  )
  expect(
    workspaceRoute(appRouter, appRouter.resolve('/experiments?study=s1&create=1&token=secret')),
  ).toBe('/experiments?study=s1')
  const decision =
    '/pipeline/decisions?game_id=g1&decision_id=d1&comparison_id=c1&compare_seed=42&compare_turn=9'
  expect(restoredWorkspaceRoute(appRouter, decision)).toBe(decision)
  const tasks = '/research/study?panel=operations&task_state=attention&task_page=2'
  expect(restoredWorkspaceRoute(appRouter, tasks)).toBe(tasks)
  const taskRun = '/experiments/run?task_study=study&task_state=attention&task_page=2'
  expect(restoredWorkspaceRoute(appRouter, taskRun)).toBe(taskRun)
  const trainingTasks =
    '/research/study?panel=operations&task_kind=training&task_state=attention&task_page=2'
  expect(restoredWorkspaceRoute(appRouter, trainingTasks)).toBe(trainingTasks)
  const finance = '/research/study?panel=operations&task_kind=finance&task_page=2'
  expect(restoredWorkspaceRoute(appRouter, finance)).toBe(finance)
  const trainingTask =
    '/pipeline/training?experiment_id=run&study_id=study&task_id=train&task_study=study&task_kind=training&task_state=attention&task_page=2'
  expect(restoredWorkspaceRoute(appRouter, trainingTask)).toBe(trainingTask)
  const testPreview = `/experiments/compare?snapshot=c1&report_id=rev&review_pack=pack&review_result=run_12345678&review_hash=${'a'.repeat(64)}&review_page=3&puzzle_evidence=pack/run_12345678`
  expect(restoredWorkspaceRoute(appRouter, testPreview)).toBe(testPreview)
  expect(workspaceRoute(appRouter, appRouter.resolve(`${testPreview}&cite=1`))).toBe(testPreview)
  const tracePreview = `/experiments/compare?snapshot=c1&report_id=rev&review_trace=tr&review_trace_hash=${'a'.repeat(64)}&trace_evidence=tr`
  expect(restoredWorkspaceRoute(appRouter, tracePreview)).toBe(tracePreview)
  const traceSource =
    '/pipeline/traces?experiment_id=e1&game_id=g1&trace_id=tr&parser_ok=false&report_id=rev&trace_evidence=tr'
  expect(restoredWorkspaceRoute(appRouter, traceSource)).toBe(traceSource)
  expect(restoredWorkspaceRoute(appRouter, '/research-reports/rev?trace_evidence=tr')).toBe(
    '/research-reports/rev?trace_evidence=tr',
  )
  expect(workspaceRoute(appRouter, appRouter.resolve('/research/s1/prompt-ab'))).toBeNull()
  expect(
    workspaceRoute(appRouter, appRouter.resolve('/experiments/compare?snapshot=a&snapshot=b')),
  ).toBe('/experiments/compare')
  expect(
    workspaceRoute(appRouter, appRouter.resolve(`/experiments?study=${'a'.repeat(513)}`)),
  ).toBe('/experiments')
})
