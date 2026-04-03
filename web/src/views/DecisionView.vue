<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { showApiError } from '@/utils/error'
import { decisionApi, type DecisionPoint, type DecisionStats } from '@/api/decision'
import { formatDateTime } from '@/utils/format'

const route = useRoute()
const decisionPoints = ref<DecisionPoint[]>([])
const loading = ref(false)
const selectedPoint = ref<DecisionPoint | null>(null)
const stats = ref<DecisionStats | null>(null)
const showStats = ref(false)

const gameId = computed(() => route.query.game_id as string | undefined)
const minQuality = computed(() => {
  const q = route.query.min_quality
  return q ? parseFloat(q as string) : undefined
})

async function fetchDecisionPoints() {
  loading.value = true
  try {
    const params: Record<string, string | number | undefined> = {}
    if (gameId.value) {
      params.game_id = gameId.value
    }
    if (minQuality.value !== undefined) {
      params.min_quality = minQuality.value
    }
    const res = await decisionApi.list(params)
    decisionPoints.value = res.data.data || []
    if (decisionPoints.value.length > 0 && !selectedPoint.value) {
      selectedPoint.value = decisionPoints.value[0] ?? null
    }
  } catch (e: unknown) {
    showApiError(e, '获取决策点数据失败')
  } finally {
    loading.value = false
  }
}

