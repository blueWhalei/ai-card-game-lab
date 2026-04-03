<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { computed } from 'vue'

const route = useRoute()
const router = useRouter()

const currentPath = computed(() => route.path)

interface NavItem {
  path: string
  label: string
}

const navItems: NavItem[] = [
  { path: '/game', label: '对局' },
  { path: '/ai-players', label: 'AI 角色' },
  { path: '/data', label: '数据' },
  { path: '/training', label: '训练' },
  { path: '/prompt', label: '提示词' },
  { path: '/traces', label: '追踪' },
  { path: '/decisions', label: '决策点' },
  { path: '/settings', label: '设置' },
]

function isActive(path: string): boolean {
  return currentPath.value === path || currentPath.value.startsWith(path + '/')
}
</script>

<template>
  <nav class="sticky top-0 z-50 flex h-12 items-center border-b border-black/[0.06] bg-white/80 px-6 backdrop-blur-xl">
    <div
      class="mr-8 cursor-pointer text-base font-semibold tracking-tight text-[#1d1d1f]"
      @click="router.push('/game')"
    >
      AI Card Game Lab
    </div>
    <div class="flex items-center gap-1">
      <button
        v-for="item in navItems"
        :key="item.path"
        class="rounded-full px-4 py-1.5 text-sm transition-all duration-200"
        :class="isActive(item.path)
          ? 'font-semibold text-[#0071e3]'
          : 'font-normal text-[#424245] hover:text-[#1d1d1f]'"
        @click="router.push(item.path)"
      >
        {{ item.label }}
      </button>
    </div>
  </nav>
</template>
