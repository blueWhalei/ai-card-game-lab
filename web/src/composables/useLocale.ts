import { computed } from 'vue'
import {
  applyDocumentLocale,
  isAppLocale,
  localeRef,
  LOCALE_STORAGE_KEY,
  type AppLocale,
} from '@/i18n'

let initialized = false

function readStored(): AppLocale | null {
  try {
    const v = localStorage.getItem(LOCALE_STORAGE_KEY)
    return isAppLocale(v) ? v : null
  } catch {
    return null
  }
}

export function initLocale(): AppLocale {
  const locale = readStored() ?? 'zh-CN'
  localeRef().value = locale
  applyDocumentLocale(locale)
  initialized = true
  return locale
}

export function useLocale() {
  if (!initialized) {
    initLocale()
  }

  const locale = computed(() => localeRef().value)

  function setLocale(next: AppLocale): void {
    localeRef().value = next
    applyDocumentLocale(next)
    try {
      localStorage.setItem(LOCALE_STORAGE_KEY, next)
    } catch {
      /* ignore quota / private mode */
    }
  }

  function toggleLocale(): void {
    setLocale(locale.value === 'zh-CN' ? 'en' : 'zh-CN')
  }

  return { locale, setLocale, toggleLocale }
}
