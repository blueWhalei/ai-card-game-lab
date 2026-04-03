<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { showApiError } from '@/utils/error'
import { aiPlayerApi, type AIPlayer, type AIPlayerStats, type CreateAIPlayerRequest, type UpdateAIPlayerRequest } from '@/api/aiPlayerApi'
import { formatDateTime, formatPercentage } from '@/utils/format'

const players = ref<AIPlayer[]>([])
const playerStats = ref<Map<string, AIPlayerStats>>(new Map())
const loading = ref(false)
const dialogVisible = ref(false)
const isEditing = ref(false)

const PROVIDERS = [
  { value: 'openai', label: 'OpenAI', defaultModel: 'gpt-4o-mini' },
  { value: 'deepseek', label: 'DeepSeek', defaultModel: 'deepseek-chat' },
  { value: 'kimi', label: 'Kimi / Moonshot', defaultModel: 'moonshot-v1-8k' },
  { value: 'dashscope', label: 'DashScope（通义千问）', defaultModel: 'qwen-plus' },
  { value: 'zhipu', label: '智谱 AI（GLM）', defaultModel: 'glm-4-flash' },
  { value: 'minimax', label: 'MiniMax', defaultModel: 'MiniMax-Text-01' },
  { value: 'yi', label: '零一万物（Yi）', defaultModel: 'yi-lightning' },
  { value: 'baichuan', label: '百川智能', defaultModel: 'Baichuan4-Air' },
  { value: 'ollama', label: 'Ollama（本地模型）', defaultModel: 'qwen2.5:7b' },
]

function onProviderChange(val: string) {
  const provider = PROVIDERS.find(p => p.value === val)
  if (provider) {
    form.value.model_config_data.model_name = provider.defaultModel
  }
}

const defaultForm = (): CreateAIPlayerRequest => ({
  id: '',
  name: '',
  description: '',
  avatar: '🤖',
  model_config_data: {
    provider: 'openai',
    model_name: 'gpt-4o-mini',
    temperature: 0.7,
    top_p: 0.95,
    max_tokens: 1024,
  },
})

const form = ref<CreateAIPlayerRequest>(defaultForm())

function getPlayerStats(playerId: string): AIPlayerStats | undefined {
  return playerStats.value.get(playerId)
}

async function fetchPlayers() {
  loading.value = true
  try {
    const [playersRes, statsRes] = await Promise.all([
      aiPlayerApi.list(),
      aiPlayerApi.getAllStats(),
    ])
    players.value = playersRes.data
    const statsMap = new Map<string, AIPlayerStats>()
    for (const stat of statsRes.data) {
      statsMap.set(stat.player_id, stat)
    }
    playerStats.value = statsMap
  } catch (e: unknown) {
    showApiError(e, '加载失败')
  } finally {
    loading.value = false
  }
}

function openCreateDialog() {
  isEditing.value = false
  form.value = defaultForm()
  dialogVisible.value = true
}

function openEditDialog(player: AIPlayer) {
  isEditing.value = true
  form.value = {
    id: player.id,
    name: player.name,
    description: player.description,
    avatar: player.avatar,
    model_config_data: { ...player.model_config },
  }
  dialogVisible.value = true
}

