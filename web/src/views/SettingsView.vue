<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { apiClient } from '@/api/client'
import type { ApiResponse } from '@/api/types'
import { formatBytes } from '@/utils/format'

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
  <div v-loading="loading" class="page-container">
    <h2 class="page-title mb-8">系统设置</h2>

    <!-- System Info -->
    <div v-if="config" class="apple-card mb-6">
      <h3 class="mb-4 text-xs font-semibold uppercase tracking-wider text-[#86868b]">系统信息</h3>
      <div class="grid grid-cols-3 gap-6">
        <div>
          <div class="apple-label">应用名称</div>
          <div class="apple-value mt-1">{{ config.app_name }}</div>
        </div>
        <div>
          <div class="apple-label">版本</div>
          <div class="apple-value mt-1">{{ config.version }}</div>
        </div>
        <div>
          <div class="apple-label">调试模式</div>
          <div class="mt-1">
            <span
              class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium"
              :class="config.debug ? 'bg-[#fff8e6] text-[#ff9f0a]' : 'bg-[#e8f8ee] text-[#34c759]'"
            >
              {{ config.debug ? '开启' : '关闭' }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Provider Status -->
    <div class="apple-card mb-6">
      <h3 class="mb-4 text-xs font-semibold uppercase tracking-wider text-[#86868b]">模型供应商</h3>
      <div class="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
        <div
          v-for="p in providers"
          :key="p.id"
          class="flex items-center gap-3 rounded-xl bg-[#f5f5f7] p-4 transition-all duration-200"
        >
          <span
            class="inline-block h-2 w-2 rounded-full"
            :class="p.configured ? 'bg-[#34c759]' : 'bg-[#aeaeb2]'"
          />
          <div class="flex-1">
            <div class="text-sm font-medium text-[#1d1d1f]">{{ p.name }}</div>
            <div class="text-xs text-[#86868b]">{{ p.description }}</div>
          </div>
          <span
            class="rounded-full px-2.5 py-0.5 text-xs font-medium"
            :class="p.configured ? 'bg-[#e8f8ee] text-[#34c759]' : 'bg-[#e8e8ed] text-[#86868b]'"
          >
            {{ p.configured ? '已配置' : '未配置' }}
          </span>
        </div>
      </div>
    </div>

    <!-- Storage -->
    <div v-if="storage" class="apple-card mb-6">
      <h3 class="mb-4 text-xs font-semibold uppercase tracking-wider text-[#86868b]">存储信息</h3>
      <div class="grid grid-cols-3 gap-6">
        <div>
          <div class="apple-label">数据库大小</div>
          <div class="apple-stat-number mt-1">{{ formatBytes(storage.db_size_bytes) }}</div>
        </div>
        <div>
          <div class="apple-label">数据目录大小</div>
          <div class="apple-stat-number mt-1">{{ formatBytes(storage.data_size_bytes) }}</div>
        </div>
        <div>
          <div class="apple-label">JSONL 文件数</div>
          <div class="apple-stat-number mt-1">{{ storage.jsonl_file_count }}</div>
        </div>
      </div>
    </div>

    <!-- Paths -->
    <div v-if="config" class="apple-card">
      <h3 class="mb-4 text-xs font-semibold uppercase tracking-wider text-[#86868b]">路径配置</h3>
      <div class="space-y-4">
        <div v-for="item in [
          { label: '数据目录', value: config.data_dir },
          { label: '数据库路径', value: config.sqlite_path },
          { label: '配置目录', value: config.config_dir },
          { label: '模型目录', value: config.models_dir },
        ]" :key="item.label">
          <div class="apple-label">{{ item.label }}</div>
          <code class="mt-1 block rounded-lg bg-[#f5f5f7] px-3 py-2 text-xs text-[#424245]">{{ item.value }}</code>
        </div>
      </div>
    </div>
  </div>
</template>
