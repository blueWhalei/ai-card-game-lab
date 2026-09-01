<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Icon } from '@iconify/vue'
import { cn } from '@/lib/cn'
import HeaderToggles from '@/components/common/HeaderToggles.vue'
import { useSidebarCollapse } from '@/composables/useSidebarCollapse'

type NavItem = { path: string; label: string; icon: string }
type NavGroup = { id: string; label: string; items: NavItem[] }

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const mobileOpen = ref(false)
const { isCollapsed, toggleCollapsed } = useSidebarCollapse()

const groups = computed((): NavGroup[] => [
  {
    id: 'lab',
    label: t('nav.groupLab'),
    items: [
      { path: '/', label: t('nav.experiments'), icon: 'lucide:beaker' },
      { path: '/experiment-configs', label: t('nav.playerConfigs'), icon: 'lucide:flask-conical' },
      { path: '/game', label: t('nav.games'), icon: 'lucide:swords' },
    ],
  },
  {
    id: 'pipeline',
    label: t('nav.groupPipeline'),
    items: [
      { path: '/data', label: t('nav.data'), icon: 'lucide:database' },
      { path: '/decisions', label: t('nav.decisions'), icon: 'lucide:crosshair' },
      { path: '/training', label: t('nav.training'), icon: 'lucide:brain' },
    ],
  },
  {
    id: 'tune',
    label: t('nav.groupTune'),
    items: [
      { path: '/prompt', label: t('nav.prompts'), icon: 'lucide:file-text' },
      { path: '/traces', label: t('nav.traces'), icon: 'lucide:activity' },
      { path: '/settings', label: t('nav.settings'), icon: 'lucide:settings' },
    ],
  },
])

const flatItems = computed(() => groups.value.flatMap((g) => g.items))

const activePath = computed(() => {
  const p = route.path
  if (p === '/' || p === '') return '/'
  if (p.startsWith('/experiments/compare')) return '/'
  if (p.startsWith('/experiments/')) return '/'
  const match = flatItems.value
    .filter((i) => i.path !== '/')
    .find((i) => p === i.path || p.startsWith(`${i.path}/`))
  return match?.path ?? p
})

/** Detail workspace owns its own title (experiment name); hide layout chrome. */
const isExperimentDetail = computed(
  () =>
    route.path.startsWith('/experiments/') && !route.path.startsWith('/experiments/compare'),
)

const pageTitle = computed(() => {
  if (route.path.startsWith('/experiments/compare')) return t('nav.experimentCompare')
  if (isExperimentDetail.value) return ''
  return flatItems.value.find((i) => i.path === activePath.value)?.label ?? t('nav.experiments')
})

const pageHint = computed(() => {
  const hints: Record<string, string> = {
    '/': t('nav.hintHome'),
    '/game': t('nav.hintGame'),
    '/experiment-configs': t('nav.hintConfigs'),
    '/decisions': t('nav.hintDecisions'),
    '/data': t('nav.hintData'),
    '/training': t('nav.hintTraining'),
    '/prompt': t('nav.hintPrompt'),
    '/traces': t('nav.hintTraces'),
    '/settings': t('nav.hintSettings'),
  }
  if (route.path.startsWith('/experiments/compare')) {
    return t('nav.hintCompare')
  }
  if (isExperimentDetail.value) {
    return ''
  }
  return hints[activePath.value] ?? ''
})

