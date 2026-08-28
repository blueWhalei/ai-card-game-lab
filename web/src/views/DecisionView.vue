<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { toast } from '@/components/ui/toast'
import { showApiError } from '@/utils/error'
import { decisionApi, type DecisionPoint, type DecisionStats } from '@/api/decision'
import { dataApi } from '@/api/dataApi'
import { formatDateTime } from '@/utils/format'
import UiSpinner from '@/components/ui/Spinner.vue'
import UiButton from '@/components/ui/Button.vue'
import UiCheckbox from '@/components/ui/Checkbox.vue'
import UiBadge from '@/components/ui/Badge.vue'
import UiEmpty from '@/components/ui/Empty.vue'
import UiSelect from '@/components/ui/Select.vue'
import UiInput from '@/components/ui/Input.vue'

const route = useRoute()
const decisionPoints = ref<DecisionPoint[]>([])
const loading = ref(false)
const exporting = ref(false)
const registering = ref(false)
const selectedPoint = ref<DecisionPoint | null>(null)
const stats = ref<DecisionStats | null>(null)
const showStats = ref(false)
const exportTrainUsableOnly = ref(true)
const exportIncludeThinking = ref(false)
const datasetName = ref('')
/** list-level filter: all | true | false */
const trainUsableFilter = ref<'all' | 'true' | 'false'>('all')

const trainUsableOptions = [
  { label: '全部', value: 'all' },
  { label: '可训练', value: 'true' },
  { label: '不可训练', value: 'false' },
]

const gameId = computed(() => route.query.game_id as string | undefined)
const minQuality = computed(() => {
  const q = route.query.min_quality
  return q ? parseFloat(q as string) : undefined
})

async function fetchDecisionPoints() {
  loading.value = true
  try {
    const params: {
      game_id?: string
      min_quality?: number
      train_usable?: boolean
    } = {}
    if (gameId.value) {
      params.game_id = gameId.value
    }
    if (minQuality.value !== undefined) {
      params.min_quality = minQuality.value
    }
    if (trainUsableFilter.value === 'true') {
      params.train_usable = true
    } else if (trainUsableFilter.value === 'false') {
      params.train_usable = false
    }
    const res = await decisionApi.list(params)
    decisionPoints.value = res.data || []
    selectedPoint.value =
      decisionPoints.value.find((p) => p.id === selectedPoint.value?.id) ??
      decisionPoints.value[0] ??
      null
  } catch (e: unknown) {
    showApiError(e, '获取决策点数据失败')
  } finally {
    loading.value = false
  }
}

async function fetchStats() {
  try {
    const res = await decisionApi.stats()
    stats.value = res.data
  } catch (e: unknown) {
    showApiError(e, '获取统计数据失败')
  }
}

async function exportChatml() {
  exporting.value = true
  try {
    const res = await decisionApi.export({
      game_id: gameId.value,
      min_quality: minQuality.value,
      train_usable_only: exportTrainUsableOnly.value,
      include_thinking: exportIncludeThinking.value,
    })
    const { filepath, count } = res.data
    if (!filepath || count === 0) {
      toast.warning('没有可导出的决策点')
      return
    }
    toast.success(`已导出 ${count} 条 → ${filepath}`)
  } catch (e: unknown) {
    showApiError(e, '导出失败')
  } finally {
    exporting.value = false
  }
}

async function registerAsDataset() {
  const name =
    datasetName.value.trim() ||
    `decisions-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}`
  registering.value = true
  try {
    const res = await dataApi.createDatasetFromDecisions({
      name,
      game_type: 'doudizhu',
      game_id: gameId.value,
      min_quality: minQuality.value,
      train_usable_only: exportTrainUsableOnly.value,
      include_thinking: exportIncludeThinking.value,
    })
    toast.success(
      `已登记训练数据集「${res.data.name}」(${res.data.sample_count} 条 ChatML)，可在训练台选用`,
    )
    datasetName.value = ''
  } catch (e: unknown) {
    showApiError(e, '登记数据集失败')
  } finally {
    registering.value = false
  }
}

function selectPoint(point: DecisionPoint) {
  selectedPoint.value = point
}

function formatCards(cards: string[]): string {
  return cards.join(', ')
}

