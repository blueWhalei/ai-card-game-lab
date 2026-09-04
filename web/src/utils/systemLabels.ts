import type { PreflightCheck } from '@/api/systemApi'
import { i18n, tt } from '@/i18n'

function hasKey(key: string): boolean {
  return i18n.global.te(key)
}

export function providerName(id: string, fallback?: string): string {
  const key = `settings.providerMeta.${id}.name`
  if (hasKey(key)) return tt(key)
  return fallback || id
}

export function providerDescription(id: string, fallback?: string): string {
  const key = `settings.providerMeta.${id}.description`
  if (hasKey(key)) return tt(key)
  return fallback || ''
}

export function preflightCheckMessage(check: PreflightCheck): string {
  const params = check.params ?? {}
  if (check.id === 'providers_seats' && params.incomplete === true) {
    return tt('preflight.providers_seatsIncomplete')
  }
  const key = `preflight.${check.id}`
  if (hasKey(key)) return tt(key, params)
  return check.message
}
