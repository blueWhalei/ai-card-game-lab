import { toast } from '@/components/ui/toast'
import { tt } from '@/i18n'

import type { ApiError } from '@/api/types'

const API_ERROR_KEYS = [
  'NETWORK_ERROR',
  'AI_RATE_LIMIT_EXCEEDED',
  'AI_TIMEOUT',
  'AI_PROVIDER_UNAVAILABLE',
  'AI_PROVIDER_ERROR',
] as const

function isApiError(error: unknown): error is ApiError {
  return typeof error === 'object' && error !== null && 'message' in error && 'code' in error
}

export function getErrorMessage(error: unknown, fallback?: string): string {
  const resolvedFallback = fallback ?? tt('error.operationFailed')
  if (!isApiError(error)) {
    return resolvedFallback
  }

  if ((API_ERROR_KEYS as readonly string[]).includes(error.code)) {
    return tt(`error.${error.code}`)
  }
  return error.message ?? resolvedFallback
}

export function showApiError(error: unknown, fallback?: string): void {
  toast.error(getErrorMessage(error, fallback ?? tt('error.operationFailed')))
}
