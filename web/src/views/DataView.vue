<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import OverviewTab from '@/components/data/tabs/OverviewTab.vue'
import AIPerformanceTab from '@/components/data/tabs/AIPerformanceTab.vue'
import DatasetTab from '@/components/data/tabs/DatasetTab.vue'
import StorageTab from '@/components/data/tabs/StorageTab.vue'
import ArchiveTab from '@/components/data/tabs/ArchiveTab.vue'
import UiTabs from '@/components/ui/Tabs.vue'

type TabType = 'overview' | 'ai-performance' | 'datasets' | 'storage' | 'archive'

const TAB_VALUES: TabType[] = [
  'overview',
  'ai-performance',
  'datasets',
  'storage',
  'archive',
]

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const activeTab = ref<TabType>('overview')

const tabs = computed((): { value: TabType; label: string }[] => [
  { value: 'overview', label: t('data.tabOverview') },
  { value: 'ai-performance', label: t('data.tabAi') },
  { value: 'datasets', label: t('data.tabDatasets') },
  { value: 'storage', label: t('data.tabStorage') },
  { value: 'archive', label: t('data.tabArchive') },
])

function parseTab(raw: unknown): TabType {
  return typeof raw === 'string' && TAB_VALUES.includes(raw as TabType)
    ? (raw as TabType)
    : 'overview'
}

function applyTabFromRoute(): void {
  activeTab.value = parseTab(route.query.tab)
}

function setTab(tab: string): void {
  const next = parseTab(tab)
  activeTab.value = next
  const query = { ...route.query }
  if (next === 'overview') {
    delete query.tab
  } else {
    query.tab = next
  }
  void router.replace({ query })
}

onMounted(applyTabFromRoute)
watch(() => route.query.tab, applyTabFromRoute)
</script>

<template>
  <div class="page-container">
    <UiTabs
      :model-value="activeTab"
      :tabs="tabs"
      class="mb-6"
      @update:model-value="setTab"
    />

    <div>
      <OverviewTab v-if="activeTab === 'overview'" />
      <AIPerformanceTab v-else-if="activeTab === 'ai-performance'" />
      <DatasetTab v-else-if="activeTab === 'datasets'" />
      <StorageTab v-else-if="activeTab === 'storage'" />
      <ArchiveTab v-else-if="activeTab === 'archive'" />
    </div>
  </div>
</template>
