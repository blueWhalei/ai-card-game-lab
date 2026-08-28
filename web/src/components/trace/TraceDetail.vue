<script setup lang="ts">
import { ref, computed } from 'vue'
import type { Trace } from '@/api/traces'
import UiBadge from '@/components/ui/Badge.vue'

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
  <div class="ink-card">
    <div class="mb-4 flex items-center justify-between border-b border-ink-border pb-3">
      <div>
        <h3 class="text-base font-semibold text-ink-text">追踪详情</h3>
        <p class="mt-1 text-xs text-ink-text-muted">Trace ID: {{ trace.id }}</p>
      </div>
      <div class="flex gap-2">
        <UiBadge variant="muted">{{ trace.prompt_version }}</UiBadge>
        <UiBadge>{{ trace.model }}</UiBadge>
      </div>
    </div>

    <div class="mb-6 grid grid-cols-3 gap-4">
      <div class="rounded-ink-md bg-ink-surface-muted p-3 text-center">
        <div class="text-2xl font-semibold text-ink-text">
          {{ trace.metrics.response_time_ms.toFixed(0) }}
        </div>
        <div class="text-xs text-ink-text-muted">响应时间 (ms)</div>
      </div>
      <div class="rounded-ink-md bg-ink-surface-muted p-3 text-center">
        <div class="text-2xl font-semibold text-ink-text">{{ trace.round_number }}</div>
        <div class="text-xs text-ink-text-muted">轮次</div>
      </div>
      <div class="rounded-ink-md bg-ink-surface-muted p-3 text-center">
        <div
          class="text-2xl font-semibold"
          :class="trace.metrics.used_langchain_parser ? 'text-ink-success' : 'text-ink-accent'"
        >
          {{ trace.metrics.used_langchain_parser ? '✓' : '!' }}
        </div>
        <div class="text-xs text-ink-text-muted">解析状态</div>
      </div>
    </div>

    <div class="mb-6">
      <h4 class="mb-2 text-sm font-semibold text-ink-text-secondary">决策结果</h4>
      <div class="flex items-center gap-3">
        <span
          class="rounded-[6px] bg-ink-primary px-3 py-1 text-sm font-medium text-[var(--ink-primary-fg)]"
        >
          {{ actionType }}
        </span>
        <span v-if="cards.length > 0" class="text-sm text-ink-text-secondary">
          {{ cards.join(', ') }}
        </span>
      </div>
    </div>

    <div v-if="thinking" class="mb-6">
      <h4 class="mb-2 text-sm font-semibold text-ink-text-secondary">AI 思考</h4>
      <div class="max-h-40 overflow-y-auto rounded-ink-md bg-ink-surface-muted p-3">
        <pre class="whitespace-pre-wrap text-sm text-ink-text-secondary">{{ thinking }}</pre>
      </div>
    </div>

    <div class="space-y-4">
      <div>
        <button
          class="flex w-full items-center justify-between rounded-ink-md bg-ink-surface-muted p-3 text-left transition-colors hover:bg-ink-paper-elevated"
          @click="showInput = !showInput"
        >
          <span class="text-sm font-medium text-ink-text-secondary">输入快照</span>
          <span class="text-xs text-ink-text-muted">{{ showInput ? '收起' : '展开' }}</span>
        </button>
        <div
          v-if="showInput"
          class="mt-2 max-h-60 overflow-y-auto rounded-ink-md bg-ink-text p-3"
        >
          <pre class="text-xs text-ink-paper">{{ formatJson(trace.input_snapshot) }}</pre>
        </div>
      </div>

      <div>
        <button
          class="flex w-full items-center justify-between rounded-ink-md bg-ink-surface-muted p-3 text-left transition-colors hover:bg-ink-paper-elevated"
          @click="showOutput = !showOutput"
        >
          <span class="text-sm font-medium text-ink-text-secondary">输出数据</span>
          <span class="text-xs text-ink-text-muted">{{ showOutput ? '收起' : '展开' }}</span>
        </button>
        <div
          v-if="showOutput"
          class="mt-2 max-h-60 overflow-y-auto rounded-ink-md bg-ink-text p-3"
        >
          <pre class="text-xs text-ink-paper">{{ formatJson(trace.output_data) }}</pre>
        </div>
      </div>

      <div v-if="promptPreview">
        <button
          class="flex w-full items-center justify-between rounded-ink-md bg-ink-surface-muted p-3 text-left transition-colors hover:bg-ink-paper-elevated"
          @click="showPrompt = !showPrompt"
        >
          <span class="text-sm font-medium text-ink-text-secondary">Prompt 预览</span>
          <span class="text-xs text-ink-text-muted">{{ showPrompt ? '收起' : '展开' }}</span>
        </button>
        <div
          v-if="showPrompt"
          class="mt-2 max-h-60 overflow-y-auto rounded-ink-md bg-ink-text p-3"
        >
          <pre class="whitespace-pre-wrap text-xs text-ink-paper">{{ promptPreview }}</pre>
        </div>
      </div>
    </div>

    <div v-if="trace.spans && trace.spans.length > 0" class="mt-6">
      <h4 class="mb-2 text-sm font-semibold text-ink-text-secondary">子操作</h4>
      <div class="space-y-2">
        <div
          v-for="span in trace.spans"
          :key="span.id"
          class="rounded-ink-md bg-ink-surface-muted p-3"
        >
          <div class="flex items-center justify-between">
            <span class="text-sm font-medium text-ink-text">{{ span.span_type }}</span>
            <UiBadge :variant="span.status === 'completed' ? 'success' : 'warning'">
              {{ span.status }}
            </UiBadge>
          </div>
          <div v-if="span.data && Object.keys(span.data).length > 0" class="mt-2">
            <pre class="text-xs text-ink-text-muted">{{ formatJson(span.data) }}</pre>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
