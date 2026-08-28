import { computed, ref } from 'vue'

export type ThemeMode = 'light' | 'dark'

const STORAGE_KEY = 'ink-theme'

const theme = ref<ThemeMode>('light')
let initialized = false

function getSystemTheme(): ThemeMode {
  if (typeof window === 'undefined') return 'light'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function readStored(): ThemeMode | null {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    return v === 'dark' || v === 'light' ? v : null
  } catch {
    return null
  }
}

export function applyTheme(mode: ThemeMode): void {
  document.documentElement.setAttribute('data-theme', mode)
  // Drop FOUC inline background from index.html so token CSS owns the paint.
  document.documentElement.style.background = ''
}

/** Call before mount (and mirrored by index.html inline script) to avoid FOUC. */
export function initTheme(): ThemeMode {
  const mode = readStored() ?? getSystemTheme()
  theme.value = mode
  applyTheme(mode)
  initialized = true
  return mode
}

export function useTheme() {
  if (!initialized) {
    initTheme()
  }

  const isDark = computed(() => theme.value === 'dark')

  function setTheme(mode: ThemeMode): void {
    theme.value = mode
    try {
      localStorage.setItem(STORAGE_KEY, mode)
    } catch {
      /* ignore quota / private mode */
    }
    applyTheme(mode)
  }

  function toggleTheme(): void {
    setTheme(theme.value === 'dark' ? 'light' : 'dark')
  }

  return { theme, isDark, setTheme, toggleTheme }
}
