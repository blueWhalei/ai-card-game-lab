<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from '@/components/ui/toast'
import { showApiError } from '@/utils/error'
import { gameApi } from '@/api/gameApi'
import { aiPlayerApi } from '@/api/aiPlayerApi'
import type { GameItem } from '@/api/gameApi'
import type { AIPlayer } from '@/api/aiPlayerApi'
import { GAME_STATUS_MAP } from '@/utils/constants'
import { formatDateTime } from '@/utils/format'
import EmptyState from '@/components/common/EmptyState.vue'
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
import { systemApi, gameTypeLabel } from '@/api/systemApi'

const router = useRouter()
const games = ref<GameItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const players = ref<AIPlayer[]>([])
const createDialogVisible = ref(false)

const createForm = ref({
  game_type: 'doudizhu',
  player_ids: [] as string[],
  mode: 'realtime',
  isBatch: false,
  batchCount: 5,
})

const gameTypeOptions = ref([{ label: '斗地主', value: 'doudizhu' }])
const modeOptions = [{ label: '实时观察', value: 'realtime' }]

type GameRow = GameItem & Record<string, unknown>

const columns: TableColumn<GameRow>[] = [
  { key: 'id', label: '对局 ID', class: 'w-60' },
  { key: 'game_type', label: '游戏类型', class: 'w-28' },
  { key: 'status', label: '状态', class: 'w-24' },
  { key: 'player_ids', label: '玩家' },
  { key: 'total_rounds', label: '总轮次', class: 'w-20' },
  { key: 'winner_id', label: '赢家', class: 'w-36' },
  { key: 'created_at', label: '创建时间', class: 'w-44' },
]

const gameRows = computed(() => games.value as GameRow[])

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
    if (ids.length >= 3) return
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
    showApiError(e, '加载失败')
  } finally {
    loading.value = false
  }
}

async function fetchPlayers() {
  try {
    const res = await aiPlayerApi.list()
    players.value = res.data
  } catch {
    /* ignore */
  }
}

function openCreateDialog() {
  createForm.value = {
    game_type: 'doudizhu',
    player_ids: [],
    mode: 'realtime',
    isBatch: false,
    batchCount: 5,
  }
  createDialogVisible.value = true
  fetchPlayers()
}

async function handleCreate() {
  if (createForm.value.player_ids.length !== 3) {
    toast.warning('斗地主需要选择 3 个 AI 角色')
    return
  }
  try {
    if (createForm.value.isBatch) {
      await gameApi.batch({
        game_type: createForm.value.game_type,
        player_ids: createForm.value.player_ids,
        count: createForm.value.batchCount,
      })
      toast.success(`已创建 ${createForm.value.batchCount} 局对局`)
      createDialogVisible.value = false
      await fetchGames()
    } else {
      const res = await gameApi.create(createForm.value)
      toast.success('对局创建成功')
      createDialogVisible.value = false
      await fetchGames()
      router.push(`/game/${res.data.id}`)
    }
  } catch (e: unknown) {
    showApiError(e, '创建失败')
  }
}

function goToGame(game: GameRow) {
  router.push(`/game/${game.id}`)
}

function handlePageChange(newPage: number) {
  page.value = newPage
  fetchGames()
}

onMounted(async () => {
  try {
    const res = await systemApi.listGameTypes()
    if (res.data.length > 0) {
      gameTypeOptions.value = res.data.map((id) => ({
        label: gameTypeLabel(id),
        value: id,
      }))
      if (!res.data.includes(createForm.value.game_type)) {
        createForm.value.game_type = res.data[0] ?? 'doudizhu'
      }
    }
  } catch {
    /* keep fallback options */
  }
  await fetchGames()
})
</script>

<template>
  <div class="page-container">
    <div class="mb-5 flex flex-wrap items-center justify-between gap-3">
      <p class="text-base text-ink-text-secondary">点开列表进入观战；批量创建用于采集。</p>
      <UiButton @click="openCreateDialog">创建对局</UiButton>
    </div>

    <div class="relative">
      <UiSpinner v-if="loading" overlay label="加载中…" />
      <EmptyState
        v-if="!loading && games.length === 0"
        title="暂无对局"
        description="还没有创建任何对局"
      >
        <template #action>
          <UiButton @click="openCreateDialog">创建第一局</UiButton>
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
            class="font-mono text-sm text-ink-primary hover:underline"
            @click="goToGame(row)"
          >
            {{ row.id }}
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
          <div class="flex flex-wrap gap-1">
            <UiBadge v-for="pid in (row.player_ids as string[])" :key="pid" variant="muted">
              {{ pid }}
            </UiBadge>
          </div>
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

    <div v-if="total > pageSize" class="mt-4">
      <UiPagination
        :page="page"
        :page-size="pageSize"
        :total="total"
        @update:page="handlePageChange"
      />
    </div>

    <UiDialog
      :open="createDialogVisible"
      title="创建对局"
      @update:open="createDialogVisible = $event"
    >
      <div class="space-y-4">
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-text">游戏类型</label>
          <UiSelect
            v-model="createForm.game_type"
            :options="gameTypeOptions"
            disabled
            class="w-full"
          />
        </div>

        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-text">
            选择 AI 角色（3个） <span class="text-ink-danger">*</span>
          </label>
          <div class="flex flex-col gap-2 rounded-ink border border-ink-border p-3">
            <UiCheckbox
              v-for="p in players"
              :key="p.id"
              :model-value="createForm.player_ids.includes(p.id)"
              :disabled="
                !createForm.player_ids.includes(p.id) && createForm.player_ids.length >= 3
              "
              @update:model-value="(v) => togglePlayer(p.id, v)"
            >
              {{ p.avatar }} {{ p.name }}
            </UiCheckbox>
          </div>
          <div v-if="players.length === 0" class="mt-2 text-xs text-ink-accent">
            暂无 AI 角色，请先在「AI 角色」页面创建
          </div>
        </div>

        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-text">模式</label>
          <UiRadioGroup v-model="createForm.mode" name="game-mode" :options="modeOptions" />
        </div>

        <div class="flex items-center gap-3">
          <label class="text-sm font-medium text-ink-text">批量模式</label>
          <UiSwitch v-model="createForm.isBatch" />
        </div>

        <div v-if="createForm.isBatch">
          <label class="mb-1.5 block text-sm font-medium text-ink-text">对局数量</label>
          <div class="flex items-center gap-2">
            <UiInputNumber
              :model-value="createForm.batchCount"
              :min="1"
              :max="50"
              :step="1"
              class="w-28"
              @update:model-value="(v) => (createForm.batchCount = v ?? 1)"
            />
            <span class="text-xs text-ink-text-muted">最多 50 局</span>
          </div>
        </div>
      </div>

      <template #footer>
        <UiButton variant="secondary" @click="createDialogVisible = false">取消</UiButton>
        <UiButton @click="handleCreate">
          {{ createForm.isBatch ? `批量创建 ${createForm.batchCount} 局` : '创建并进入' }}
        </UiButton>
      </template>
    </UiDialog>
  </div>
</template>
