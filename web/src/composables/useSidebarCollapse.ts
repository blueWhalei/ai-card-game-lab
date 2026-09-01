import { computed, ref } from 'vue'

const STORAGE_KEY = 'ink-sidebar-collapsed'

const collapsed = ref(false)
let initialized = false

function readStored(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

export function initSidebarCollapse(): boolean {
  collapsed.value = readStored()
  initialized = true
  return collapsed.value
}

export function useSidebarCollapse() {
  if (!initialized) {
    initSidebarCollapse()
  }

  const isCollapsed = computed(() => collapsed.value)

  function setCollapsed(value: boolean): void {
    collapsed.value = value
    try {
      localStorage.setItem(STORAGE_KEY, value ? '1' : '0')
    } catch {
      /* ignore quota / private mode */
    }
  }

  function toggleCollapsed(): void {
    setCollapsed(!collapsed.value)
  }

  return { isCollapsed, setCollapsed, toggleCollapsed }
}