async function handleSubmit() {
  try {
    if (isEditing.value) {
      const updateData: UpdateAIPlayerRequest = {
        name: form.value.name,
        description: form.value.description,
        avatar: form.value.avatar,
        model_config_data: form.value.model_config_data,
      }
      await aiPlayerApi.update(form.value.id, updateData)
      ElMessage.success('更新成功')
    } else {
      await aiPlayerApi.create(form.value)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    await fetchPlayers()
  } catch (e: unknown) {
    showApiError(e, '操作失败')
  }
}

async function handleDelete(player: AIPlayer) {
  try {
    await ElMessageBox.confirm(
      `确定删除 AI 角色「${player.name}」吗？`,
      '删除确认',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    )
    await aiPlayerApi.delete(player.id)
    ElMessage.success('已删除')
    await fetchPlayers()
  } catch {
    /* cancelled */
  }
}

onMounted(fetchPlayers)
</script>

<template>
  <div class="page-container">
    <div class="mb-8 flex items-center justify-between">
      <h2 class="page-title">AI 角色管理</h2>
      <button class="apple-btn" @click="openCreateDialog">新增角色</button>
    </div>

    <div v-loading="loading" class="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
      <div
        v-for="player in players"
        :key="player.id"
        class="apple-card-hover"
      >
        <div class="mb-4 flex items-center gap-3">
          <span class="text-3xl">{{ player.avatar }}</span>
          <div class="flex-1">
            <h3 class="font-semibold text-[#1d1d1f]">{{ player.name }}</h3>
            <span class="text-xs text-[#86868b]">{{ player.id }}</span>
          </div>
        </div>
        <p class="mb-4 text-sm text-[#424245]">{{ player.description || '暂无描述' }}</p>
        <div class="mb-4 flex flex-wrap gap-2">
          <span class="rounded-full bg-[#f5f5f7] px-3 py-1 text-xs font-medium text-[#424245]">{{ player.model_config.provider }}</span>
          <span class="rounded-full bg-[#e6f2ff] px-3 py-1 text-xs font-medium text-[#0071e3]">{{ player.model_config.model_name }}</span>
          <span class="rounded-full bg-[#fff8e6] px-3 py-1 text-xs font-medium text-[#ff9f0a]">T={{ player.model_config.temperature }}</span>
        </div>
        
        <!-- Stats Section -->
        <div v-if="getPlayerStats(player.id)" class="mb-4 border-t border-[#f5f5f7] pt-4">
          <div class="grid grid-cols-3 gap-2 text-center">
            <div>
              <div class="text-lg font-semibold text-[#1d1d1f]">{{ getPlayerStats(player.id)?.games_played ?? 0 }}</div>
              <div class="text-xs text-[#86868b]">对局</div>
            </div>
            <div>
              <div class="text-lg font-semibold" :class="(getPlayerStats(player.id)?.win_rate ?? 0) >= 0.5 ? 'text-[#34c759]' : 'text-[#ff3b30]'">
                {{ formatPercentage(getPlayerStats(player.id)?.win_rate) }}
              </div>
              <div class="text-xs text-[#86868b]">胜率</div>
            </div>
            <div>
              <div class="text-lg font-semibold text-[#1d1d1f]">{{ getPlayerStats(player.id)?.wins ?? 0 }}</div>
              <div class="text-xs text-[#86868b]">胜场</div>
            </div>
          </div>
          <div v-if="getPlayerStats(player.id)?.last_game_at" class="mt-2 text-center text-xs text-[#86868b]">
            最近对局: {{ formatDateTime(getPlayerStats(player.id)?.last_game_at) }}
          </div>
        </div>
        
        <div class="flex gap-2">
          <button class="apple-btn-secondary text-xs" @click="openEditDialog(player)">编辑</button>
          <button class="rounded-full px-4 py-1.5 text-xs font-medium text-[#ff3b30] transition-all hover:bg-red-50" @click="handleDelete(player)">删除</button>
        </div>
      </div>

      <div
        v-if="!loading && players.length === 0"
        class="col-span-full flex flex-col items-center justify-center py-20 text-[#86868b]"
      >
        <span class="mb-3 text-5xl">🤖</span>
        <p class="text-sm">暂无 AI 角色，点击上方按钮创建</p>
      </div>
    </div>

    <!-- Create / Edit Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEditing ? '编辑 AI 角色' : '新增 AI 角色'"
      width="560px"
      destroy-on-close
    >
      <el-form :model="form" label-width="100px" label-position="top">
        <el-form-item v-if="!isEditing" label="角色 ID" required>
          <el-input v-model="form.id" placeholder="如 aggressive_tiger" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="如 激进虎" />
        </el-form-item>
        <el-form-item label="头像 Emoji">
          <el-input v-model="form.avatar" placeholder="🤖" style="width: 80px" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="2"
            placeholder="描述 AI 角色的性格和策略特点"
          />
        </el-form-item>

        <div class="mb-4 rounded-lg bg-gray-50 p-4">
          <h4 class="mb-3 font-medium text-gray-700">模型配置</h4>
          <el-form-item label="供应商">
            <el-select v-model="form.model_config_data.provider" style="width: 100%" @change="onProviderChange">
              <el-option
                v-for="p in PROVIDERS"
                :key="p.value"
                :label="p.label"
                :value="p.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="模型名称">
            <el-input v-model="form.model_config_data.model_name" placeholder="gpt-4o-mini" />
          </el-form-item>
          <div class="grid grid-cols-3 gap-4">
            <el-form-item label="Temperature">
              <el-input-number
                v-model="form.model_config_data.temperature"
                :min="0"
                :max="2"
                :step="0.1"
                :precision="1"
                style="width: 100%"
              />
            </el-form-item>
            <el-form-item label="Top P">
              <el-input-number
                v-model="form.model_config_data.top_p"
                :min="0"
                :max="1"
                :step="0.05"
                :precision="2"
                style="width: 100%"
              />
            </el-form-item>
            <el-form-item label="Max Tokens">
              <el-input-number
                v-model="form.model_config_data.max_tokens"
                :min="64"
                :max="4096"
                :step="64"
                style="width: 100%"
              />
            </el-form-item>
          </div>
        </div>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">
          {{ isEditing ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>
