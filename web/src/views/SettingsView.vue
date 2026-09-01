<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'
import { systemApi, type ProviderInfo, type StartupCheck, type SystemConfig } from '@/api/systemApi'
import { apiClient } from '@/api/client'
import type { ApiResponse } from '@/api/types'
import { showApiError } from '@/utils/error'
import { formatBytes } from '@/utils/format'
import UiSpinner from '@/components/ui/Spinner.vue'
import UiBadge from '@/components/ui/Badge.vue'
import UiButton from '@/components/ui/Button.vue'

type StorageInfo = {
  db_size_bytes: number
  data_size_bytes: number
  jsonl_file_count: number
}

const { t } = useI18n()
const providers = ref<ProviderInfo[]>([])
const config = ref<SystemConfig | null>(null)
const storage = ref<StorageInfo | null>(null)
const startup = ref<StartupCheck | null>(null)
const loading = ref(true)
const loadError = ref(false)
const showPaths = ref(false)
const showIdleProviders = ref(false)

const readyProviders = computed(() => providers.value.filter((p) => p.configured))
const idleProviders = computed(() => providers.value.filter((p) => !p.configured))

const pathItems = computed(() => {
  if (!config.value) return []
  return [
    { label: t('settings.dataDir'), value: config.value.data_dir },
    { label: t('settings.database'), value: config.value.sqlite_path },
    { label: t('settings.modelsDir'), value: config.value.models_dir },
  ]
})

async function fetchAll() {
  loading.value = true
  loadError.value = false
  try {
    const [provRes, cfgRes, stRes, startRes] = await Promise.all([
      systemApi.listProviders(),
      systemApi.getConfig(),
      apiClient.get<never, ApiResponse<StorageInfo>>('/api/v1/system/storage'),
      systemApi.getStartupCheck(),
    ])
    providers.value = provRes.data
    config.value = cfgRes.data
    storage.value = stRes.data
    startup.value = startRes.data
  } catch (e: unknown) {
    loadError.value = true
    showApiError(e, t('settings.loadFailed'))
  } finally {
    loading.value = false
  }
}

onMounted(fetchAll)
</script>

