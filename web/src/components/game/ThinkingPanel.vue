<script setup lang="ts">
import { computed } from 'vue'
import { formatMs } from '@/utils/card'

interface ThinkingEntry {
  playerId: string
  round: number
  thinking: string
  responseTimeMs: number
  promptTokens?: number | null
  completionTokens?: number | null
  totalTokens?: number | null
  modelProvider?: string
  modelName?: string
  actionType?: string
  cards?: string[]
  promptPreview?: string
  rawResponsePreview?: string
  promptMessages?: Array<{ role: string; content: string }>
  rawResponseFull?: string
  reasoning?: string
  answer?: string
}

const props = defineProps<{
  currentPlayerId: string
  currentThinking: string
  currentRound?: number
  currentActionType?: string
  currentCards?: string[]
  currentPromptPreview?: string
  currentRawResponsePreview?: string
  currentPromptMessages?: Array<{ role: string; content: string }>
  currentRawResponseFull?: string
  history: ThinkingEntry[]
  isStreaming?: boolean
  currentReasoning?: string
  currentAnswer?: string
}>()

const expandedSet = defineModel<Set<number>>('expandedSet', { default: () => new Set<number>() })

function toggleExpand(index: number): void {
  const s = new Set(expandedSet.value)
  if (s.has(index)) {
    s.delete(index)
  } else {
    s.add(index)
  }
  expandedSet.value = s
}

function formatPromptMessages(messages: Array<{ role: string; content: string }>): string {
  return messages.map((m) => `[${m.role}]\n${m.content}`).join('\n\n')
}

// Check if currently streaming (has player but thinking is still being populated)
const isActivelyStreaming = computed(() => {
  return props.currentPlayerId && props.isStreaming !== false
})
</script>

