import { computed, ref, type Ref } from 'vue'
import { experimentApi, isBenchmarkExperiment, type Experiment } from '@/api/experimentApi'
import { toast } from '@/components/ui/toast'
import { showApiError } from '@/utils/error'
import { remainingCollectGames } from '@/utils/experimentBenchmark'
import { createCollectRequestCache } from '@/utils/collectRequest'
import type { ComposerTranslation } from 'vue-i18n'

type Translate = ComposerTranslation

/**
 * Collect count + submit for the experiment detail page.
 * Default path is inline confirm; the dialog is only for a custom batch from ⋯.
 */
export function useExperimentCollect(opts: {
  experiment: Ref<Experiment | null>
  collectBlocked: Ref<boolean>
  noticeText: Ref<string>
  t: Translate
  onCollected?: () => Promise<void> | void
}) {
  const collecting = ref(false)
  const collectOpen = ref(false)
  const collectCount = ref(1)
  const requestCache = createCollectRequestCache()

  const remaining = computed(() =>
    opts.experiment.value ? remainingCollectGames(opts.experiment.value) : 0,
  )

  function prepareCollect(): boolean {
    if (opts.collectBlocked.value) {
      toast.warning(opts.noticeText.value || opts.t('experiment.apiKeyWarning'))
      return false
    }
    const exp = opts.experiment.value
    if (exp && isBenchmarkExperiment(exp) && remaining.value <= 0) {
      toast.info(opts.t('stage.benchmarkSeedsExhausted'))
      return false
    }
    collectCount.value = Math.min(Math.max(remaining.value, 1), 5)
    return true
  }

  /** Primary CTA: set a sensible default count; stage shows the stepper. */
  function openCollect(): void {
    void prepareCollect()
  }

  /** ⋯ menu: custom batch dialog. */
  function openCollectDialog(): void {
    if (!prepareCollect()) return
    collectOpen.value = true
  }

  async function submitCollect(): Promise<void> {
    if (collecting.value) return
    const exp = opts.experiment.value
    if (!exp) return
    if (opts.collectBlocked.value) {
      toast.warning(opts.noticeText.value || opts.t('experiment.apiKeyWarning'))
      return
    }
    const expBench = exp
    if (isBenchmarkExperiment(expBench) && remaining.value <= 0) {
      toast.info(opts.t('stage.benchmarkSeedsExhausted'))
      return
    }
    const n = collectCount.value ?? 1
    if (n < 1 || n > 50) return
    collecting.value = true
    try {
      const res = await experimentApi.collect(exp.id, {
        count: n,
        idempotency_key: requestCache.get(exp.id, n),
      })
      requestCache.complete(exp.id)
      collectOpen.value = false
      toast.success(opts.t('experiment.startedN', { n: res.data.count }))
      await opts.onCollected?.()
    } catch (e: unknown) {
      showApiError(e, opts.t('experiment.collectFailed'))
    } finally {
      collecting.value = false
    }
  }

  return {
    collecting,
    collectOpen,
    collectCount,
    remaining,
    openCollect,
    openCollectDialog,
    submitCollect,
  }
}