<template>
  <div class="page-container relative min-h-[240px] space-y-6">
    <UiSpinner v-if="loading" overlay :label="t('common.loading')" />

    <div
      v-if="loadError && !loading"
      class="flex flex-wrap items-center justify-between gap-3 rounded-ink-md border border-ink-danger/30 bg-ink-surface px-4 py-3"
    >
      <p class="text-sm text-ink-text">{{ t('settings.loadError') }}</p>
      <UiButton size="sm" variant="secondary" @click="fetchAll">{{ t('common.retry') }}</UiButton>
    </div>

    <section v-if="config" class="ink-card">
      <h3 class="mb-1 text-sm font-semibold text-ink-text">{{ t('settings.runtime') }}</h3>
      <p class="mb-4 text-xs text-ink-text-muted">
        {{ t('settings.runtimeHint', { env: '.env' }) }}
        <RouterLink to="/experiment-configs" class="text-ink-primary hover:underline">{{
          t('nav.playerConfigs')
        }}</RouterLink>
        {{ t('settings.runtimeHintMid') }}
        <RouterLink to="/prompt" class="text-ink-primary hover:underline">{{ t('nav.prompts') }}</RouterLink>
      </p>
      <div class="grid grid-cols-2 gap-4 md:grid-cols-4">
        <div>
          <div class="text-xs text-ink-text-muted">{{ t('settings.app') }}</div>
          <div class="mt-1 text-sm font-medium text-ink-text">{{ config.app_name }}</div>
        </div>
        <div>
          <div class="text-xs text-ink-text-muted">{{ t('settings.version') }}</div>
          <div class="mt-1 text-sm font-medium text-ink-text">{{ config.version }}</div>
        </div>
        <div>
          <div class="text-xs text-ink-text-muted">{{ t('settings.debug') }}</div>
          <div class="mt-1">
            <UiBadge :variant="config.debug ? 'warning' : 'muted'">
              {{ config.debug ? t('common.on') : t('common.off') }}
            </UiBadge>
          </div>
        </div>
        <div>
          <div class="text-xs text-ink-text-muted">{{ t('settings.maxGames') }}</div>
          <div class="mt-1 text-sm font-medium tabular-nums text-ink-text">
            {{ config.max_concurrent_games ?? t('common.dash') }}
          </div>
        </div>
      </div>
      <div
        v-if="startup && startup.warnings.length > 0"
        class="mt-4 space-y-1 border-t border-ink-border pt-3"
      >
        <p class="text-xs text-ink-text-muted">{{ t('settings.startup') }}</p>
        <p
          v-for="(warning, i) in startup.warnings"
          :key="i"
          class="text-sm text-ink-text-secondary"
        >
          {{ warning }}
        </p>
      </div>
    </section>

    <section class="ink-card">
      <h3 class="mb-4 text-sm font-semibold text-ink-text">
        {{ t('settings.providers') }}
        <span class="ml-2 font-normal text-ink-text-muted">
          {{ t('settings.configuredN', { ready: readyProviders.length, total: providers.length }) }}
        </span>
      </h3>
      <ul class="divide-y divide-ink-border">
        <li
          v-for="p in readyProviders"
          :key="p.id"
          class="flex items-center justify-between gap-3 py-2.5"
        >
          <div class="min-w-0">
            <div class="text-sm font-medium text-ink-text">{{ p.name }}</div>
            <div class="truncate text-xs text-ink-text-muted">{{ p.description }}</div>
          </div>
          <UiBadge variant="success">{{ t('settings.configured') }}</UiBadge>
        </li>
      </ul>
      <div v-if="idleProviders.length" class="mt-2">
        <button
          type="button"
          class="text-sm text-ink-text-secondary hover:text-ink-text"
          @click="showIdleProviders = !showIdleProviders"
        >
          {{ showIdleProviders ? t('settings.hideIdle') : t('settings.showIdle', { n: idleProviders.length }) }}
        </button>
        <ul v-if="showIdleProviders" class="mt-2 divide-y divide-ink-border">
          <li
            v-for="p in idleProviders"
            :key="p.id"
            class="flex items-center justify-between gap-3 py-2"
          >
            <span class="text-sm text-ink-text-muted">{{ p.name }}</span>
            <UiBadge variant="muted">{{ t('settings.unconfigured') }}</UiBadge>
          </li>
        </ul>
      </div>
    </section>

    <section v-if="storage" class="ink-card">
      <div class="mb-4 flex items-baseline justify-between gap-2">
        <h3 class="text-sm font-semibold text-ink-text">{{ t('settings.disk') }}</h3>
        <RouterLink to="/data?tab=storage" class="text-xs text-ink-primary hover:underline">
          {{ t('settings.storageLink') }}
        </RouterLink>
      </div>
      <div class="grid grid-cols-3 gap-4">
        <div>
          <div class="text-lg font-semibold tabular-nums text-ink-text">
            {{ formatBytes(storage.db_size_bytes) }}
          </div>
          <div class="text-xs text-ink-text-muted">{{ t('settings.database') }}</div>
        </div>
        <div>
          <div class="text-lg font-semibold tabular-nums text-ink-text">
            {{ formatBytes(storage.data_size_bytes) }}
          </div>
          <div class="text-xs text-ink-text-muted">{{ t('settings.dataDir') }}</div>
        </div>
        <div>
          <div class="text-lg font-semibold tabular-nums text-ink-text">
            {{ storage.jsonl_file_count }}
          </div>
          <div class="text-xs text-ink-text-muted">JSONL</div>
        </div>
      </div>
    </section>

    <section v-if="config" class="ink-card">
      <button
        type="button"
        class="flex w-full items-center justify-between text-left"
        @click="showPaths = !showPaths"
      >
        <h3 class="text-sm font-semibold text-ink-text">{{ t('settings.paths') }}</h3>
        <span class="text-xs text-ink-text-muted">{{ showPaths ? t('common.collapse') : t('common.expand') }}</span>
      </button>
      <div v-if="showPaths" class="mt-4 space-y-3">
        <div v-for="item in pathItems" :key="item.label">
          <div class="text-xs text-ink-text-muted">{{ item.label }}</div>
          <code
            class="mt-1 block overflow-x-auto rounded-ink bg-ink-surface-muted px-3 py-2 text-xs text-ink-text-secondary"
          >
            {{ item.value }}
          </code>
        </div>
      </div>
    </section>
  </div>
</template>
