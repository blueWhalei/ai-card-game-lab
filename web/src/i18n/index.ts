import type { WritableComputedRef } from 'vue'
import { createI18n } from 'vue-i18n'
import zhCN from './locales/zh-CN'
import en from './locales/en'

export const LOCALES = ['zh-CN', 'en'] as const
export type AppLocale = (typeof LOCALES)[number]
export type MessageSchema = typeof zhCN

export const LOCALE_STORAGE_KEY = 'ink-locale'

export function isAppLocale(value: string | null | undefined): value is AppLocale {
  return value === 'zh-CN' || value === 'en'
}

export const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  fallbackLocale: 'zh-CN',
  missingWarn: false,
  fallbackWarn: false,
  messages: {
    'zh-CN': zhCN,
    en,
  },
})

export function localeRef(): WritableComputedRef<AppLocale> {
  return i18n.global.locale as unknown as WritableComputedRef<AppLocale>
}

/** Translate outside of setup(); touches locale so Vue computeds re-run. */
export function tt(key: string, named?: Record<string, unknown>): string {
  void localeRef().value
  if (named) {
    return String(i18n.global.t(key, named))
  }
  return String(i18n.global.t(key))
}

export function applyDocumentLocale(locale: AppLocale): void {
  if (typeof document === 'undefined') return
  document.documentElement.lang = locale
}
