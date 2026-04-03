<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { showApiError } from '@/utils/error'
import { gameApi } from '@/api/gameApi'
import { aiPlayerApi } from '@/api/aiPlayerApi'
import type { GameItem } from '@/api/gameApi'
import type { AIPlayer } from '@/api/aiPlayerApi'
import { GAME_TYPE_MAP, GAME_STATUS_MAP } from '@/utils/constants'
import EmptyState from '@/components/common/EmptyState.vue'

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
  createForm.value = { game_type: 'doudizhu', player_ids: [], mode: 'realtime', isBatch: false, batchCount: 5 }
  createDialogVisible.value = true
  fetchPlayers()
}

async function handleCreate() {
  if (createForm.value.player_ids.length !== 3) {
    ElMessage.warning('斗地主需要选择 3 个 AI 角色')
    return
  }
  try {
    if (createForm.value.isBatch) {
      await gameApi.batch({
        game_type: createForm.value.game_type,
        player_ids: createForm.value.player_ids,
        count: createForm.value.batchCount,
      })
      ElMessage.success(`已创建 ${createForm.value.batchCount} 局对局`)
      createDialogVisible.value = false
      await fetchGames()
    } else {
      const res = await gameApi.create(createForm.value)
      ElMessage.success('对局创建成功')
      createDialogVisible.value = false
      await fetchGames()
      router.push(`/game/${res.data.id}`)
    }
  } catch (e: unknown) {
    showApiError(e, '创建失败')
  }
}

function goToGame(game: GameItem) {
  router.push(`/game/${game.id}`)
}

function handlePageChange(newPage: number) {
  page.value = newPage
  fetchGames()
}

import { formatDateTime } from '@/utils/format'

onMounted(fetchGames)
</script>

<template>
  <div class="page-container">
    <div class="mb-8 flex items-center justify-between">
      <h2 class="page-title">对局管理</h2>
      <button class="apple-btn" @click="openCreateDialog">创建对局</button>
    </div>

    <div class="apple-card">
      <EmptyState
        v-if="!loading && games.length === 0"
        title="暂无对局"
        description="还没有创建任何对局"
      >
        <template #action>
          <button class="apple-btn" @click="openCreateDialog">创建第一局</button>
        </template>
      </EmptyState>
      <el-table
        v-else
        v-loading="loading"
        :data="games"
        class="w-full"
        @row-click="goToGame"
        style="cursor: pointer"
      >
      <el-table-column prop="id" label="对局 ID" width="240">
        <template #default="{ row }">
          <span class="font-mono text-xs text-blue-600">{{ row.id }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="game_type" label="游戏类型" width="120">
        <template #default="{ row }">
          <el-tag size="small">{{ GAME_TYPE_MAP[row.game_type] || row.game_type }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag
            size="small"
            :type="(GAME_STATUS_MAP[row.status]?.type as any) || 'info'"
          >
            {{ GAME_STATUS_MAP[row.status]?.label || row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="玩家" min-width="200">
        <template #default="{ row }">
          <div class="flex flex-wrap gap-1">
            <el-tag
              v-for="pid in row.player_ids"
              :key="pid"
              size="small"
              type="info"
            >
              {{ pid }}
            </el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="total_rounds" label="总轮次" width="80" align="center">
        <template #default="{ row }">
          {{ row.total_rounds ?? '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="winner_id" label="赢家" width="150">
        <template #default="{ row }">
          <span v-if="row.winner_id" class="font-medium text-green-600">
            {{ row.winner_id }}
          </span>
          <span v-else class="text-gray-400">-</span>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="180">
        <template #default="{ row }">
          {{ formatDateTime(row.created_at) }}
        </template>
      </el-table-column>
    </el-table>
    </div>

    <div v-if="total > pageSize" class="mt-4 flex justify-center">
      <el-pagination
        :current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        @current-change="handlePageChange"
      />
    </div>

    <!-- Create Game Dialog -->
    <el-dialog v-model="createDialogVisible" title="创建对局" width="500px" destroy-on-close>
      <el-form :model="createForm" label-width="100px" label-position="top">
        <el-form-item label="游戏类型">
          <el-select v-model="createForm.game_type" style="width: 100%" disabled>
            <el-option label="斗地主" value="doudizhu" />
          </el-select>
        </el-form-item>

        <el-form-item label="选择 AI 角色（3个）" required>
          <el-select
            v-model="createForm.player_ids"
            multiple
            :multiple-limit="3"
            placeholder="请选择 3 个 AI 角色"
            style="width: 100%"
          >
            <el-option
              v-for="p in players"
              :key="p.id"
              :label="`${p.avatar} ${p.name}`"
              :value="p.id"
            />
          </el-select>
          <div v-if="players.length === 0" class="mt-2 text-xs text-orange-500">
            暂无 AI 角色，请先在「AI 角色」页面创建
          </div>
        </el-form-item>

        <el-form-item label="模式">
          <el-radio-group v-model="createForm.mode">
            <el-radio value="realtime">实时观察</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="批量模式">
          <el-switch v-model="createForm.isBatch" />
        </el-form-item>

        <el-form-item v-if="createForm.isBatch" label="对局数量">
          <el-input-number
            v-model="createForm.batchCount"
            :min="1"
            :max="50"
            :step="1"
          />
          <span class="ml-2 text-xs text-gray-400">最多 50 局</span>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCreate">
          {{ createForm.isBatch ? `批量创建 ${createForm.batchCount} 局` : '创建并进入' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>
