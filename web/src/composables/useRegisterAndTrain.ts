import { ref, type Ref } from 'vue'
import { dataApi } from '@/api/dataApi'
import { trainingApi } from '@/api/trainingApi'
import { toast } from '@/components/ui/toast'
import { showApiError } from '@/utils/error'
import { sanitizeNamePart } from '@/utils/experimentWorkbench'
import type { ComposerTranslation } from 'vue-i18n'

type Translate = ComposerTranslation

export type RegisterDatasetParams = {
  name: string
  game_type: string
  experiment_id?: string
  game_id?: string
  player_id?: string
  outcome?: string
  game_phase?: string
  min_quality?: number
  train_usable?: boolean
  train_usable_only?: boolean
  include_thinking?: boolean
  eval_ratio?: number
}

export type RegisterAndTrainOptions = {
  /** When true, create an SFT task after the dataset is registered. */
  startTraining?: boolean
  trainingDepsAvailable?: boolean
  experimentId?: string
  /** Prefix used for generated dataset / task names. */
  nameBase?: string
  stamp?: string
  t: Translate
  busy?: Ref<boolean>
  onTrainStarted?: () => void
}

function stampNow(): string {
  return new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')
}

/**
 * Shared "register ChatML dataset (+ optional SFT task)" flow used by the
 * experiment detail page and the decision workbench.
 */
export function useRegisterAndTrain() {
  const busy = ref(false)

  async function registerDataset(params: RegisterDatasetParams): Promise<{
    id: string
    name: string
    sample_count: number
  }> {
    const res = await dataApi.createDatasetFromDecisions(params)
    return res.data
  }

  async function registerAndMaybeTrain(
    params: RegisterDatasetParams,
    opts: RegisterAndTrainOptions,
  ): Promise<boolean> {
    const flag = opts.busy ?? busy
    flag.value = true
    try {
      const dataset = await registerDataset(params)
      if (!opts.startTraining) {
        toast.success(
          opts.t('decision.savedChatml', {
            name: dataset.name,
            count: dataset.sample_count,
          }),
        )
        return true
      }

      if (!opts.trainingDepsAvailable) {
        toast.warning(
          opts.t('experiment.savedNoDeps', {
            name: dataset.name,
            count: dataset.sample_count,
          }),
        )
        return true
      }

      const base = sanitizeNamePart(opts.nameBase || dataset.name)
      const stamp = opts.stamp || stampNow()
      try {
        const taskRes = await trainingApi.createTask({
          name: `${base}-sft-${stamp}`,
          dataset_id: dataset.id,
          training_type: 'sft',
          experiment_id: opts.experimentId,
        })
        opts.onTrainStarted?.()
        toast.success(opts.t('experiment.trainStartedNamed', { name: taskRes.data.name }))
      } catch (e: unknown) {
        toast.success(
          opts.t('experiment.savedNamed', {
            name: dataset.name,
            count: dataset.sample_count,
          }),
        )
        showApiError(e, opts.t('experiment.trainStartFailed'))
      }
      return true
    } catch (e: unknown) {
      showApiError(e, opts.t('experiment.saveDatasetFailed'))
      return false
    } finally {
      flag.value = false
    }
  }

  return { busy, registerDataset, registerAndMaybeTrain, stampNow }
}
