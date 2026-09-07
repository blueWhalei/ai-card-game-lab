<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'
import { systemApi, type PreflightResult, type ProviderInfo, type SystemConfig } from '@/api/systemApi'
import { apiClient } from '@/api/client'
import type { ApiResponse } from '@/api/types'
import { showApiError } from '@/utils/error'
import { formatBytes } from '@/utils/format'
import { providerDescription, providerName } from '@/utils/systemLabels'
import UiSpinner from '@/components/ui/Spinner.vue'
import UiBadge from '@/components/ui/Badge.vue'
import UiButton from '@/components/ui/Button.vue'
import PreflightBanner from '@/components/common/PreflightBanner.vue'

type StorageInfo = {
  db_size_bytes: number
  data_size_bytes: number
  jsonl_file_count: number
}

const { t } = useI18n()
const providers = ref<ProviderInfo[]>([])
const config = ref<SystemConfig | null>(null)
const storage = ref<StorageInfo | null>(null)
const startup = ref<PreflightResult | null>(null)
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
      systemApi.preflight({ scope: 'all' }),
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
  <div class="page-container relative min-h-[240px] space-y-ink-8">
    <UiSpinner v-if="loading" overlay :label="t('common.loading')" />

    <div
      v-if="loadError && !loading"
      class="flex flex-wrap items-center justify-between gap-ink-3 rounded-ink-md border border-ink-danger/30 bg-ink-surface px-ink-4 py-ink-3"
    >
      <p class="text-body text-ink-text">{{ t('settings.loadError') }}</p>
      <UiButton size="sm" variant="secondary" @click="fetchAll">{{ t('common.retry') }}</UiButton>
    </div>

    <section v-if="config" class="ink-section">
      <h2 class="ink-section-title">{{ t('settings.runtime') }}</h2>
      <p class="mt-ink-2 max-w-2xl text-body text-ink-text-secondary">
        {{ t('settings.runtimeHint', { env: '.env' }) }}
        <RouterLink to="/experiment-configs" class="text-ink-primary hover:underline">{{
          t('nav.playerConfigs')
        }}</RouterLink>
        {{ t('settings.runtimeHintMid') }}
        <RouterLink to="/prompt" class="text-ink-primary hover:underline">{{ t('nav.prompts') }}</RouterLink>
        ·
        <RouterLink to="/guide" class="text-ink-primary hover:underline">{{ t('guide.button') }}</RouterLink>
      </p>
      <div class="mt-ink-4 grid grid-cols-2 gap-ink-4 md:grid-cols-4">
        <div>
          <div class="text-caption text-ink-text-muted">{{ t('settings.app') }}</div>
          <div class="mt-ink-1 text-body font-medium text-ink-text">{{ config.app_name }}</div>
        </div>
        <div>
          <div class="text-caption text-ink-text-muted">{{ t('settings.version') }}</div>
          <div class="mt-ink-1 text-body font-medium text-ink-text">{{ config.version }}</div>
        </div>
        <div>
          <div class="text-caption text-ink-text-muted">{{ t('settings.debug') }}</div>
          <div class="mt-ink-1">
            <UiBadge :variant="config.debug ? 'warning' : 'muted'">
              {{ config.debug ? t('common.on') : t('common.off') }}
            </UiBadge>
          </div>
        </div>
        <div>
          <div class="text-caption text-ink-text-muted">{{ t('settings.maxGames') }}</div>
          <div class="mt-ink-1 text-body font-medium tabular-nums text-ink-text">
            {{ config.max_concurrent_games ?? t('common.dash') }}
          </div>
        </div>
      </div>
      <div
        v-if="startup && startup.checks?.some((c) => !c.ok)"
        class="mt-ink-4 space-y-ink-2 border-t border-ink-border pt-ink-3"
      >
        <p class="text-caption text-ink-text-muted">{{ t('settings.startup') }}</p>
        <PreflightBanner :checks="startup.checks" />
      </div>
    </section>

    <section class="ink-section">
      <h2 class="ink-section-title">
        {{ t('settings.providers') }}
        <span class="ml-ink-2 text-body font-normal text-ink-text-muted">
          {{ t('settings.configuredN', { ready: readyProviders.length, total: providers.length }) }}
        </span>
      </h2>
      <ul class="mt-ink-3 divide-y divide-ink-border">
        <li
          v-for="p in readyProviders"
          :key="p.id"
          class="flex items-center justify-between gap-ink-3 py-ink-3"
        >
          <div class="min-w-0">
            <div class="text-body font-medium text-ink-text">{{ providerName(p.id, p.name) }}</div>
            <div class="truncate text-caption text-ink-text-muted">
              {{ providerDescription(p.id, p.description) }}
            </div>
          </div>
          <UiBadge variant="success">{{ t('settings.configured') }}</UiBadge>
        </li>
      </ul>
      <div v-if="idleProviders.length" class="mt-ink-2">
        <button
          type="button"
          class="text-body text-ink-text-secondary hover:text-ink-text"
          @click="showIdleProviders = !showIdleProviders"
        >
          {{ showIdleProviders ? t('settings.hideIdle') : t('settings.showIdle', { n: idleProviders.length }) }}
        </button>
        <ul v-if="showIdleProviders" class="mt-ink-2 divide-y divide-ink-border">
          <li
            v-for="p in idleProviders"
            :key="p.id"
            class="flex items-center justify-between gap-ink-3 py-ink-2"
          >
            <span class="text-body text-ink-text-muted">{{ providerName(p.id, p.name) }}</span>
            <UiBadge variant="muted">{{ t('settings.unconfigured') }}</UiBadge>
          </li>
        </ul>
      </div>
    </section>

    <section v-if="storage" class="ink-section">
      <div class="flex items-baseline justify-between gap-ink-2">
        <h2 class="ink-section-title">{{ t('settings.disk') }}</h2>
        <RouterLink to="/pipeline/data?tab=storage" class="text-caption text-ink-primary hover:underline">
          {{ t('settings.storageLink') }}
        </RouterLink>
      </div>
      <div class="mt-ink-3 grid grid-cols-3 gap-ink-4">
        <div>
          <div class="ink-kpi-value">
            {{ formatBytes(storage.db_size_bytes) }}
          </div>
          <div class="ink-kpi-label">{{ t('settings.database') }}</div>
        </div>
        <div>
          <div class="ink-kpi-value">
            {{ formatBytes(storage.data_size_bytes) }}
          </div>
          <div class="ink-kpi-label">{{ t('settings.dataDir') }}</div>
        </div>
        <div>
          <div class="ink-kpi-value">
            {{ storage.jsonl_file_count }}
          </div>
          <div class="ink-kpi-label">JSONL</div>
        </div>
      </div>
    </section>

    <section v-if="config" class="ink-section">
      <button
        type="button"
        class="flex w-full items-center justify-between text-left"
        @click="showPaths = !showPaths"
      >
        <h2 class="ink-section-title">{{ t('settings.paths') }}</h2>
        <span class="text-caption text-ink-text-muted">{{ showPaths ? t('common.collapse') : t('common.expand') }}</span>
      </button>
      <div v-if="showPaths" class="mt-ink-4 space-y-ink-3">
        <div v-for="item in pathItems" :key="item.label">
          <div class="text-caption text-ink-text-muted">{{ item.label }}</div>
          <code
            class="mt-ink-1 block overflow-x-auto rounded-ink bg-ink-surface-muted px-ink-3 py-ink-2 text-caption text-ink-text-secondary"
          >
            {{ item.value }}
          </code>
        </div>
      </div>
    </section>
  </div>
</template>
