<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { GameItem } from '@/api/gameApi'
import { formatDateTime } from '@/utils/format'
import UiButton from '@/components/ui/Button.vue'

defineProps<{
  activeGames: GameItem[]
  runningGames: GameItem[]
  finishedGames: GameItem[]
  collectCta: string
  pausingAll: boolean
  actionGameId: string | null
  configLabel: (id: string) => string
  gameStatusLabel: (status: string) => string
}>()

const emit = defineEmits<{
  openGame: [game: GameItem]
  pause: [gameId: string]
  resume: [gameId: string]
  pauseAll: []
}>()

const { t } = useI18n()
</script>

<template>
  <div class="space-y-4">
    <section v-if="activeGames.length > 0" class="space-y-2">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h2 class="text-sm font-semibold text-ink-text">{{ t('gamesTab.active') }}</h2>
        <UiButton
          v-if="runningGames.length > 0"
          variant="secondary"
          size="sm"
          :loading="pausingAll"
          @click="emit('pauseAll')"
        >
          {{ t('gamesTab.pauseAll') }}
        </UiButton>
      </div>
      <div class="overflow-x-auto rounded-ink-md border border-ink-border">
        <table class="w-full min-w-[36rem] text-left text-sm">
          <thead class="bg-ink-surface-muted text-ink-text-muted">
            <tr>
              <th class="px-3 py-2 font-medium">{{ t('gamesTab.colGame') }}</th>
              <th class="px-3 py-2 font-medium">{{ t('gamesTab.colStatus') }}</th>
              <th class="px-3 py-2 font-medium">{{ t('gamesTab.colCreated') }}</th>
              <th class="px-3 py-2 font-medium">{{ t('gamesTab.colActions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="g in activeGames"
              :key="g.id"
              class="border-t border-ink-border hover:bg-ink-surface-muted"
            >
              <td class="px-3 py-2">
                <button
                  type="button"
                  class="font-medium text-ink-primary hover:underline"
                  @click="emit('openGame', g)"
                >
                  {{ g.id }}
                </button>
              </td>
              <td class="px-3 py-2">{{ gameStatusLabel(g.status) }}</td>
              <td class="px-3 py-2 whitespace-nowrap text-ink-text-secondary">
                {{ formatDateTime(g.created_at) }}
              </td>
              <td class="px-3 py-2">
                <div class="flex flex-wrap gap-1.5">
                  <UiButton
                    v-if="g.status === 'running'"
                    variant="secondary"
                    size="sm"
                    :loading="actionGameId === g.id"
                    @click="emit('pause', g.id)"
                  >
                    {{ t('common.pause') }}
                  </UiButton>
                  <UiButton
                    v-else-if="g.status === 'paused'"
                    variant="secondary"
                    size="sm"
                    :loading="actionGameId === g.id"
                    @click="emit('resume', g.id)"
                  >
                    {{ t('common.resume') }}
                  </UiButton>
                  <span v-else class="text-xs text-ink-text-muted">{{ t('common.dash') }}</span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="space-y-2">
      <h2 class="text-sm font-semibold text-ink-text">{{ t('gamesTab.finished') }}</h2>
      <div
        v-if="finishedGames.length === 0"
        class="rounded-ink border border-dashed border-ink-border px-4 py-8 text-center text-sm text-ink-text-muted"
      >
        {{ t('gamesTab.emptyFinished', { cta: collectCta }) }}
      </div>
      <div v-else class="overflow-x-auto rounded-ink-md border border-ink-border">
        <table class="w-full min-w-[32rem] text-left text-sm">
          <thead class="bg-ink-surface-muted text-ink-text-muted">
            <tr>
              <th class="px-3 py-2 font-medium">{{ t('gamesTab.colGame') }}</th>
              <th class="px-3 py-2 font-medium">{{ t('gamesTab.colStatus') }}</th>
              <th class="px-3 py-2 font-medium">{{ t('gamesTab.colWinner') }}</th>
              <th class="px-3 py-2 font-medium">{{ t('gamesTab.colRounds') }}</th>
              <th class="px-3 py-2 font-medium">{{ t('gamesTab.colEnded') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="g in finishedGames"
              :key="g.id"
              class="border-t border-ink-border hover:bg-ink-surface-muted"
            >
              <td class="px-3 py-2">
                <button
                  type="button"
                  class="font-medium text-ink-primary hover:underline"
                  @click="emit('openGame', g)"
                >
                  {{ g.id }}
                </button>
              </td>
              <td class="px-3 py-2">{{ gameStatusLabel(g.status) }}</td>
              <td class="px-3 py-2">
                {{ g.winner_id ? configLabel(g.winner_id) : t('common.dash') }}
              </td>
              <td class="px-3 py-2 tabular-nums">{{ g.total_rounds ?? t('common.dash') }}</td>
              <td class="px-3 py-2 whitespace-nowrap text-ink-text-secondary">
                {{ formatDateTime(g.finished_at ?? g.created_at) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>