async function fetchStats() {
  try {
    const res = await decisionApi.stats()
    stats.value = res.data.data
  } catch (e: unknown) {
    showApiError(e, '获取统计数据失败')
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

function getQualityColor(score: number): string {
  if (score >= 0.7) return 'bg-[#e1f3d8] text-[#4a9c2d]'
  if (score >= 0.5) return 'bg-[#fff3e0] text-[#e65100]'
  return 'bg-[#ffebee] text-[#c62828]'
}

watch([gameId, minQuality], () => {
  fetchDecisionPoints()
})

onMounted(() => {
  fetchDecisionPoints()
  fetchStats()
})
</script>

<template>
  <div class="page-container">
    <div class="mb-8 flex items-center justify-between">
      <div>
        <h2 class="page-title">决策点数据</h2>
        <p class="page-subtitle">AI 决策状态-动作对，用于 SFT 训练</p>
      </div>
      <div class="flex gap-3">
        <button
          class="rounded-full border border-[#d2d2d7] px-4 py-2 text-sm font-medium text-[#424245] transition-all hover:border-[#86868b]"
          :class="{ 'bg-[#f5f5f7]': showStats }"
          @click="showStats = !showStats"
        >
          {{ showStats ? '隐藏统计' : '统计数据' }}
        </button>
      </div>
    </div>

    <div v-if="showStats && stats" class="mb-6">
      <div class="apple-card">
        <div class="grid grid-cols-2 gap-4 md:grid-cols-4">
          <div class="text-center">
            <div class="text-2xl font-semibold text-[#1d1d1f]">{{ stats.total }}</div>
            <div class="text-xs text-[#86868b]">总决策点</div>
          </div>
          <div class="text-center">
            <div class="text-2xl font-semibold text-[#1d1d1f]">{{ stats.avg_quality.toFixed(2) }}</div>
            <div class="text-xs text-[#86868b]">平均质量</div>
          </div>
          <div class="text-center">
            <div class="text-2xl font-semibold text-[#4a9c2d]">{{ stats.outcome_counts.win || 0 }}</div>
            <div class="text-xs text-[#86868b]">胜利决策</div>
          </div>
          <div class="text-center">
            <div class="text-2xl font-semibold text-[#c62828]">{{ stats.outcome_counts.lose || 0 }}</div>
            <div class="text-xs text-[#86868b]">失败决策</div>
          </div>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <div class="lg:col-span-1">
        <div class="apple-card">
          <div class="mb-4 border-b border-[#f5f5f7] pb-3">
            <h3 class="text-base font-semibold text-[#1d1d1f]">决策点列表</h3>
            <p v-if="gameId" class="mt-1 text-xs text-[#86868b]">游戏: {{ gameId }}</p>
          </div>

          <div v-loading="loading" class="max-h-[600px] overflow-y-auto">
            <div v-if="!loading && decisionPoints.length === 0" class="py-8 text-center text-[#86868b]">
              暂无决策点数据
            </div>

            <div v-else class="space-y-2">
              <div
                v-for="point in decisionPoints"
                :key="point.id"
                class="cursor-pointer rounded-xl p-3 transition-colors"
                :class="selectedPoint?.id === point.id ? 'bg-[#e6f2ff]' : 'hover:bg-[#f5f5f7]'"
                @click="selectPoint(point)"
              >
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-2">
                    <span class="rounded-full bg-[#f5f5f7] px-2 py-0.5 text-xs font-medium text-[#424245]">
                      R{{ point.round_number }}
                    </span>
                    <span class="text-sm font-medium text-[#1d1d1f]">{{ point.player_id }}</span>
                  </div>
                  <span
                    class="rounded-full px-2 py-0.5 text-xs"
                    :class="getQualityColor(point.quality_score)"
                  >
                    {{ point.quality_score.toFixed(2) }}
                  </span>
                </div>
                <div class="mt-2 text-xs text-[#86868b]">
                  {{ formatAction(point.chosen_action) }}
                </div>
                <div class="mt-1 text-xs text-[#86868b]">
                  {{ formatDateTime(point.created_at) }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="lg:col-span-2">
        <div v-if="selectedPoint" class="apple-card">
          <div class="mb-4 border-b border-[#f5f5f7] pb-3">
            <h3 class="text-base font-semibold text-[#1d1d1f]">决策详情</h3>
          </div>

          <div class="space-y-4">
            <div class="grid grid-cols-2 gap-4">
              <div>
                <div class="text-xs font-medium text-[#86868b]">游戏阶段</div>
                <div class="mt-1 text-sm text-[#1d1d1f]">{{ selectedPoint.game_phase }}</div>
              </div>
              <div>
                <div class="text-xs font-medium text-[#86868b]">结果</div>
                <div class="mt-1 text-sm text-[#1d1d1f]">
                  <span
                    v-if="selectedPoint.outcome"
                    class="rounded-full px-2 py-0.5 text-xs"
                    :class="selectedPoint.outcome === 'win' ? 'bg-[#e1f3d8] text-[#4a9c2d]' : 'bg-[#ffebee] text-[#c62828]'"
                  >
                    {{ selectedPoint.outcome === 'win' ? '胜利' : '失败' }}
                  </span>
                  <span v-else class="text-[#86868b]">未知</span>
                </div>
              </div>
            </div>

            <div>
              <div class="text-xs font-medium text-[#86868b]">手牌</div>
              <div class="mt-1 rounded-lg bg-[#f5f5f7] p-2 font-mono text-sm">
                {{ formatCards(selectedPoint.hand_cards) }}
              </div>
            </div>

            <div v-if="selectedPoint.opponent_hands">
              <div class="text-xs font-medium text-[#86868b]">对手剩余牌数</div>
              <div class="mt-1 text-sm text-[#1d1d1f]">
                <span v-for="(count, pid) in selectedPoint.opponent_hands" :key="pid" class="mr-3">
                  {{ pid }}: {{ count }}张
                </span>
              </div>
            </div>

            <div v-if="selectedPoint.last_action">
              <div class="text-xs font-medium text-[#86868b]">上家出牌</div>
              <div class="mt-1 text-sm text-[#1d1d1f]">
                {{ selectedPoint.last_action.player }}: {{ formatAction(selectedPoint.last_action) }}
              </div>
            </div>

            <div>
              <div class="text-xs font-medium text-[#86868b]">合法动作</div>
              <div class="mt-1 flex flex-wrap gap-2">
                <span
                  v-for="(action, idx) in selectedPoint.legal_actions"
                  :key="idx"
                  class="rounded bg-[#f5f5f7] px-2 py-1 text-xs text-[#424245]"
                >
                  {{ formatAction(action) }}
                </span>
              </div>
            </div>

            <div>
              <div class="text-xs font-medium text-[#86868b]">选择动作</div>
              <div class="mt-1 rounded-lg bg-[#e6f2ff] p-2 font-medium text-[#1d1d1f]">
                {{ formatAction(selectedPoint.chosen_action) }}
              </div>
            </div>

            <div v-if="selectedPoint.thinking">
              <div class="text-xs font-medium text-[#86868b]">AI 思考</div>
              <div class="mt-1 rounded-lg bg-[#f5f5f7] p-3 text-sm leading-relaxed text-[#424245]">
                {{ selectedPoint.thinking }}
              </div>
            </div>
          </div>
        </div>

        <div v-else class="apple-card">
          <div class="py-16 text-center text-[#86868b]">
            选择一个决策点查看详情
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
