<script setup lang="ts">
import { ref } from 'vue'
import OverviewTab from '@/components/data/tabs/OverviewTab.vue'
import AIPerformanceTab from '@/components/data/tabs/AIPerformanceTab.vue'
import DatasetTab from '@/components/data/tabs/DatasetTab.vue'
import StorageTab from '@/components/data/tabs/StorageTab.vue'
import ArchiveTab from '@/components/data/tabs/ArchiveTab.vue'

type TabType = 'overview' | 'ai-performance' | 'datasets' | 'storage' | 'archive'

const activeTab = ref<TabType>('overview')

const tabs: { key: TabType; label: string }[] = [
  { key: 'overview', label: '总览' },
  { key: 'ai-performance', label: 'AI 性能' },
  { key: 'datasets', label: '数据集' },
  { key: 'storage', label: '存储管理' },
  { key: 'archive', label: '归档清理' },
]
</script>

<template>
  <div class="page-container">
    <h2 class="page-title mb-6">数据看板</h2>

    <!-- Tab Bar -->
    <div class="mb-6 flex border-b border-[#d2d2d7]">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="relative px-4 py-3 text-sm font-medium transition-colors"
        :class="activeTab === tab.key ? 'text-[#0071e3]' : 'text-[#86868b] hover:text-[#1d1d1f]'"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
        <span
          v-if="activeTab === tab.key"
          class="absolute bottom-0 left-0 right-0 h-0.5 bg-[#0071e3]"
        />
      </button>
    </div>

    <!-- Tab Content -->
    <div>
      <OverviewTab v-if="activeTab === 'overview'" />
      <AIPerformanceTab v-else-if="activeTab === 'ai-performance'" />
      <DatasetTab v-else-if="activeTab === 'datasets'" />
      <StorageTab v-else-if="activeTab === 'storage'" />
      <ArchiveTab v-else-if="activeTab === 'archive'" />
    </div>
  </div>
</template>