<template>
  <div class="flex h-full flex-col">
    <!-- 实时思考区域 -->
    <div v-if="currentPlayerId && (currentReasoning || currentAnswer || currentThinking)" class="border-b border-gray-200 p-4">
      <!-- 推理过程 -->
      <div v-if="currentReasoning" class="mb-3">
        <div class="mb-2 flex items-center gap-2">
          <span class="inline-block h-2 w-2 animate-pulse rounded-full bg-purple-500" />
          <span class="text-sm font-medium text-purple-700">推理过程</span>
          <span v-if="currentRound" class="rounded bg-purple-100 px-1.5 py-0.5 text-xs text-purple-700">R{{ currentRound }}</span>
          <span v-if="isActivelyStreaming && !currentAnswer" class="text-xs text-gray-400">生成中...</span>
        </div>
        <div class="max-h-40 overflow-y-auto rounded-lg bg-purple-50 p-3 text-sm leading-relaxed text-gray-700">
          {{ currentReasoning }}<span v-if="isActivelyStreaming && !currentAnswer" class="animate-blink ml-0.5 inline-block h-4 w-0.5 bg-purple-500" />
        </div>
      </div>

      <!-- 最终决策 -->
      <div v-if="currentAnswer || (!currentReasoning && currentThinking)">
        <div class="mb-2 flex items-center gap-2">
          <span class="text-sm font-medium text-green-700">最终决策</span>
        </div>
        <div class="rounded-lg bg-green-50 p-3 text-sm leading-relaxed text-gray-700">
          {{ currentAnswer || currentThinking }}
        </div>
        <div v-if="currentActionType || (currentCards && currentCards.length > 0)" class="mt-2 text-xs text-gray-600">
          动作: {{ currentActionType || '-' }}<template v-if="currentCards && currentCards.length > 0"> · {{ currentCards.join(' ') }}</template>
        </div>
      </div>

      <!-- Prompt/Response 详情(折叠) -->
      <details v-if="currentPromptMessages && currentPromptMessages.length > 0" class="mt-2 text-xs text-gray-600">
        <summary class="cursor-pointer select-none text-gray-500">查看完整 Prompt</summary>
        <pre class="mt-1 max-h-64 overflow-y-auto whitespace-pre-wrap rounded bg-gray-50 p-2 text-xs text-gray-600">{{ formatPromptMessages(currentPromptMessages) }}</pre>
      </details>
      <details v-if="currentRawResponseFull" class="mt-2 text-xs text-gray-600">
        <summary class="cursor-pointer select-none text-gray-500">查看完整原始响应</summary>
        <pre class="mt-1 max-h-64 overflow-y-auto whitespace-pre-wrap rounded bg-gray-50 p-2 text-xs text-gray-600">{{ currentRawResponseFull }}</pre>
      </details>
    </div>

    <!-- 思考中状态(无内容时) -->
    <div
      v-else-if="currentPlayerId"
      class="flex items-center gap-2 border-b border-gray-200 p-4"
    >
      <span class="inline-block h-2 w-2 animate-pulse rounded-full bg-blue-500" />
      <span class="text-sm text-blue-600">{{ currentPlayerId }} 思考中...</span>
      <span class="animate-blink ml-1 inline-block h-3 w-0.5 bg-blue-500" />
    </div>

    <!-- 历史思考链 -->
    <div class="flex-1 overflow-y-auto p-4">
      <div v-if="history.length === 0" class="py-8 text-center text-gray-400">
        暂无思考记录
      </div>
      <div
        v-for="(entry, i) in [...history].reverse()"
        :key="history.length - 1 - i"
        class="mb-3 rounded-lg bg-gray-50 p-3"
      >
        <div
          class="flex cursor-pointer items-center justify-between"
          @click="toggleExpand(history.length - 1 - i)"
        >
          <div class="flex items-center gap-2 text-xs text-gray-500">
            <span class="font-mono">R{{ entry.round }}</span>
            <span class="font-medium text-gray-700">{{ entry.playerId }}</span>
            <span
              v-if="entry.responseTimeMs"
              class="rounded bg-gray-200 px-1.5 py-0.5 text-xs text-gray-600"
            >
              {{ formatMs(entry.responseTimeMs) }}
            </span>
            <span v-if="entry.totalTokens" class="rounded bg-amber-100 px-1.5 py-0.5 text-[11px] text-amber-700">
              total {{ entry.totalTokens }}
            </span>
            <span v-if="entry.modelName" class="rounded bg-slate-200 px-1.5 py-0.5 text-[11px] text-slate-700">
              {{ entry.modelName }}
            </span>
          </div>
          <span class="text-gray-400">{{ expandedSet.has(history.length - 1 - i) ? '▼' : '▶' }}</span>
        </div>

        <!-- 折叠状态:只显示摘要 -->
        <div v-if="!expandedSet.has(history.length - 1 - i)" class="mt-1 text-xs text-gray-500">
          动作: {{ entry.actionType }}
          <span v-if="entry.cards && entry.cards.length > 0"> · {{ entry.cards.join(' ') }}</span>
        </div>

        <!-- 展开状态:分开显示 -->
        <div v-else class="mt-2 space-y-2">
          <!-- 推理过程 -->
          <div v-if="entry.reasoning" class="rounded-lg bg-purple-50 p-2">
            <div class="mb-1 text-xs font-medium text-purple-700">推理过程</div>
            <div class="max-h-32 overflow-y-auto whitespace-pre-wrap text-sm leading-relaxed text-gray-700">
              {{ entry.reasoning }}
            </div>
          </div>

          <!-- 最终决策 -->
          <div v-if="entry.answer" class="rounded-lg bg-green-50 p-2">
            <div class="mb-1 text-xs font-medium text-green-700">最终决策</div>
            <div class="whitespace-pre-wrap text-sm leading-relaxed text-gray-700">
              {{ entry.answer }}
            </div>
          </div>

          <!-- 兼容旧数据:无 reasoning/answer 时显示 thinking -->
          <div v-if="!entry.reasoning && !entry.answer && entry.thinking" class="max-h-48 overflow-y-auto whitespace-pre-wrap text-sm leading-relaxed text-gray-700">
            {{ entry.thinking }}
          </div>

          <div v-if="entry.promptTokens || entry.completionTokens || entry.totalTokens" class="flex flex-wrap gap-2 text-[11px] text-gray-500">
            <span v-if="entry.promptTokens != null">Prompt: {{ entry.promptTokens }}</span>
            <span v-if="entry.completionTokens != null">Completion: {{ entry.completionTokens }}</span>
            <span v-if="entry.totalTokens != null">Total: {{ entry.totalTokens }}</span>
          </div>

          <!-- Prompt/Response 详情 -->
          <details v-if="entry.promptMessages && entry.promptMessages.length > 0" class="text-xs text-gray-600">
            <summary class="cursor-pointer select-none text-gray-500">查看完整 Prompt</summary>
            <pre class="mt-1 max-h-64 overflow-y-auto whitespace-pre-wrap rounded bg-white p-2 text-xs text-gray-600">{{ formatPromptMessages(entry.promptMessages) }}</pre>
          </details>
          <details v-if="entry.rawResponseFull" class="text-xs text-gray-600">
            <summary class="cursor-pointer select-none text-gray-500">查看完整原始响应</summary>
            <pre class="mt-1 max-h-64 overflow-y-auto whitespace-pre-wrap rounded bg-white p-2 text-xs text-gray-600">{{ entry.rawResponseFull }}</pre>
          </details>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@keyframes blink {
  0%,
  50% {
    opacity: 1;
  }
  51%,
  100% {
    opacity: 0;
  }
}

.animate-blink {
  animation: blink 1s step-end infinite;
}
</style>
