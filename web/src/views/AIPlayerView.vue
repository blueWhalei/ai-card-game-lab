<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { toast } from '@/components/ui/toast'
import { confirmDialog } from '@/components/ui/confirm'
import { showApiError } from '@/utils/error'
import {
  aiPlayerApi,
  type AIPlayer,
  type AIPlayerStats,
  type CreateAIPlayerRequest,
  type UpdateAIPlayerRequest,
} from '@/api/aiPlayerApi'
import { formatDateTime, formatPercentage } from '@/utils/format'
import UiButton from '@/components/ui/Button.vue'
import UiDialog from '@/components/ui/Dialog.vue'
import UiInput from '@/components/ui/Input.vue'
import UiTextarea from '@/components/ui/Textarea.vue'
import UiSelect from '@/components/ui/Select.vue'
import UiInputNumber from '@/components/ui/InputNumber.vue'
import UiSpinner from '@/components/ui/Spinner.vue'
import UiBadge from '@/components/ui/Badge.vue'
import UiEmpty from '@/components/ui/Empty.vue'
import { systemApi, type ProviderInfo } from '@/api/systemApi'

const players = ref<AIPlayer[]>([])
const playerStats = ref<Map<string, AIPlayerStats>>(new Map())
const loading = ref(false)
const dialogVisible = ref(false)
const isEditing = ref(false)

const providers = ref<ProviderInfo[]>([])
const providerOptions = computed(() =>
  providers.value.map((p) => ({ label: p.name, value: p.id })),
)

function onProviderChange(val: string) {
  const provider = providers.value.find((p) => p.id === val)
  if (provider?.default_model) {
    form.value.model_config_data.model_name = provider.default_model
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
    const [playersRes, statsRes, providersRes] = await Promise.all([
      aiPlayerApi.list(),
      aiPlayerApi.getAllStats(),
      systemApi.listProviders(),
    ])
    players.value = playersRes.data
    providers.value = providersRes.data
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
      toast.success('更新成功')
    } else {
      await aiPlayerApi.create(form.value)
      toast.success('创建成功')
    }
    dialogVisible.value = false
    await fetchPlayers()
  } catch (e: unknown) {
    showApiError(e, '操作失败')
  }
}

async function handleDelete(player: AIPlayer) {
  const ok = await confirmDialog({
    message: `确定删除 AI 角色「${player.name}」吗？`,
    title: '删除确认',
    confirmText: '删除',
    danger: true,
  })
  if (!ok) return
  try {
    await aiPlayerApi.delete(player.id)
    toast.success('已删除')
    await fetchPlayers()
  } catch (e: unknown) {
    showApiError(e, '删除失败')
  }
}

onMounted(fetchPlayers)
</script>

