<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { showApiError } from '@/utils/error'
import { tracesApi, type Trace } from '@/api/traces'
import TraceDetail from '@/components/trace/TraceDetail.vue'
import { formatDateTime } from '@/utils/format'

const route = useRoute()
const traces = ref<Trace[]>([])
const loading = ref(false)
const selectedTrace = ref<Trace | null>(null)

const gameId = computed(() => route.query.game_id as string | undefined)

async function fetchTraces() {
  loading.value = true
  try {
    const params: Record<string, string | number> = {}
    if (gameId.value) {
      params.game_id = gameId.value
    }
    const res = await tracesApi.list(params)
    traces.value = res.data.data || []
    if (traces.value.length > 0 && !selectedTrace.value) {
      selectedTrace.value = traces.value[0] ?? null
    }
  } catch (e: unknown) {
    showApiError(e, '获取追踪数据失败')
  } finally {
    loading.value = false
  }
}

function selectTrace(trace: Trace) {
  selectedTrace.value = trace
}

watch(gameId, fetchTraces)

onMounted(fetchTraces)
</script>

<template>
  <div class="page-container">
    <div class="mb-8 flex items-center justify-between">
      <div>
        <h2 class="page-title">决策追踪</h2>
        <p class="page-subtitle">AI 决策链路追踪与调试</p>
      </div>
    </div>

    <div class="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <div class="lg:col-span-1">
        <div class="apple-card">
          <div class="mb-4 border-b border-[#f5f5f7] pb-3">
            <h3 class="text-base font-semibold text-[#1d1d1f]">追踪列表</h3>
            <p v-if="gameId" class="mt-1 text-xs text-[#86868b]">游戏: {{ gameId }}</p>
          </div>

          <div v-loading="loading" class="max-h-[600px] overflow-y-auto">
            <div v-if="!loading && traces.length === 0" class="py-8 text-center text-[#86868b]">
              暂无追踪数据
            </div>

            <div v-else class="space-y-2">
              <div
                v-for="trace in traces"
                :key="trace.id"
                class="cursor-pointer rounded-xl p-3 transition-colors"
                :class="selectedTrace?.id === trace.id ? 'bg-[#e6f2ff]' : 'hover:bg-[#f5f5f7]'"
                @click="selectTrace(trace)"
              >
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-2">
                    <span class="rounded-full bg-[#f5f5f7] px-2 py-0.5 text-xs font-medium text-[#424245]">
                      R{{ trace.round_number }}
                    </span>
                    <span class="text-sm font-medium text-[#1d1d1f]">{{ trace.player_id }}</span>
                  </div>
                  <span
                    class="rounded-full px-2 py-0.5 text-xs"
                    :class="trace.metrics.used_langchain_parser ? 'bg-[#e1f3d8] text-[#4a9c2d]' : 'bg-[#fff3e0] text-[#e65100]'"
                  >
                    {{ trace.metrics.used_langchain_parser ? '解析成功' : '降级解析' }}
                  </span>
                </div>
                <div class="mt-2 flex items-center justify-between text-xs text-[#86868b]">
                  <span>{{ trace.model }}</span>
                  <span>{{ trace.metrics.response_time_ms.toFixed(0) }}ms</span>
                </div>
                <div class="mt-1 text-xs text-[#86868b]">
                  {{ formatDateTime(trace.created_at) }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="lg:col-span-2">
        <TraceDetail v-if="selectedTrace" :trace="selectedTrace" />
        <div v-else class="apple-card">
          <div class="py-16 text-center text-[#86868b]">
            选择一个追踪查看详情
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
