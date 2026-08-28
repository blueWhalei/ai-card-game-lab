<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { showApiError } from '@/utils/error'
import { tracesApi, type Trace } from '@/api/traces'
import TraceDetail from '@/components/trace/TraceDetail.vue'
import { formatDateTime } from '@/utils/format'
import UiSpinner from '@/components/ui/Spinner.vue'
import UiBadge from '@/components/ui/Badge.vue'
import UiEmpty from '@/components/ui/Empty.vue'

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
    <p class="page-subtitle mb-8 mt-0">AI 决策链路追踪与调试</p>

    <div class="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <div class="lg:col-span-1">
        <div class="rounded-ink-md border border-ink-border bg-ink-surface p-5">
          <div class="mb-4 border-b border-ink-border pb-3">
            <h3 class="text-base font-semibold text-ink-text">追踪列表</h3>
            <p v-if="gameId" class="mt-1 text-xs text-ink-text-muted">游戏: {{ gameId }}</p>
          </div>

          <div class="relative max-h-[600px] overflow-y-auto">
            <UiSpinner v-if="loading" overlay label="加载中…" />
            <UiEmpty v-if="!loading && traces.length === 0" title="暂无追踪数据" />

            <div v-else-if="!loading" class="space-y-2">
              <div
                v-for="trace in traces"
                :key="trace.id"
                class="cursor-pointer rounded-ink-md p-3 transition-colors"
                :class="
                  selectedTrace?.id === trace.id
                    ? 'bg-ink-primary-muted'
                    : 'hover:bg-ink-surface-muted'
                "
                @click="selectTrace(trace)"
              >
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-2">
                    <UiBadge variant="muted">R{{ trace.round_number }}</UiBadge>
                    <span class="text-sm font-medium text-ink-text">{{ trace.player_id }}</span>
                  </div>
                  <UiBadge :variant="trace.metrics.used_langchain_parser ? 'success' : 'warning'">
                    {{ trace.metrics.used_langchain_parser ? '解析成功' : '降级解析' }}
                  </UiBadge>
                </div>
                <div class="mt-2 flex items-center justify-between text-xs text-ink-text-muted">
                  <span>{{ trace.model }}</span>
                  <span>{{ trace.metrics.response_time_ms.toFixed(0) }}ms</span>
                </div>
                <div class="mt-1 text-xs text-ink-text-muted">
                  {{ formatDateTime(trace.created_at) }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="lg:col-span-2">
        <TraceDetail v-if="selectedTrace" :trace="selectedTrace" />
        <div v-else class="rounded-ink-md border border-ink-border bg-ink-surface p-5">
          <UiEmpty title="选择一个追踪查看详情" />
        </div>
      </div>
    </div>
  </div>
</template>