const showPageChrome = computed(() => Boolean(pageTitle.value))

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
      :class="
        cn(
          'sticky top-0 hidden h-screen shrink-0 flex-col border-r border-ink-border bg-ink-paper-elevated transition-[width] duration-200 ease-out md:flex',
          isCollapsed ? 'w-16' : 'w-64',
        )
      "
    >
      <button
        type="button"
        :class="
          cn(
            'flex items-center py-5 text-left transition-[padding] duration-200',
            isCollapsed ? 'justify-center px-0' : 'gap-2.5 px-4',
          )
        "
        :title="t('app.name')"
        @click="go('/')"
      >
        <span
          class="flex h-9 w-9 shrink-0 items-center justify-center rounded-ink bg-ink-primary text-sm font-semibold text-[var(--ink-primary-fg)]"
        >
          {{ t('app.lab') }}
        </span>
        <span
          :class="
            cn(
              'overflow-hidden text-base font-semibold tracking-tight whitespace-nowrap transition-[opacity,width] duration-200',
              isCollapsed ? 'w-0 opacity-0' : 'opacity-100',
            )
          "
        >
          {{ t('app.name') }}
        </span>
      </button>

      <nav class="flex-1 space-y-4 overflow-y-auto px-2 pb-2">
        <div
          v-for="(group, groupIndex) in groups"
          :key="group.id"
          :class="
            cn(
              'space-y-1',
              groupIndex > 0 && isCollapsed && 'border-t border-ink-border pt-3',
            )
          "
        >
          <p
            v-if="!isCollapsed"
            class="px-3 pb-1 text-sm font-semibold tracking-wide text-ink-text-secondary"
          >
            {{ group.label }}
          </p>
          <RouterLink
            v-for="item in group.items"
            :key="item.path"
            :to="item.path"
            :title="isCollapsed ? item.label : undefined"
            :class="
              cn(
                'relative flex w-full items-center rounded-[6px] py-2.5 text-base transition-colors duration-150',
                isCollapsed ? 'justify-center px-2' : 'gap-2.5 px-3',
                activePath === item.path
                  ? 'bg-ink-primary-muted font-medium text-ink-primary'
                  : 'text-ink-text hover:bg-ink-surface-muted',
              )
            "
          >
            <span
              class="absolute top-1/2 left-0 h-5 w-0.5 -translate-y-1/2 rounded-full bg-ink-primary transition-all duration-200"
              :class="activePath === item.path ? 'opacity-100 scale-y-100' : 'opacity-0 scale-y-50'"
            />
            <Icon :icon="item.icon" class="h-[18px] w-[18px] shrink-0 opacity-80" />
            <span
              :class="
                cn(
                  'overflow-hidden whitespace-nowrap transition-[opacity,width] duration-200',
                  isCollapsed ? 'w-0 opacity-0' : 'opacity-100',
                )
              "
            >
              {{ item.label }}
            </span>
          </RouterLink>
        </div>
      </nav>

      <div class="border-t border-ink-border p-2">
        <button
          type="button"
          :class="
            cn(
              'flex w-full items-center rounded-[6px] py-2 text-ink-text-secondary transition-colors hover:bg-ink-surface-muted hover:text-ink-text',
              isCollapsed ? 'justify-center px-2' : 'gap-2.5 px-3',
            )
          "
          :aria-label="isCollapsed ? t('nav.expandSidebar') : t('nav.collapseSidebar')"
          :title="isCollapsed ? t('nav.expandSidebar') : t('nav.collapseSidebar')"
          @click="toggleCollapsed"
        >
          <Icon
            :icon="isCollapsed ? 'lucide:panel-left-open' : 'lucide:panel-left-close'"
            class="h-[18px] w-[18px] shrink-0"
          />
          <span
            :class="
              cn(
                'overflow-hidden text-sm whitespace-nowrap transition-[opacity,width] duration-200',
                isCollapsed ? 'w-0 opacity-0' : 'opacity-100',
              )
            "
          >
            {{ t('nav.collapseSidebar') }}
          </span>
        </button>
      </div>
    </aside>

    <!-- Mobile top bar -->
    <div class="flex min-w-0 flex-1 flex-col">
      <header
        class="sticky top-0 z-40 flex h-12 items-center gap-3 border-b border-ink-border bg-ink-paper-elevated/90 px-4 backdrop-blur md:hidden"
      >
        <button
          type="button"
          class="rounded-ink p-1.5 text-ink-text hover:bg-ink-surface-muted"
          :aria-label="t('common.menu')"
          @click="mobileOpen = !mobileOpen"
        >
          <Icon :icon="mobileOpen ? 'lucide:x' : 'lucide:menu'" class="h-5 w-5" />
        </button>
        <span class="min-w-0 flex-1 truncate text-base font-semibold">
          {{ pageTitle || t('nav.experimentDetail') }}
        </span>
        <HeaderToggles />
      </header>

      <!-- Mobile drawer -->
      <div
        v-if="mobileOpen"
        class="fixed inset-0 z-50 md:hidden"
      >
        <button
          type="button"
          class="absolute inset-0 bg-black/40"
          :aria-label="t('common.closeMenu')"
          @click="mobileOpen = false"
        />
        <aside class="absolute inset-y-0 left-0 w-72 overflow-y-auto bg-ink-paper-elevated p-3 shadow-[var(--ink-shadow-md)]">
          <p class="mb-4 px-2 text-base font-semibold">{{ t('app.name') }}</p>
          <div v-for="group in groups" :key="group.id" class="mb-4 space-y-1">
            <p class="px-2 text-sm font-semibold tracking-wide text-ink-text-secondary">
              {{ group.label }}
            </p>
            <RouterLink
              v-for="item in group.items"
              :key="item.path"
              :to="item.path"
              :class="
                cn(
                  'flex w-full items-center gap-2.5 rounded-[6px] px-3 py-2.5 text-base',
                  activePath === item.path
                    ? 'bg-ink-primary-muted font-medium text-ink-primary'
                    : 'text-ink-text',
                )
              "
            >
              <Icon :icon="item.icon" class="h-[18px] w-[18px]" />
              {{ item.label }}
            </RouterLink>
          </div>
        </aside>
      </div>

      <header
        v-if="showPageChrome"
        class="hidden border-b border-ink-border px-6 pt-6 pb-4 md:block md:px-8 xl:px-10"
      >
        <div class="flex items-start justify-between gap-4">
          <div class="min-w-0">
            <h1 class="page-title">{{ pageTitle }}</h1>
            <p v-if="pageHint" class="page-subtitle">{{ pageHint }}</p>
          </div>
          <HeaderToggles class="-mt-0.5" />
        </div>
      </header>
      <header
        v-else
        class="hidden justify-end border-b border-ink-border px-6 py-3 md:flex md:px-8 xl:px-10"
      >
        <HeaderToggles />
      </header>

      <main class="flex-1">
        <RouterView v-slot="{ Component, route: viewRoute }">
          <Transition name="ink-page">
            <component :is="Component" :key="viewRoute.path" />
          </Transition>
        </RouterView>
      </main>
    </div>
  </div>
</template>
