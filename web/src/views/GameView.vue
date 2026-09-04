<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { toast } from '@/components/ui/toast'
import { showApiError } from '@/utils/error'
import { gameApi } from '@/api/gameApi'
import { experimentConfigApi } from '@/api/experimentConfigApi'
import type { GameItem } from '@/api/gameApi'
import type { ExperimentConfig } from '@/api/experimentConfigApi'
import { GAME_STATUS_MAP } from '@/utils/constants'
import { formatDateTime } from '@/utils/format'
import EmptyState from '@/components/common/EmptyState.vue'
import NameChips from '@/components/common/NameChips.vue'
import UiButton from '@/components/ui/Button.vue'
import UiDialog from '@/components/ui/Dialog.vue'
import UiSelect from '@/components/ui/Select.vue'
import UiSwitch from '@/components/ui/Switch.vue'
import UiInputNumber from '@/components/ui/InputNumber.vue'
import UiRadioGroup from '@/components/ui/RadioGroup.vue'
import UiCheckbox from '@/components/ui/Checkbox.vue'
import UiBadge from '@/components/ui/Badge.vue'
import UiPagination from '@/components/ui/Pagination.vue'
import UiSpinner from '@/components/ui/Spinner.vue'
import type { TableColumn } from '@/components/ui/Table.vue'
import UiTable from '@/components/ui/Table.vue'
import { systemApi, gameTypeLabel, type ProviderInfo } from '@/api/systemApi'
import {
  defaultEngineId,
  engineById,
  isValidPlayerSelection,
  maxSelectable,
  playerCountLabel,
  type EngineInfo,
} from '@/utils/engineSlots'
import { DEFAULT_PAGE_SIZE, parsePageSize } from '@/utils/pagination'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const games = ref<GameItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(DEFAULT_PAGE_SIZE)
const loading = ref(false)
const seedingDemo = ref(false)
const configs = ref<ExperimentConfig[]>([])
const providers = ref<ProviderInfo[]>([])
const createDialogVisible = ref(false)

const createForm = ref({
  game_type: '',
  player_ids: [] as string[],
  mode: 'realtime',
  isBatch: false,
  batchCount: 5,
})

const gameTypeIds = ref<string[]>([])
const gameTypeOptions = computed(() =>
  gameTypeIds.value.map((id) => ({ label: gameTypeLabel(id), value: id })),
)
const engines = ref<EngineInfo[]>([])
const currentEngine = computed(() => engineById(engines.value, createForm.value.game_type))
const slotsLabel = computed(() => playerCountLabel(currentEngine.value))
const maxPlayers = computed(() => maxSelectable(currentEngine.value))
const modeOptions = computed(() => [{ label: t('game.realtime'), value: 'realtime' }])

type GameRow = GameItem & Record<string, unknown>

const columns = computed<TableColumn<GameRow>[]>(() => [
  { key: 'id', label: t('game.colId'), class: 'w-44 max-w-[11rem]' },
  { key: 'game_type', label: t('game.colType'), class: 'w-28' },
  { key: 'status', label: t('game.colStatus'), class: 'w-24' },
  { key: 'player_ids', label: t('game.colPlayers') },
  { key: 'total_rounds', label: t('game.colRounds'), class: 'w-20' },
  { key: 'winner_id', label: t('game.colWinner'), class: 'w-36' },
  { key: 'created_at', label: t('game.colCreated'), class: 'hidden w-44 md:table-cell' },
])

const gameRows = computed(() => games.value as GameRow[])

const configNameById = computed(() => {
  const map = new Map<string, string>()
  for (const c of configs.value) map.set(c.id, c.name)
  return map
})

function playerChipNames(ids: string[]): string[] {
  return ids.map((id) => configNameById.value.get(id) ?? id)
}

const unconfiguredProviders = computed(() => {
  const selected = new Set(createForm.value.player_ids)
  const ready = new Set(providers.value.filter((p) => p.configured).map((p) => p.id))
  const missing = new Set<string>()
  for (const config of configs.value) {
    if (!selected.has(config.id)) continue
    const provider = config.model_config.provider
    if (provider && !ready.has(provider)) missing.add(provider)
  }
  return [...missing]
})

function statusVariant(status: string): 'muted' | 'success' | 'warning' | 'danger' | 'default' {
  const type = GAME_STATUS_MAP[status]?.type
  if (type === 'success') return 'success'
  if (type === 'warning') return 'warning'
  if (type === 'danger') return 'danger'
  if (type === 'info') return 'muted'
  return 'default'
}

function togglePlayer(id: string, checked: boolean) {
  const ids = createForm.value.player_ids
  if (checked) {
    if (ids.length >= maxPlayers.value) return
    if (!ids.includes(id)) createForm.value.player_ids = [...ids, id]
  } else {
    createForm.value.player_ids = ids.filter((p) => p !== id)
  }
}

async function fetchGames() {
  loading.value = true
  try {
    const res = await gameApi.list({ page: page.value, page_size: pageSize.value })
    games.value = res.data.items
    total.value = res.data.total
  } catch (e: unknown) {
    showApiError(e, t('game.loadFailed'))
  } finally {
    loading.value = false
  }
}

