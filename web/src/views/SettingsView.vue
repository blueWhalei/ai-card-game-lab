<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { apiClient } from '@/api/client'
import type { ApiResponse } from '@/api/types'
import { formatBytes } from '@/utils/format'
import UiSpinner from '@/components/ui/Spinner.vue'
import UiBadge from '@/components/ui/Badge.vue'

interface ProviderInfo {
  id: string
  name: string
  description: string
  configured: boolean
}

interface SystemConfig {
  app_name: string
  version: string
  debug: boolean
  data_dir: string
  sqlite_path: string
  config_dir: string
  models_dir: string
}

interface StorageInfo {
  db_size_bytes: number
  data_size_bytes: number
  jsonl_file_count: number
}

const providers = ref<ProviderInfo[]>([])
const config = ref<SystemConfig | null>(null)
const storage = ref<StorageInfo | null>(null)
const loading = ref(true)

async function fetchAll() {
  loading.value = true
  try {
    const [provRes, cfgRes, stRes] = await Promise.all([
      apiClient.get<never, ApiResponse<ProviderInfo[]>>('/api/v1/system/providers'),
      apiClient.get<never, ApiResponse<SystemConfig>>('/api/v1/system/config'),
      apiClient.get<never, ApiResponse<StorageInfo>>('/api/v1/system/storage'),
    ])
    providers.value = provRes.data
    config.value = cfgRes.data
    storage.value = stRes.data
  } finally {
    loading.value = false
  }
}

onMounted(fetchAll)
</script>
<template>
  <div class="page-container relative min-h-[240px]">
    <UiSpinner v-if="loading" overlay label="加载中…" />

    <!-- System Info -->
    <div v-if="config" class="mb-6 rounded-ink-md border border-ink-border bg-ink-surface p-5">
      <h3 class="mb-4 text-xs font-semibold uppercase tracking-wider text-ink-text-muted">系统信息</h3>
      <div class="grid grid-cols-3 gap-6">
        <div>
          <div class="text-xs text-ink-text-muted">应用名称</div>
          <div class="mt-1 text-sm font-medium text-ink-text">{{ config.app_name }}</div>
        </div>
        <div>
          <div class="text-xs text-ink-text-muted">版本</div>
          <div class="mt-1 text-sm font-medium text-ink-text">{{ config.version }}</div>
        </div>
        <div>
          <div class="text-xs text-ink-text-muted">调试模式</div>
          <div class="mt-1">
            <UiBadge :variant="config.debug ? 'warning' : 'success'">
              {{ config.debug ? '开启' : '关闭' }}
            </UiBadge>
          </div>
        </div>
      </div>
    </div>

    <!-- Provider Status -->
    <div class="mb-6 rounded-ink-md border border-ink-border bg-ink-surface p-5">
      <h3 class="mb-4 text-xs font-semibold uppercase tracking-wider text-ink-text-muted">模型供应商</h3>
      <div class="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
        <div
          v-for="p in providers"
          :key="p.id"
          class="flex items-center gap-3 rounded-ink-md bg-ink-surface-muted p-4"
        >
          <span
            class="inline-block h-2 w-2 rounded-full"
            :class="p.configured ? 'bg-ink-success' : 'bg-ink-text-muted'"
          />
          <div class="flex-1">
            <div class="text-sm font-medium text-ink-text">{{ p.name }}</div>
            <div class="text-xs text-ink-text-muted">{{ p.description }}</div>
          </div>
          <UiBadge :variant="p.configured ? 'success' : 'muted'">
            {{ p.configured ? '已配置' : '未配置' }}
          </UiBadge>
        </div>
      </div>
    </div>

    <!-- Storage -->
    <div v-if="storage" class="mb-6 rounded-ink-md border border-ink-border bg-ink-surface p-5">
      <h3 class="mb-4 text-xs font-semibold uppercase tracking-wider text-ink-text-muted">存储信息</h3>
      <div class="grid grid-cols-3 gap-6">
        <div>
          <div class="text-xs text-ink-text-muted">数据库大小</div>
          <div class="mt-1 text-lg font-semibold text-ink-text">{{ formatBytes(storage.db_size_bytes) }}</div>
        </div>
        <div>
          <div class="text-xs text-ink-text-muted">数据目录大小</div>
          <div class="mt-1 text-lg font-semibold text-ink-text">{{ formatBytes(storage.data_size_bytes) }}</div>
        </div>
        <div>
          <div class="text-xs text-ink-text-muted">JSONL 文件数</div>
          <div class="mt-1 text-lg font-semibold text-ink-text">{{ storage.jsonl_file_count }}</div>
        </div>
      </div>
    </div>

    <!-- Paths -->
    <div v-if="config" class="rounded-ink-md border border-ink-border bg-ink-surface p-5">
      <h3 class="mb-4 text-xs font-semibold uppercase tracking-wider text-ink-text-muted">路径配置</h3>
      <div class="space-y-4">
        <div
          v-for="item in [
            { label: '数据目录', value: config.data_dir },
            { label: '数据库路径', value: config.sqlite_path },
            { label: '配置目录', value: config.config_dir },
            { label: '模型目录', value: config.models_dir },
          ]"
          :key="item.label"
        >
          <div class="text-xs text-ink-text-muted">{{ item.label }}</div>
          <code class="mt-1 block rounded-ink bg-ink-surface-muted px-3 py-2 text-xs text-ink-text-secondary">{{
            item.value
          }}</code>
        </div>
      </div>
    </div>
  </div>
</template>
