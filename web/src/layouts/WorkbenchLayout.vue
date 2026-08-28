<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { cn } from '@/lib/cn'
import ThemeToggle from '@/components/common/ThemeToggle.vue'

type NavItem = { path: string; label: string; icon: string }
type NavGroup = { id: string; label: string; items: NavItem[] }

const route = useRoute()
const router = useRouter()
const mobileOpen = ref(false)

const groups: NavGroup[] = [
  {
    id: 'lab',
    label: '实验室',
    items: [
      { path: '/game', label: '对局', icon: 'lucide:swords' },
      { path: '/experiment-configs', label: '实验配置', icon: 'lucide:flask-conical' },
    ],
  },
  {
    id: 'pipeline',
    label: '管道',
    items: [
      { path: '/', label: '总览', icon: 'lucide:git-branch' },
      { path: '/data', label: '数据', icon: 'lucide:database' },
      { path: '/decisions', label: '决策点', icon: 'lucide:crosshair' },
      { path: '/training', label: '训练', icon: 'lucide:brain' },
    ],
  },
  {
    id: 'tune',
    label: '调参',
    items: [
      { path: '/prompt', label: '提示词', icon: 'lucide:file-text' },
      { path: '/traces', label: '追踪', icon: 'lucide:activity' },
      { path: '/settings', label: '设置', icon: 'lucide:settings' },
    ],
  },
]

const flatItems = groups.flatMap((g) => g.items)

const activePath = computed(() => {
  const p = route.path
  if (p === '/' || p === '') return '/'
  const match = flatItems
    .filter((i) => i.path !== '/')
    .find((i) => p === i.path || p.startsWith(`${i.path}/`))
  return match?.path ?? p
})

const pageTitle = computed(() => {
  return flatItems.find((i) => i.path === activePath.value)?.label ?? '工作台'
})

const pageHint = computed(() => {
  const hints: Record<string, string> = {
    '/': '采集 → 数据 → 训练 → 部署',
    '/game': '批量对局采集行为数据',
    '/experiment-configs': '采样参数配置档；提示词在「提示词」页统一管理',
    '/data': '指标与数据集',
    '/decisions': 'train_usable 与 ChatML 导出',
    '/training': 'SFT 任务与本地模型',
    '/prompt': '提示词版本与 A/B',
    '/traces': '决策可观测性',
    '/settings': '系统路径与状态',
  }
  return hints[activePath.value] ?? ''
})

watch(
  () => route.fullPath,
  () => {
    mobileOpen.value = false
  },
)

function go(path: string): void {
  void router.push(path)
}
</script>

<template>
  <div class="flex min-h-screen bg-ink-paper text-ink-text">
    <!-- Desktop sidebar -->
    <aside
      class="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-ink-border bg-ink-paper-elevated md:flex"
    >
      <button
        type="button"
        class="flex items-center gap-2.5 px-4 py-5 text-left"
        @click="go('/')"
      >
        <span
          class="flex h-9 w-9 items-center justify-center rounded-ink bg-ink-primary text-sm font-semibold text-[var(--ink-primary-fg)]"
        >
          IL
        </span>
        <span class="text-base font-semibold tracking-tight">AI Card Game Lab</span>
      </button>

      <nav class="flex-1 space-y-6 overflow-y-auto px-2 pb-6">
        <div v-for="group in groups" :key="group.id" class="space-y-1">
          <p class="px-3 pb-1 text-sm font-semibold tracking-wider text-ink-text-muted">
            {{ group.label }}
          </p>
          <button
            v-for="item in group.items"
            :key="item.path"
            type="button"
            :class="
              cn(
                'relative flex w-full items-center gap-2.5 rounded-[6px] px-3 py-2.5 text-base transition-colors duration-150',
                activePath === item.path
                  ? 'bg-ink-primary-muted font-medium text-ink-primary'
                  : 'text-ink-text-secondary hover:bg-ink-surface-muted hover:text-ink-text',
              )
            "
            @click="go(item.path)"
          >
            <span
              class="absolute top-1/2 left-0 h-5 w-0.5 -translate-y-1/2 rounded-full bg-ink-primary transition-all duration-200"
              :class="activePath === item.path ? 'opacity-100 scale-y-100' : 'opacity-0 scale-y-50'"
            />
            <Icon :icon="item.icon" class="h-[18px] w-[18px] shrink-0 opacity-80" />
            {{ item.label }}
          </button>
        </div>
      </nav>
    </aside>

    <!-- Mobile top bar -->
    <div class="flex min-w-0 flex-1 flex-col">
      <header
        class="sticky top-0 z-40 flex h-12 items-center gap-3 border-b border-ink-border bg-ink-paper-elevated/90 px-4 backdrop-blur md:hidden"
      >
        <button
          type="button"
          class="rounded-ink p-1.5 text-ink-text hover:bg-ink-surface-muted"
          aria-label="菜单"
          @click="mobileOpen = !mobileOpen"
        >
          <Icon :icon="mobileOpen ? 'lucide:x' : 'lucide:menu'" class="h-5 w-5" />
        </button>
        <span class="min-w-0 flex-1 truncate text-base font-semibold">{{ pageTitle }}</span>
        <ThemeToggle />
      </header>

      <!-- Mobile drawer -->
      <div
        v-if="mobileOpen"
        class="fixed inset-0 z-50 md:hidden"
      >
        <button
          type="button"
          class="absolute inset-0 bg-black/40"
          aria-label="关闭菜单"
          @click="mobileOpen = false"
        />
        <aside class="absolute inset-y-0 left-0 w-72 overflow-y-auto bg-ink-paper-elevated p-3 shadow-[var(--ink-shadow-md)]">
          <p class="mb-4 px-2 text-base font-semibold">AI Card Game Lab</p>
          <div v-for="group in groups" :key="group.id" class="mb-4 space-y-1">
            <p class="px-2 text-sm font-semibold tracking-wider text-ink-text-muted">
              {{ group.label }}
            </p>
            <button
              v-for="item in group.items"
              :key="item.path"
              type="button"
              :class="
                cn(
                  'flex w-full items-center gap-2.5 rounded-[6px] px-3 py-2.5 text-base',
                  activePath === item.path
                    ? 'bg-ink-primary-muted font-medium text-ink-primary'
                    : 'text-ink-text-secondary',
                )
              "
              @click="go(item.path)"
            >
              <Icon :icon="item.icon" class="h-[18px] w-[18px]" />
              {{ item.label }}
            </button>
          </div>
        </aside>
      </div>

      <header class="hidden border-b border-ink-border px-6 pt-6 pb-4 md:block md:px-8 xl:px-10">
        <div class="flex items-start justify-between gap-4">
          <div class="min-w-0">
            <h1 class="page-title">{{ pageTitle }}</h1>
            <p v-if="pageHint" class="page-subtitle">{{ pageHint }}</p>
          </div>
          <ThemeToggle class="-mt-0.5" />
        </div>
      </header>

      <main class="flex-1">
        <RouterView />
      </main>
    </div>
  </div>
</template>