function configOptionLabel(c: ExperimentConfig): string {
  return `${c.name}（${c.model_config.provider}/${c.model_config.model_name} · T=${c.model_config.temperature}）`
}

async function fetchConfigs() {
  try {
    const [configRes, providerRes] = await Promise.all([
      experimentConfigApi.list(),
      systemApi.listProviders(),
    ])
    configs.value = configRes.data
    providers.value = providerRes.data
  } catch (e: unknown) {
    showApiError(e, t('game.loadConfigsFailed'))
  }
}

function parsePlayersQuery(): string[] {
  const raw = route.query.players
  if (typeof raw !== 'string' || !raw.trim()) return []
  return raw
    .split(',')
    .map((id) => id.trim())
    .filter(Boolean)
}

async function applyPlayersFromQuery(): Promise<void> {
  const ids = parsePlayersQuery()
  if (ids.length === 0) return
  await fetchConfigs()
  createForm.value = {
    game_type: defaultEngineId(engines.value),
    player_ids: ids.slice(0, maxPlayers.value),
    mode: 'realtime',
    isBatch: false,
    batchCount: 5,
  }
  createDialogVisible.value = true
}

function openCreateDialog() {
  createForm.value = {
    game_type: defaultEngineId(engines.value),
    player_ids: [],
    mode: 'realtime',
    isBatch: false,
    batchCount: 5,
  }
  createDialogVisible.value = true
  void fetchConfigs()
}

async function loadDemoGame(): Promise<void> {
  seedingDemo.value = true
  try {
    const res = await systemApi.seedDemo()
    toast.success(res.data.created ? t('game.demoReplayReady') : t('game.demoExists'))
    await fetchGames()
    router.push(`/game/${res.data.game_id}`)
  } catch (e: unknown) {
    showApiError(e, t('experiment.demoFailed'))
  } finally {
    seedingDemo.value = false
  }
}

async function handleCreate() {
  if (!isValidPlayerSelection(createForm.value.player_ids.length, currentEngine.value)) {
    toast.warning(t('game.needPlayers', { n: slotsLabel.value }))
    return
  }
  if (unconfiguredProviders.value.length > 0) {
    toast.warning(
      t('game.missingApiKeys', { names: unconfiguredProviders.value.join('、') }),
    )
    return
  }
  try {
    if (createForm.value.isBatch) {
      await gameApi.batch({
        game_type: createForm.value.game_type,
        player_ids: createForm.value.player_ids,
        count: createForm.value.batchCount,
      })
      toast.success(t('game.createdBatch', { n: createForm.value.batchCount }))
      createDialogVisible.value = false
      await fetchGames()
    } else {
      const res = await gameApi.create(createForm.value)
      await gameApi.start(res.data.id)
      toast.success(t('game.createdOne'))
      createDialogVisible.value = false
      await fetchGames()
      router.push(`/game/${res.data.id}`)
    }
  } catch (e: unknown) {
    showApiError(e, t('game.createFailed'))
  }
}

function goToGame(game: GameRow) {
  router.push(`/game/${game.id}`)
}

function handlePageChange(newPage: number) {
  page.value = newPage
  void fetchGames()
}

function handlePageSizeChange(size: number) {
  pageSize.value = parsePageSize(size)
  page.value = 1
  void fetchGames()
}

onMounted(async () => {
  try {
    const [typesRes, enginesRes] = await Promise.all([
      systemApi.listGameTypes(),
      systemApi.listEngines().catch(() => null),
    ])
    if (typesRes.data.length > 0) {
      gameTypeIds.value = typesRes.data
    }
    engines.value = enginesRes?.data ?? []
    if (engines.value.length > 0) {
      createForm.value.game_type = defaultEngineId(engines.value)
    } else if (gameTypeIds.value.length > 0) {
      createForm.value.game_type = gameTypeIds.value[0] ?? ''
    }
  } catch (e: unknown) {
    showApiError(e, t('game.typesFallback'))
  }
  await Promise.all([fetchGames(), fetchConfigs()])
  await applyPlayersFromQuery()
})

watch(
  () => route.query.players,
  () => {
    void applyPlayersFromQuery()
  },
)
</script>

