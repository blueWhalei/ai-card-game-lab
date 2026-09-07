<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { GameItem } from '@/api/gameApi'
import { formatDateTime } from '@/utils/format'
import { formatGameProgress } from '@/utils/gameProgress'
import UiButton from '@/components/ui/Button.vue'

const emit = defineEmits<{
  openGame: [game: GameItem]
  pause: [gameId: string]
  resume: [gameId: string]
  pauseAll: []
  resumeAll: []
}>()

const { t } = useI18n()
const props = defineProps<{
  activeGames: GameItem[]
  runningGames: GameItem[]
  pausedGames: GameItem[]
  finishedGames: GameItem[]
  collectCta: string
  pausingAll: boolean
  resumingAll: boolean
  actionGameId: string | null
  configLabel: (id: string) => string
  gameStatusLabel: (status: string) => string
}>()

function progressText(game: GameItem): string {
  return formatGameProgress(game.progress, t, props.configLabel)
}

function gameLabel(index: number): string {
  return t('gamesTab.gameN', { n: index + 1 })
}
</script>

<template>
  <div class="space-y-ink-4">
    <section v-if="activeGames.length > 0" class="space-y-ink-2">
      <div class="flex flex-wrap items-center justify-between gap-ink-2">
        <h2 class="text-body font-semibold text-ink-text">{{ t('gamesTab.active') }}</h2>
        <div v-if="runningGames.length > 0 || pausedGames.length > 0" class="flex flex-wrap gap-ink-2">
          <UiButton
            v-if="runningGames.length > 0"
            variant="secondary"
            size="sm"
            :loading="pausingAll"
            :disabled="resumingAll"
            @click="emit('pauseAll')"
          >
            {{ t('gamesTab.pauseAll') }}
          </UiButton>
          <UiButton
            v-if="pausedGames.length > 0"
            variant="secondary"
            size="sm"
            :loading="resumingAll"
            :disabled="pausingAll"
            @click="emit('resumeAll')"
          >
            {{ t('gamesTab.resumeAll') }}
          </UiButton>
        </div>
      </div>
      <div class="overflow-x-auto rounded-ink-md border border-ink-border">
        <table class="w-full min-w-[36rem] text-left text-body">
          <thead class="bg-ink-surface-muted text-ink-text-muted">
            <tr>
              <th class="px-3 py-ink-2 font-medium text-caption">{{ t('gamesTab.colGame') }}</th>
              <th class="px-3 py-ink-2 font-medium text-caption">{{ t('gamesTab.colStatus') }}</th>
              <th class="px-3 py-ink-2 font-medium text-caption">{{ t('gamesTab.colProgress') }}</th>
              <th class="px-3 py-ink-2 font-medium text-caption">{{ t('gamesTab.colActions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(g, index) in activeGames"
              :key="g.id"
              class="border-t border-ink-border hover:bg-ink-surface-muted"
              :class="
                g.status === 'running' &&
                'bg-ink-primary-muted/50 shadow-[inset_2px_0_0_0_var(--ink-primary)]'
              "
            >
              <td class="px-3 py-ink-2 align-middle">
                <button
                  type="button"
                  class="font-medium text-ink-primary hover:underline"
                  :title="g.id"
                  @click="emit('openGame', g)"
                >
                  {{ gameLabel(index) }}
                </button>
              </td>
              <td class="px-3 py-ink-2 align-middle">{{ gameStatusLabel(g.status) }}</td>
              <td class="px-3 py-ink-2 align-middle text-ink-text-secondary">
                {{ progressText(g) }}
              </td>
              <td class="px-3 py-ink-2 align-middle">
                <div class="flex flex-wrap items-center gap-1.5">
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
                  <span v-else class="text-caption text-ink-text-muted">{{ t('common.dash') }}</span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="space-y-ink-2">
      <h2 class="text-body font-semibold text-ink-text">{{ t('gamesTab.finished') }}</h2>
      <div
        v-if="finishedGames.length === 0"
        class="rounded-ink border border-dashed border-ink-border px-4 py-8 text-center text-body text-ink-text-muted"
      >
        {{ t('gamesTab.emptyFinished', { cta: collectCta }) }}
      </div>
      <div v-else class="overflow-x-auto rounded-ink-md border border-ink-border">
        <table class="w-full min-w-[32rem] text-left text-body">
          <thead class="bg-ink-surface-muted text-ink-text-muted">
            <tr>
              <th class="px-3 py-ink-2 font-medium text-caption">{{ t('gamesTab.colGame') }}</th>
              <th class="px-3 py-ink-2 font-medium text-caption">{{ t('gamesTab.colStatus') }}</th>
              <th class="px-3 py-ink-2 font-medium text-caption">{{ t('gamesTab.colWinner') }}</th>
              <th class="px-3 py-ink-2 font-medium text-caption">{{ t('gamesTab.colRounds') }}</th>
              <th class="px-3 py-ink-2 font-medium text-caption">{{ t('gamesTab.colEnded') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(g, index) in finishedGames"
              :key="g.id"
              class="border-t border-ink-border hover:bg-ink-surface-muted"
            >
              <td class="px-3 py-ink-2 align-middle">
                <button
                  type="button"
                  class="font-medium text-ink-primary hover:underline"
                  :title="g.id"
                  @click="emit('openGame', g)"
                >
                  {{ gameLabel(index) }}
                </button>
              </td>
              <td class="px-3 py-ink-2 align-middle">{{ gameStatusLabel(g.status) }}</td>
              <td class="px-3 py-ink-2 align-middle">
                {{ g.winner_id ? configLabel(g.winner_id) : t('common.dash') }}
              </td>
              <td class="px-3 py-ink-2 align-middle tabular-nums">{{ g.total_rounds ?? t('common.dash') }}</td>
              <td class="px-3 py-ink-2 align-middle whitespace-nowrap tabular-nums text-ink-text-secondary">
                {{ formatDateTime(g.finished_at ?? g.created_at) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>
