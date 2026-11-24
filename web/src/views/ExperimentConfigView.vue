<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { toast } from '@/components/ui/toast'
import { confirmDialog } from '@/components/ui/confirm'
import { showApiError } from '@/utils/error'
import {
  experimentConfigApi,
  type ExperimentConfig,
  type ExperimentConfigStats,
} from '@/api/experimentConfigApi'
import { formatPercentage } from '@/utils/format'
import { downloadJson, pickJsonFile } from '@/utils/jsonFile'
import UiDropdownMenu from '@/components/ui/DropdownMenu.vue'
import { Icon } from '@iconify/vue'
import UiButton from '@/components/ui/Button.vue'
import PlayerConfigDialog from '@/components/experiment/PlayerConfigDialog.vue'
import { policyLabels, isBaselineKind } from '@/utils/playerPolicy'
import UiSpinner from '@/components/ui/Spinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'
const { t } = useI18n()

const router = useRouter()
const configs = ref<ExperimentConfig[]>([])
const configStats = ref<Map<string, ExperimentConfigStats>>(new Map())
const loading = ref(false)
const packing = ref(false)
const editor = ref<InstanceType<typeof PlayerConfigDialog>>()

const EMPTY_STATS: ExperimentConfigStats = {
  config_id: '',
  decided_games: 0,
  wins: 0,
  losses: 0,
  win_rate: null,
  last_game_id: null,
  last_game_at: null,
}

function getConfigStats(configId: string): ExperimentConfigStats {
  return configStats.value.get(configId) ?? { ...EMPTY_STATS, config_id: configId }
}