<template>
  <div class="page-container">
    <div class="mb-5 flex flex-wrap items-center justify-end gap-2">
      <UiButton variant="secondary" :loading="seedingDemo" @click="loadDemoGame">
        {{ t('experiment.loadDemo') }}
      </UiButton>
      <UiButton @click="openCreateDialog">{{ t('game.create') }}</UiButton>
    </div>

    <div class="relative">
      <UiSpinner v-if="loading" overlay :label="t('common.loading')" />
      <EmptyState
        v-if="!loading && games.length === 0"
        :title="t('game.emptyTitle')"
      >
        <template #action>
          <div class="flex flex-wrap gap-2">
            <UiButton @click="openCreateDialog">{{ t('game.createFirst') }}</UiButton>
            <UiButton variant="secondary" :loading="seedingDemo" @click="loadDemoGame">
              {{ t('game.loadDemoNoKey') }}
            </UiButton>
            <UiButton variant="outline" @click="router.push('/experiment-configs')">
              {{ t('game.goCreateConfig') }}
            </UiButton>
          </div>
        </template>
      </EmptyState>
      <UiTable
        v-else-if="!loading || games.length > 0"
        :columns="columns"
        :rows="gameRows"
        row-key="id"
        class="cursor-pointer"
      >
        <template #cell-id="{ row }">
          <button
            type="button"
            class="block max-w-full truncate font-mono text-sm text-ink-primary hover:underline"
            :title="String(row.id)"
            @click="goToGame(row)"
          >
            {{ row.id }}
            <UiBadge v-if="row.id === 'game_demo_doudizhu'" variant="muted" class="ml-1">{{
              t('common.demo')
            }}</UiBadge>
          </button>
        </template>
        <template #cell-game_type="{ row }">
          <UiBadge>{{ gameTypeLabel(String(row.game_type)) }}</UiBadge>
        </template>
        <template #cell-status="{ row }">
          <UiBadge :variant="statusVariant(String(row.status))">
            {{ GAME_STATUS_MAP[String(row.status)]?.label || row.status }}
          </UiBadge>
        </template>
        <template #cell-player_ids="{ row }">
          <NameChips :names="playerChipNames((row.player_ids as string[]) ?? [])" :max="4" />
        </template>
        <template #cell-total_rounds="{ row }">
          {{ row.total_rounds ?? '-' }}
        </template>
        <template #cell-winner_id="{ row }">
          <span v-if="row.winner_id" class="font-medium text-ink-success">{{ row.winner_id }}</span>
          <span v-else class="text-ink-text-muted">-</span>
        </template>
        <template #cell-created_at="{ row }">
          {{ formatDateTime(String(row.created_at)) }}
        </template>
      </UiTable>
    </div>

    <div v-if="total > 0" class="mt-4">
      <UiPagination
        :page="page"
        :page-size="pageSize"
        :total="total"
        @update:page="handlePageChange"
        @update:page-size="handlePageSizeChange"
      />
    </div>

    <UiDialog
      :open="createDialogVisible"
      size="lg"
      :title="t('game.createTitle')"
      @update:open="createDialogVisible = $event"
    >
      <div class="space-y-4">
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-text">{{
            t('game.gameType')
          }}</label>
          <UiSelect
            v-model="createForm.game_type"
            :options="gameTypeOptions"
            disabled
            class="w-full"
          />
        </div>

        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-text">
            {{ t('game.pickPlayers', { selected: createForm.player_ids.length, max: maxPlayers }) }}
            <span class="text-ink-danger">*</span>
          </label>
          <div class="flex flex-col gap-2 rounded-ink border border-ink-border p-3">
            <UiCheckbox
              v-for="c in configs"
              :key="c.id"
              :id="`create-config-${c.id}`"
              :model-value="createForm.player_ids.includes(c.id)"
              :disabled="
                !createForm.player_ids.includes(c.id) && createForm.player_ids.length >= maxPlayers
              "
              @update:model-value="(v) => togglePlayer(c.id, Boolean(v))"
            >
              {{ configOptionLabel(c) }}
            </UiCheckbox>
          </div>
          <div v-if="configs.length === 0" class="mt-2 text-xs text-ink-accent">
            {{ t('game.noConfigsPrefix') }}
            <button
              type="button"
              class="underline"
              @click="createDialogVisible = false; router.push('/experiment-configs')"
            >
              {{ t('game.goCreateConfig') }}
            </button>
          </div>
          <p
            v-else-if="unconfiguredProviders.length > 0"
            class="mt-2 text-xs text-ink-danger"
          >
            {{ t('game.providersNotReady', { names: unconfiguredProviders.join('、') }) }}
          </p>
        </div>

        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-text">{{ t('game.mode') }}</label>
          <UiRadioGroup v-model="createForm.mode" name="game-mode" :options="modeOptions" />
        </div>

        <div class="flex items-center gap-3">
          <label class="text-sm font-medium text-ink-text">{{ t('game.batchMode') }}</label>
          <UiSwitch v-model="createForm.isBatch" />
        </div>

        <div v-if="createForm.isBatch">
          <label class="mb-1.5 block text-sm font-medium text-ink-text">{{
            t('game.gameCount')
          }}</label>
          <div class="flex items-center gap-2">
            <UiInputNumber
              :model-value="createForm.batchCount"
              :min="1"
              :max="50"
              :step="1"
              @update:model-value="(v) => (createForm.batchCount = v ?? 1)"
            />
            <span class="text-xs text-ink-text-muted">{{ t('game.max50') }}</span>
          </div>
        </div>
      </div>

      <template #footer>
        <UiButton variant="secondary" @click="createDialogVisible = false">{{
          t('common.cancel')
        }}</UiButton>
        <UiButton @click="handleCreate">
          {{
            createForm.isBatch
              ? t('game.batchCreate', { n: createForm.batchCount })
              : t('game.createAndEnter')
          }}
        </UiButton>
      </template>
    </UiDialog>
  </div>
</template>
