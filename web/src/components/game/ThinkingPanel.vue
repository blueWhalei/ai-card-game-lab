<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { formatMs } from '@/utils/card'
import UiBadge from '@/components/ui/Badge.vue'

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

const { t } = useI18n()
const expandedSet = defineModel<Set<number>>('expandedSet', { default: () => new Set<number>() })

const waitElapsedSec = ref(0)
let waitTimer: ReturnType<typeof setInterval> | null = null

function clearWaitTimer(): void {
  if (waitTimer) {
    clearInterval(waitTimer)
    waitTimer = null
  }
}

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

const isActivelyStreaming = computed(() => {
  return Boolean(props.currentPlayerId) && props.isStreaming !== false
})

const isWaitingForFirstToken = computed(() => {
  return Boolean(
    props.currentPlayerId &&
      !props.currentReasoning &&
      !props.currentAnswer &&
      !props.currentThinking,
  )
})

watch(
  () => [props.currentPlayerId, isWaitingForFirstToken.value] as const,
  ([playerId, waiting]) => {
    clearWaitTimer()
    waitElapsedSec.value = 0
    if (!playerId || !waiting) return
    waitTimer = setInterval(() => {
      waitElapsedSec.value += 1
    }, 1000)
  },
  { immediate: true },
)

onUnmounted(() => {
  clearWaitTimer()
})
</script>