async function fetchConfigs() {
  loading.value = true
  try {
    const [configsRes, statsRes] = await Promise.all([
      experimentConfigApi.list(),
      experimentConfigApi.getAllStats(),
    ])
    configs.value = configsRes.data
    const statsMap = new Map<string, ExperimentConfigStats>()
    for (const stat of statsRes.data) {
      statsMap.set(stat.config_id, stat)
    }
    configStats.value = statsMap
  } catch (e: unknown) {
    showApiError(e, t('config.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function handleDelete(config: ExperimentConfig) {
  const id = String(config.id ?? '')
  const ok = await confirmDialog({
    message: t('config.deleteConfirm', { name: config.name || id || t('common.noId') }),
    title: t('config.deleteTitle'),
    confirmText: t('common.delete'),
    danger: true,
  })
  if (!ok) return
  try {
    await experimentConfigApi.delete(id)
    toast.success(t('error.deleted'))
    await fetchConfigs()
  } catch (e: unknown) {
    showApiError(e, t('error.deleteFailed'))
  }
}

onMounted(fetchConfigs)

async function exportPack(): Promise<void> {
  packing.value = true
  try {
    const res = await experimentConfigApi.exportPack()
    await downloadJson('cardlab-players.json', res.data)
  } catch (e: unknown) {
    showApiError(e, t('config.exportFailed'))
  } finally {
    packing.value = false
  }
}

async function importPack(): Promise<void> {
  packing.value = true
  try {
    const raw = await pickJsonFile()
    if (raw == null) return
    const res = await experimentConfigApi.importPack(raw)
    toast.success(
      t('config.importedPack', {
        created: res.data.players_created.length,
        reused: res.data.players_reused.length,
      }),
    )
    const tags = res.data.requirements?.ollama_tags ?? []
    if (tags.length > 0) {
      toast.info(t('experiment.importOllamaTags', { tags: tags.join(', ') }))
    }
    await fetchConfigs()
  } catch (e: unknown) {
    if (e instanceof Error && e.message === 'invalid json') {
      toast.error(t('experiment.importInvalidJson'))
    } else {
      showApiError(e, t('config.importFailed'))
    }
  } finally {
    packing.value = false
  }
}
</script>

<template>
  <div class="page-container research-page">
    <div class="mb-6 flex flex-wrap items-center justify-between gap-3">
      <p class="text-body text-ink-text-secondary">
        {{ loading ? t('common.loading') : t('config.libraryCount', { n: configs.length }) }}
      </p>
      <div class="flex flex-wrap items-center gap-2">
        <UiDropdownMenu
          :items="[
            { id: 'import', label: t('config.importPack'), disabled: packing },
            { id: 'export', label: t('config.exportPack'), disabled: packing },
          ]"
          @select="$event === 'import' ? importPack() : exportPack()"
        >
          <UiButton variant="secondary" :loading="packing">{{ t('config.transfer') }}</UiButton>
        </UiDropdownMenu>
        <UiButton @click="editor?.open()">{{ t('config.add') }}</UiButton>
      </div>
    </div>

    <div class="relative min-h-[200px]">
      <UiSpinner v-if="loading" overlay :label="t('common.loading')" />
      <EmptyState v-else-if="configs.length === 0" :title="t('config.emptyTitle')">
        <template #action>
          <UiButton @click="editor?.open()">{{ t('config.add') }}</UiButton>
          <UiButton variant="secondary" :loading="packing" @click="importPack">
            {{ t('config.importPack') }}
          </UiButton>
        </template>
      </EmptyState>
      <ul v-else class="grid gap-ink-3 md:grid-cols-2">
        <li
          v-for="row in configs"
          :key="row.id"
          class="rounded-ink-md border border-ink-border bg-ink-surface p-ink-6"
        >
          <div class="flex items-start justify-between gap-ink-2">
            <div class="min-w-0">
              <h3 class="break-words text-lead font-semibold text-ink-text">{{ row.name }}</h3>
              <p class="mt-ink-2 break-all text-caption text-ink-text-secondary">
                <template v-if="isBaselineKind(row.policy_kind)">
                  {{ t(policyLabels[row.policy_kind]) }}
                </template>
                <template v-else>
                  {{ row.model_config.provider }} / {{ row.model_config.model_name }}
                </template>
              </p>
              <p
                v-if="!isBaselineKind(row.policy_kind)"
                class="mt-ink-1 text-caption text-ink-text-muted"
              >
                T={{ row.model_config.temperature }} · top_p={{ row.model_config.top_p }} · max={{
                  row.model_config.max_tokens
                }}
              </p>
              <p v-else class="mt-ink-1 text-caption text-ink-text-muted">
                {{ t('config.policyKindHint') }}
              </p>
            </div>
            <UiDropdownMenu
              :items="[
                { id: 'edit', label: t('common.edit') },
                { id: 'delete', label: t('common.delete'), danger: true },
              ]"
              @select="$event === 'edit' ? editor?.open(row) : handleDelete(row)"
            >
              <UiButton
                variant="ghost"
                size="sm"
                class="shrink-0"
                :aria-label="t('config.actionsFor', { name: row.name })"
                ><Icon icon="lucide:more-horizontal" class="h-4 w-4"
              /></UiButton>
            </UiDropdownMenu>
          </div>
          <div
            class="mt-ink-4 flex flex-wrap items-baseline gap-ink-3 border-t border-ink-border pt-ink-4 text-caption text-ink-text-muted"
          >
            <span v-if="getConfigStats(row.id).decided_games > 0" class="tabular-nums">
              {{ t('config.finishedGames', { n: getConfigStats(row.id).decided_games }) }}
            </span>
            <span
              v-if="getConfigStats(row.id).decided_games > 0"
              class="tabular-nums text-ink-text-secondary"
            >
              {{ t('common.winRate') }}
              {{ formatPercentage(getConfigStats(row.id).win_rate) }}
            </span>
            <span v-else>{{ t('config.noFinishedGames') }}</span>
            <button
              v-if="getConfigStats(row.id).last_game_id"
              type="button"
              class="text-ink-primary hover:underline"
              @click="router.push(`/game/${getConfigStats(row.id).last_game_id}`)"
            >
              {{ t('config.replay') }}
            </button>
          </div>
        </li>
      </ul>
    </div>

    <PlayerConfigDialog ref="editor" @saved="fetchConfigs" />
  </div>
</template>
