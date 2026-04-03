<script setup lang="ts">
import { computed } from 'vue'
import type { AggregatedMetrics } from '@/api/traces'

const props = defineProps<{
  metrics: AggregatedMetrics
}>()

function formatNumber(n: number, decimals = 2): string {
  return n.toFixed(decimals)
}

const successCount = computed(() => props.metrics.langchain_success_count ?? 0)

const successRate = computed(() => {
  if (props.metrics.total_traces === 0) return 0
  return (successCount.value / props.metrics.total_traces) * 100
})
</script>

<template>
  <div class="apple-card">
    <div class="mb-4 border-b border-[#f5f5f7] pb-3">
      <h3 class="text-base font-semibold text-[#1d1d1f]">性能指标</h3>
    </div>

    <div class="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5">
      <div class="rounded-xl bg-gradient-to-br from-[#e6f2ff] to-[#f5f5f7] p-4">
        <div class="text-2xl font-bold text-[#0071e3]">{{ formatNumber(metrics.avg_response_time_ms) }}</div>
        <div class="mt-1 text-xs text-[#86868b]">平均响应 (ms)</div>
      </div>

      <div class="rounded-xl bg-gradient-to-br from-[#e1f3d8] to-[#f5f5f7] p-4">
        <div class="text-2xl font-bold text-[#4a9c2d]">{{ formatNumber(metrics.min_response_time_ms) }}</div>
        <div class="mt-1 text-xs text-[#86868b]">最小响应 (ms)</div>
      </div>

      <div class="rounded-xl bg-gradient-to-br from-[#fff3e0] to-[#f5f5f7] p-4">
        <div class="text-2xl font-bold text-[#e65100]">{{ formatNumber(metrics.max_response_time_ms) }}</div>
        <div class="mt-1 text-xs text-[#86868b]">最大响应 (ms)</div>
      </div>

      <div class="rounded-xl bg-gradient-to-br from-[#f5f5f7] to-[#fafafa] p-4">
        <div class="text-2xl font-bold text-[#1d1d1f]">{{ metrics.total_traces }}</div>
        <div class="mt-1 text-xs text-[#86868b]">总追踪数</div>
      </div>

      <div class="rounded-xl bg-gradient-to-br from-[#e6f2ff] to-[#f5f5f7] p-4">
        <div class="text-2xl font-bold text-[#0071e3]">{{ successCount }}</div>
        <div class="mt-1 text-xs text-[#86868b]">解析成功数</div>
      </div>
    </div>

    <div class="mt-4">
      <div class="mb-2 text-xs text-[#86868b]">解析成功率</div>
      <div class="h-2 w-full overflow-hidden rounded-full bg-[#f5f5f7]">
        <div
          class="h-full rounded-full bg-[#4a9c2d] transition-all"
          :style="{ width: `${successRate}%` }"
        />
      </div>
      <div class="mt-1 text-right text-xs text-[#86868b]">
        {{ formatNumber(successRate, 1) }}%
      </div>
    </div>
  </div>
</template>