<template>
  <div class="page-container">
    <div class="mb-5 flex flex-wrap items-center justify-between gap-3">
      <p class="text-base text-ink-text-secondary">配置 provider / model；运行时从数据库读取。</p>
      <UiButton @click="openCreateDialog">新增角色</UiButton>
    </div>

    <div class="relative min-h-[200px]">
      <UiSpinner v-if="loading" overlay label="加载中…" />
      <div class="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
        <div
          v-for="player in players"
          :key="player.id"
          class="rounded-ink-md border border-ink-border bg-ink-surface p-5 transition-shadow hover:shadow-[var(--ink-shadow-md)]"
        >
          <div class="mb-4 flex items-center gap-3">
            <span class="text-3xl">{{ player.avatar }}</span>
            <div class="flex-1">
              <h3 class="font-semibold text-ink-text">{{ player.name }}</h3>
              <span class="text-xs text-ink-text-muted">{{ player.id }}</span>
            </div>
          </div>
          <p class="mb-4 text-sm text-ink-text-secondary">{{ player.description || '暂无描述' }}</p>
          <div class="mb-4 flex flex-wrap gap-2">
            <UiBadge variant="muted">{{ player.model_config.provider }}</UiBadge>
            <UiBadge>{{ player.model_config.model_name }}</UiBadge>
            <UiBadge variant="warning">T={{ player.model_config.temperature }}</UiBadge>
          </div>

          <div v-if="getPlayerStats(player.id)" class="mb-4 border-t border-ink-border pt-4">
            <div class="grid grid-cols-3 gap-2 text-center">
              <div>
                <div class="text-lg font-semibold text-ink-text">
                  {{ getPlayerStats(player.id)?.games_played ?? 0 }}
                </div>
                <div class="text-xs text-ink-text-muted">对局</div>
              </div>
              <div>
                <div
                  class="text-lg font-semibold"
                  :class="
                    (getPlayerStats(player.id)?.win_rate ?? 0) >= 0.5
                      ? 'text-ink-success'
                      : 'text-ink-danger'
                  "
                >
                  {{ formatPercentage(getPlayerStats(player.id)?.win_rate) }}
                </div>
                <div class="text-xs text-ink-text-muted">胜率</div>
              </div>
              <div>
                <div class="text-lg font-semibold text-ink-text">
                  {{ getPlayerStats(player.id)?.wins ?? 0 }}
                </div>
                <div class="text-xs text-ink-text-muted">胜场</div>
              </div>
            </div>
            <div
              v-if="getPlayerStats(player.id)?.last_game_at"
              class="mt-2 text-center text-xs text-ink-text-muted"
            >
              最近对局: {{ formatDateTime(getPlayerStats(player.id)?.last_game_at) }}
            </div>
          </div>

          <div class="flex gap-2">
            <UiButton variant="secondary" size="sm" @click="openEditDialog(player)">编辑</UiButton>
            <UiButton variant="ghost" size="sm" class="text-ink-danger" @click="handleDelete(player)">
              删除
            </UiButton>
          </div>
        </div>

        <div v-if="!loading && players.length === 0" class="col-span-full">
          <UiEmpty title="暂无 AI 角色" description="点击上方按钮创建" />
        </div>
      </div>
    </div>

    <UiDialog
      :open="dialogVisible"
      :title="isEditing ? '编辑 AI 角色' : '新增 AI 角色'"
      class="w-[min(92vw,560px)]"
      @update:open="dialogVisible = $event"
    >
      <div class="space-y-4">
        <div v-if="!isEditing">
          <label class="mb-1.5 block text-sm font-medium text-ink-text">
            角色 ID <span class="text-ink-danger">*</span>
          </label>
          <UiInput v-model="form.id" placeholder="如 aggressive_tiger" class="w-full" />
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-text">
            名称 <span class="text-ink-danger">*</span>
          </label>
          <UiInput v-model="form.name" placeholder="如 激进虎" class="w-full" />
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-text">头像 Emoji</label>
          <UiInput v-model="form.avatar" placeholder="🤖" class="w-20" />
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-text">描述</label>
          <UiTextarea
            v-model="form.description"
            :rows="2"
            placeholder="描述 AI 角色的性格和策略特点"
            class="w-full"
          />
        </div>

        <div class="rounded-ink-md bg-ink-surface-muted p-4">
          <h4 class="mb-3 font-medium text-ink-text">模型配置</h4>
          <div class="space-y-3">
            <div>
              <label class="mb-1.5 block text-sm font-medium text-ink-text">供应商</label>
              <UiSelect
                v-model="form.model_config_data.provider"
                :options="providerOptions"
                class="w-full"
                @update:model-value="onProviderChange"
              />
            </div>
            <div>
              <label class="mb-1.5 block text-sm font-medium text-ink-text">模型名称</label>
              <UiInput
                v-model="form.model_config_data.model_name"
                placeholder="gpt-4o-mini"
                class="w-full"
              />
            </div>
            <div class="grid grid-cols-3 gap-3">
              <div>
                <label class="mb-1.5 block text-sm font-medium text-ink-text">Temperature</label>
                <UiInputNumber
                  :model-value="form.model_config_data.temperature"
                  :min="0"
                  :max="2"
                  :step="0.1"
                  class="w-full"
                  @update:model-value="(v) => (form.model_config_data.temperature = v ?? 0.7)"
                />
              </div>
              <div>
                <label class="mb-1.5 block text-sm font-medium text-ink-text">Top P</label>
                <UiInputNumber
                  :model-value="form.model_config_data.top_p"
                  :min="0"
                  :max="1"
                  :step="0.05"
                  class="w-full"
                  @update:model-value="(v) => (form.model_config_data.top_p = v ?? 0.95)"
                />
              </div>
              <div>
                <label class="mb-1.5 block text-sm font-medium text-ink-text">Max Tokens</label>
                <UiInputNumber
                  :model-value="form.model_config_data.max_tokens"
                  :min="64"
                  :max="4096"
                  :step="64"
                  class="w-full"
                  @update:model-value="(v) => (form.model_config_data.max_tokens = v ?? 1024)"
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <UiButton variant="secondary" @click="dialogVisible = false">取消</UiButton>
        <UiButton @click="handleSubmit">{{ isEditing ? '保存' : '创建' }}</UiButton>
      </template>
    </UiDialog>
  </div>
</template>