function formatAction(action: { action_type: string; cards: string[] } | null): string {
  if (!action) return '无'
  if (action.action_type === 'PASS') return '过'
  return `${action.action_type} [${action.cards.join(', ')}]`
}

function getQualityVariant(score: number): 'success' | 'warning' | 'danger' {
  if (score >= 0.7) return 'success'
  if (score >= 0.5) return 'warning'
  return 'danger'
}

watch([gameId, minQuality, trainUsableFilter], () => {
  fetchDecisionPoints()
})

onMounted(() => {
  fetchDecisionPoints()
  fetchStats()
})
</script>

<template>
  <div class="page-container">
    <div class="mb-8 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
      <p class="mt-0 text-base text-ink-text-secondary">
        AI 状态-动作对，用于 SFT。质量分仅为终局胜负代理；训练过滤以「可训练」为准。
      </p>
      <div class="flex flex-wrap items-center gap-3">
        <UiCheckbox v-model="exportTrainUsableOnly" label="仅可训练样本" />
        <UiCheckbox v-model="exportIncludeThinking" label="包含思考" />
        <UiInput
          v-model="datasetName"
          class="w-48"
          placeholder="数据集名称（可选）"
        />
        <UiButton variant="primary" size="sm" :loading="exporting" @click="exportChatml">
          {{ exporting ? '导出中…' : '导出 ChatML' }}
        </UiButton>
        <UiButton
          variant="secondary"
          size="sm"
          :loading="registering"
          @click="registerAsDataset"
        >
          {{ registering ? '登记中…' : '登记为训练数据集' }}
        </UiButton>
        <UiButton
          variant="secondary"
          size="sm"
          :class="showStats ? 'bg-ink-surface-muted' : ''"
          @click="showStats = !showStats"
        >
          {{ showStats ? '隐藏统计' : '统计数据' }}
        </UiButton>
      </div>
    </div>

    <div v-if="showStats && stats" class="mb-6">
      <div class="rounded-ink-md border border-ink-border bg-ink-surface p-5">
        <div class="grid grid-cols-2 gap-4 md:grid-cols-4">
          <div class="text-center">
            <div class="text-2xl font-semibold text-ink-text">{{ stats.total }}</div>
            <div class="text-xs text-ink-text-muted">总决策点</div>
          </div>
          <div class="text-center">
            <div class="text-2xl font-semibold text-ink-text">{{ stats.avg_quality.toFixed(2) }}</div>
            <div class="text-xs text-ink-text-muted">平均质量（胜负代理）</div>
          </div>
          <div class="text-center">
            <div class="text-2xl font-semibold text-ink-success">{{ stats.outcome_counts.win || 0 }}</div>
            <div class="text-xs text-ink-text-muted">胜利决策</div>
          </div>
          <div class="text-center">
            <div class="text-2xl font-semibold text-ink-danger">{{ stats.outcome_counts.lose || 0 }}</div>
            <div class="text-xs text-ink-text-muted">失败决策</div>
          </div>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <div class="lg:col-span-1">
        <div class="rounded-ink-md border border-ink-border bg-ink-surface p-5">
          <div class="mb-4 border-b border-ink-border pb-3">
            <div class="flex items-center justify-between gap-2">
              <h3 class="text-base font-semibold text-ink-text">决策点列表</h3>
              <UiSelect
                v-model="trainUsableFilter"
                :options="trainUsableOptions"
                class="w-28"
                placeholder="可训练"
              />
            </div>
            <p v-if="gameId" class="mt-1 text-xs text-ink-text-muted">游戏: {{ gameId }}</p>
          </div>

          <div class="relative max-h-[600px] overflow-y-auto">
            <UiSpinner v-if="loading" overlay label="加载中…" />
            <UiEmpty v-if="!loading && decisionPoints.length === 0" title="暂无决策点数据" />

            <div v-else-if="!loading" class="space-y-2">
              <div
                v-for="point in decisionPoints"
                :key="point.id"
                class="cursor-pointer rounded-ink-md p-3 transition-colors"
                :class="
                  selectedPoint?.id === point.id
                    ? 'bg-ink-primary-muted'
                    : 'hover:bg-ink-surface-muted'
                "
                @click="selectPoint(point)"
              >
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-2">
                    <UiBadge variant="muted">R{{ point.round_number }}</UiBadge>
                    <span class="text-sm font-medium text-ink-text">{{ point.player_id }}</span>
                    <UiBadge :variant="point.train_usable ? 'success' : 'muted'">
                      {{ point.train_usable ? '可训' : '不可训' }}
                    </UiBadge>
                  </div>
                  <UiBadge :variant="getQualityVariant(point.quality_score)">
                    {{ point.quality_score.toFixed(2) }}
                  </UiBadge>
                </div>
                <div class="mt-2 text-xs text-ink-text-muted">
                  {{ formatAction(point.chosen_action) }}
                </div>
                <div class="mt-1 text-xs text-ink-text-muted">
                  {{ formatDateTime(point.created_at) }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="lg:col-span-2">
        <div v-if="selectedPoint" class="rounded-ink-md border border-ink-border bg-ink-surface p-5">
          <div class="mb-4 border-b border-ink-border pb-3">
            <h3 class="text-base font-semibold text-ink-text">决策详情</h3>
          </div>

          <div class="space-y-4">
            <div class="grid grid-cols-2 gap-4">
              <div>
                <div class="text-xs font-medium text-ink-text-muted">游戏阶段</div>
                <div class="mt-1 text-sm text-ink-text">{{ selectedPoint.game_phase }}</div>
              </div>
              <div>
                <div class="text-xs font-medium text-ink-text-muted">可训练 / 结果</div>
                <div class="mt-1 flex flex-wrap items-center gap-2 text-sm text-ink-text">
                  <UiBadge :variant="selectedPoint.train_usable ? 'success' : 'muted'">
                    {{ selectedPoint.train_usable ? '可训练' : '不可训练' }}
                  </UiBadge>
                  <UiBadge
                    v-if="selectedPoint.outcome"
                    :variant="selectedPoint.outcome === 'win' ? 'success' : 'danger'"
                  >
                    {{ selectedPoint.outcome === 'win' ? '胜利' : '失败' }}
                  </UiBadge>
                  <span v-else class="text-ink-text-muted">结果未知</span>
                </div>
              </div>
            </div>

            <div>
              <div class="text-xs font-medium text-ink-text-muted">手牌</div>
              <div class="mt-1 rounded-ink bg-ink-surface-muted p-2 font-mono text-sm">
                {{ formatCards(selectedPoint.hand_cards) }}
              </div>
            </div>

            <div v-if="selectedPoint.opponent_hands">
              <div class="text-xs font-medium text-ink-text-muted">对手剩余牌数</div>
              <div class="mt-1 text-sm text-ink-text">
                <span v-for="(count, pid) in selectedPoint.opponent_hands" :key="pid" class="mr-3">
                  {{ pid }}: {{ count }}张
                </span>
              </div>
            </div>

            <div v-if="selectedPoint.last_action">
              <div class="text-xs font-medium text-ink-text-muted">上家出牌</div>
              <div class="mt-1 text-sm text-ink-text">
                {{ selectedPoint.last_action.player }}: {{ formatAction(selectedPoint.last_action) }}
              </div>
            </div>

            <div>
              <div class="text-xs font-medium text-ink-text-muted">合法动作</div>
              <div class="mt-1 flex flex-wrap gap-2">
                <span
                  v-for="(action, idx) in selectedPoint.legal_actions"
                  :key="idx"
                  class="rounded-ink bg-ink-surface-muted px-2 py-1 text-xs text-ink-text-secondary"
                >
                  {{ formatAction(action) }}
                </span>
              </div>
            </div>

            <div>
              <div class="text-xs font-medium text-ink-text-muted">选择动作</div>
              <div class="mt-1 rounded-ink bg-ink-primary-muted p-2 font-medium text-ink-text">
                {{ formatAction(selectedPoint.chosen_action) }}
              </div>
            </div>

            <div v-if="selectedPoint.thinking">
              <div class="text-xs font-medium text-ink-text-muted">AI 思考</div>
              <div class="mt-1 rounded-ink bg-ink-surface-muted p-3 text-sm leading-relaxed text-ink-text-secondary">
                {{ selectedPoint.thinking }}
              </div>
            </div>
          </div>
        </div>

        <div v-else class="rounded-ink-md border border-ink-border bg-ink-surface p-5">
          <UiEmpty title="选择一个决策点查看详情" />
        </div>
      </div>
    </div>
  </div>
</template>
