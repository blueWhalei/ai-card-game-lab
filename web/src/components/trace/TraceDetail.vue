<script setup lang="ts">
import { ref, computed } from 'vue'
import type { Trace } from '@/api/traces'

const props = defineProps<{
  trace: Trace
}>()

const showInput = ref(true)
const showOutput = ref(true)
const showPrompt = ref(false)

interface OutputAction {
  action_type?: string
  cards?: string[]
}

interface OutputData {
  action?: OutputAction
  thinking?: string
}

interface InputSnapshot {
  messages?: Array<{ role: string; content: string }>
}

const actionType = computed(() => {
  const output = props.trace.output_data as OutputData | undefined
  return output?.action?.action_type || 'UNKNOWN'
})

const cards = computed(() => {
  const output = props.trace.output_data as OutputData | undefined
  return output?.action?.cards || []
})

const thinking = computed(() => {
  const output = props.trace.output_data as OutputData | undefined
  return output?.thinking || ''
})

const promptPreview = computed(() => {
  const input = props.trace.input_snapshot as InputSnapshot | undefined
  const messages = input?.messages || []
  if (!messages.length) return ''
  return messages.map((m) => `[${m.role}]\n${m.content}`).join('\n\n')
})

function formatJson(data: unknown): string {
  return JSON.stringify(data, null, 2)
}
</script>

<template>
  <div class="apple-card">
    <div class="mb-4 flex items-center justify-between border-b border-[#f5f5f7] pb-3">
      <div>
        <h3 class="text-base font-semibold text-[#1d1d1f]">追踪详情</h3>
        <p class="mt-1 text-xs text-[#86868b]">Trace ID: {{ trace.id }}</p>
      </div>
      <div class="flex gap-2">
        <span class="rounded-full bg-[#f5f5f7] px-3 py-1 text-xs font-medium text-[#424245]">
          {{ trace.prompt_version }}
        </span>
        <span class="rounded-full bg-[#e6f2ff] px-3 py-1 text-xs font-medium text-[#0071e3]">
          {{ trace.model }}
        </span>
      </div>
    </div>

    <div class="mb-6 grid grid-cols-3 gap-4">
      <div class="rounded-xl bg-[#f5f5f7] p-3 text-center">
        <div class="text-2xl font-semibold text-[#1d1d1f]">{{ trace.metrics.response_time_ms.toFixed(0) }}</div>
        <div class="text-xs text-[#86868b]">响应时间 (ms)</div>
      </div>
      <div class="rounded-xl bg-[#f5f5f7] p-3 text-center">
        <div class="text-2xl font-semibold text-[#1d1d1f]">{{ trace.round_number }}</div>
        <div class="text-xs text-[#86868b]">轮次</div>
      </div>
      <div class="rounded-xl bg-[#f5f5f7] p-3 text-center">
        <div
          class="text-2xl font-semibold"
          :class="trace.metrics.used_langchain_parser ? 'text-[#4a9c2d]' : 'text-[#e65100]'"
        >
          {{ trace.metrics.used_langchain_parser ? '✓' : '!' }}
        </div>
        <div class="text-xs text-[#86868b]">解析状态</div>
      </div>
    </div>

    <div class="mb-6">
      <h4 class="mb-2 text-sm font-semibold text-[#424245]">决策结果</h4>
      <div class="flex items-center gap-3">
        <span class="rounded-full bg-[#0071e3] px-3 py-1 text-sm font-medium text-white">
          {{ actionType }}
        </span>
        <span v-if="cards.length > 0" class="text-sm text-[#424245]">
          {{ cards.join(', ') }}
        </span>
      </div>
    </div>

    <div v-if="thinking" class="mb-6">
      <h4 class="mb-2 text-sm font-semibold text-[#424245]">AI 思考</h4>
      <div class="max-h-40 overflow-y-auto rounded-xl bg-[#f5f5f7] p-3">
        <pre class="whitespace-pre-wrap text-sm text-[#424245]">{{ thinking }}</pre>
      </div>
    </div>

    <div class="space-y-4">
      <div>
        <button
          class="flex w-full items-center justify-between rounded-xl bg-[#f5f5f7] p-3 text-left transition-colors hover:bg-[#e8e8ed]"
          @click="showInput = !showInput"
        >
          <span class="text-sm font-medium text-[#424245]">输入快照</span>
          <span class="text-xs text-[#86868b]">{{ showInput ? '收起' : '展开' }}</span>
        </button>
        <div v-if="showInput" class="mt-2 max-h-60 overflow-y-auto rounded-xl bg-[#1d1d1f] p-3">
          <pre class="text-xs text-[#f5f5f7]">{{ formatJson(trace.input_snapshot) }}</pre>
        </div>
      </div>

      <div>
        <button
          class="flex w-full items-center justify-between rounded-xl bg-[#f5f5f7] p-3 text-left transition-colors hover:bg-[#e8e8ed]"
          @click="showOutput = !showOutput"
        >
          <span class="text-sm font-medium text-[#424245]">输出数据</span>
          <span class="text-xs text-[#86868b]">{{ showOutput ? '收起' : '展开' }}</span>
        </button>
        <div v-if="showOutput" class="mt-2 max-h-60 overflow-y-auto rounded-xl bg-[#1d1d1f] p-3">
          <pre class="text-xs text-[#f5f5f7]">{{ formatJson(trace.output_data) }}</pre>
        </div>
      </div>

      <div v-if="promptPreview">
        <button
          class="flex w-full items-center justify-between rounded-xl bg-[#f5f5f7] p-3 text-left transition-colors hover:bg-[#e8e8ed]"
          @click="showPrompt = !showPrompt"
        >
          <span class="text-sm font-medium text-[#424245]">Prompt 预览</span>
          <span class="text-xs text-[#86868b]">{{ showPrompt ? '收起' : '展开' }}</span>
        </button>
        <div v-if="showPrompt" class="mt-2 max-h-60 overflow-y-auto rounded-xl bg-[#1d1d1f] p-3">
          <pre class="whitespace-pre-wrap text-xs text-[#f5f5f7]">{{ promptPreview }}</pre>
        </div>
      </div>
    </div>

    <div v-if="trace.spans && trace.spans.length > 0" class="mt-6">
      <h4 class="mb-2 text-sm font-semibold text-[#424245]">子操作</h4>
      <div class="space-y-2">
        <div
          v-for="span in trace.spans"
          :key="span.id"
          class="rounded-xl bg-[#f5f5f7] p-3"
        >
          <div class="flex items-center justify-between">
            <span class="text-sm font-medium text-[#1d1d1f]">{{ span.span_type }}</span>
            <span
              class="rounded-full px-2 py-0.5 text-xs"
              :class="span.status === 'completed' ? 'bg-[#e1f3d8] text-[#4a9c2d]' : 'bg-[#fff3e0] text-[#e65100]'"
            >
              {{ span.status }}
            </span>
          </div>
          <div v-if="span.data && Object.keys(span.data).length > 0" class="mt-2">
            <pre class="text-xs text-[#86868b]">{{ formatJson(span.data) }}</pre>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