<template>
  <div class="flex h-full flex-col bg-ink-obs-bg text-ink-obs-text">
    <!-- 实时思考区域 -->
    <div
      v-if="currentPlayerId && (currentReasoning || currentAnswer || currentThinking)"
      class="border-b border-ink-obs-border p-4"
    >
      <div v-if="currentReasoning" class="mb-3">
        <div class="mb-2 flex items-center gap-2">
          <span class="inline-block h-2 w-2 animate-pulse rounded-full bg-ink-obs-accent" />
          <span class="text-sm font-medium text-ink-obs-accent">{{ t('game.reasoning') }}</span>
          <UiBadge v-if="currentRound" class="!bg-ink-obs-surface !text-ink-obs-muted">
            R{{ currentRound }}
          </UiBadge>
          <span v-if="isActivelyStreaming && !currentAnswer" class="text-xs text-ink-obs-muted">
            {{ t('game.generating') }}
          </span>
        </div>
        <div
          class="max-h-40 overflow-y-auto rounded-ink bg-ink-obs-surface p-3 text-sm leading-relaxed text-ink-obs-text"
        >
          {{ currentReasoning
          }}<span
            v-if="isActivelyStreaming && !currentAnswer"
            class="animate-blink ml-0.5 inline-block h-4 w-0.5 bg-ink-obs-accent"
          />
        </div>
      </div>

      <div v-if="currentAnswer || (!currentReasoning && currentThinking)">
        <div class="mb-2 flex items-center gap-2">
          <span class="text-sm font-medium text-ink-obs-text">{{ t('game.finalDecision') }}</span>
        </div>
        <div
          class="rounded-ink border border-ink-obs-border bg-ink-obs-surface/80 p-3 text-sm leading-relaxed text-ink-obs-text"
        >
          {{ currentAnswer || currentThinking }}
        </div>
        <div
          v-if="currentActionType || (currentCards && currentCards.length > 0)"
          class="mt-2 text-xs text-ink-obs-muted"
        >
          {{ t('game.actionLabel', { type: currentActionType || '-' })
          }}<template v-if="currentCards && currentCards.length > 0">
            · {{ currentCards.join(' ') }}
          </template>
        </div>
      </div>

      <details
        v-if="currentPromptMessages && currentPromptMessages.length > 0"
        class="mt-2 text-xs text-ink-obs-muted"
      >
        <summary class="cursor-pointer select-none text-ink-obs-muted hover:text-ink-obs-text">
          {{ t('game.viewPrompt') }}
        </summary>
        <pre
          class="mt-1 max-h-64 overflow-y-auto whitespace-pre-wrap rounded-ink bg-ink-obs-surface p-2 text-xs text-ink-obs-muted"
          >{{ formatPromptMessages(currentPromptMessages) }}</pre
        >
      </details>
      <details v-if="currentRawResponseFull" class="mt-2 text-xs text-ink-obs-muted">
        <summary class="cursor-pointer select-none text-ink-obs-muted hover:text-ink-obs-text">
          {{ t('game.viewRaw') }}
        </summary>
        <pre
          class="mt-1 max-h-64 overflow-y-auto whitespace-pre-wrap rounded-ink bg-ink-obs-surface p-2 text-xs text-ink-obs-muted"
          >{{ currentRawResponseFull }}</pre
        >
      </details>
    </div>

    <!-- 思考中状态(无内容时：本地模型首 token 前也会长时间停在这里) -->
    <div
      v-else-if="currentPlayerId"
      class="flex flex-wrap items-center gap-2 border-b border-ink-obs-border p-4"
    >
      <span class="inline-block h-2 w-2 animate-pulse rounded-full bg-ink-obs-accent" />
      <span class="text-sm text-ink-obs-accent">{{
        t('game.playerThinking', { id: currentPlayerId })
      }}</span>
      <span class="animate-blink ml-1 inline-block h-3 w-0.5 bg-ink-obs-accent" />
      <span v-if="waitElapsedSec > 0" class="text-xs text-ink-obs-muted">
        {{ t('game.waitingElapsed', { sec: waitElapsedSec }) }}
      </span>
    </div>

    <!-- 历史思考链 -->
    <div class="flex-1 overflow-y-auto p-4">
      <div v-if="history.length === 0" class="py-8 text-center text-ink-obs-muted">
        {{ t('game.noThinking') }}
      </div>
      <div
        v-for="(entry, i) in [...history].reverse()"
        :key="history.length - 1 - i"
        class="mb-3 rounded-ink border border-ink-obs-border bg-ink-obs-surface p-3"
      >
        <div
          class="flex cursor-pointer items-center justify-between"
          @click="toggleExpand(history.length - 1 - i)"
        >
          <div class="flex flex-wrap items-center gap-2 text-xs text-ink-obs-muted">
            <span class="font-mono">R{{ entry.round }}</span>
            <span class="font-medium text-ink-obs-text">{{ entry.playerId }}</span>
            <span
              v-if="entry.responseTimeMs"
              class="rounded-[6px] bg-ink-obs-bg px-1.5 py-0.5 text-xs text-ink-obs-muted"
            >
              {{ formatMs(entry.responseTimeMs) }}
            </span>
            <span
              v-if="entry.totalTokens"
              class="rounded-[6px] bg-ink-obs-bg px-1.5 py-0.5 text-[11px] text-ink-obs-accent"
            >
              total {{ entry.totalTokens }}
            </span>
            <span
              v-if="entry.modelName"
              class="rounded-[6px] bg-ink-obs-bg px-1.5 py-0.5 text-[11px] text-ink-obs-muted"
            >
              {{ entry.modelName }}
            </span>
          </div>
          <span class="text-ink-obs-muted">{{
            expandedSet.has(history.length - 1 - i) ? '▼' : '▶'
          }}</span>
        </div>

        <div v-if="!expandedSet.has(history.length - 1 - i)" class="mt-1 text-xs text-ink-obs-muted">
          {{ t('game.actionLabel', { type: entry.actionType }) }}
          <span v-if="entry.cards && entry.cards.length > 0"> · {{ entry.cards.join(' ') }}</span>
        </div>

        <div v-else class="mt-2 space-y-2">
          <div v-if="entry.reasoning" class="rounded-ink bg-ink-obs-bg p-2">
            <div class="mb-1 text-xs font-medium text-ink-obs-accent">{{ t('game.reasoning') }}</div>
            <div
              class="max-h-32 overflow-y-auto whitespace-pre-wrap text-sm leading-relaxed text-ink-obs-text"
            >
              {{ entry.reasoning }}
            </div>
          </div>

          <div
            v-if="entry.answer"
            class="rounded-ink border border-ink-obs-border bg-ink-obs-bg/60 p-2"
          >
            <div class="mb-1 text-xs font-medium text-ink-obs-text">{{ t('game.finalDecision') }}</div>
            <div class="whitespace-pre-wrap text-sm leading-relaxed text-ink-obs-text">
              {{ entry.answer }}
            </div>
          </div>

          <div
            v-if="!entry.reasoning && !entry.answer && entry.thinking"
            class="max-h-48 overflow-y-auto whitespace-pre-wrap text-sm leading-relaxed text-ink-obs-text"
          >
            {{ entry.thinking }}
          </div>

          <div
            v-if="entry.promptTokens || entry.completionTokens || entry.totalTokens"
            class="flex flex-wrap gap-2 text-[11px] text-ink-obs-muted"
          >
            <span v-if="entry.promptTokens != null">{{
              t('game.promptTokens', { n: entry.promptTokens })
            }}</span>
            <span v-if="entry.completionTokens != null">{{
              t('game.completionTokens', { n: entry.completionTokens })
            }}</span>
            <span v-if="entry.totalTokens != null">{{
              t('game.tokenTotal', { n: entry.totalTokens })
            }}</span>
          </div>

          <details
            v-if="entry.promptMessages && entry.promptMessages.length > 0"
            class="text-xs text-ink-obs-muted"
          >
            <summary class="cursor-pointer select-none hover:text-ink-obs-text">
              {{ t('game.viewPrompt') }}
            </summary>
            <pre
              class="mt-1 max-h-64 overflow-y-auto whitespace-pre-wrap rounded-ink bg-ink-obs-bg p-2 text-xs text-ink-obs-muted"
              >{{ formatPromptMessages(entry.promptMessages) }}</pre
            >
          </details>
          <details v-if="entry.rawResponseFull" class="text-xs text-ink-obs-muted">
            <summary class="cursor-pointer select-none hover:text-ink-obs-text">
              {{ t('game.viewRaw') }}
            </summary>
            <pre
              class="mt-1 max-h-64 overflow-y-auto whitespace-pre-wrap rounded-ink bg-ink-obs-bg p-2 text-xs text-ink-obs-muted"
              >{{ entry.rawResponseFull }}</pre
            >
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
