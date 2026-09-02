import { toast } from '@/components/ui/toast'
import { i18n, tt } from '@/i18n'

import type { ApiError } from '@/api/types'

function isApiError(error: unknown): error is ApiError {
  return typeof error === 'object' && error !== null && 'message' in error && 'code' in error
}

function resolveErrorCode(code: string, params?: Record<string, unknown>): string | null {
  const key = `error.${code}`
  if (!i18n.global.te(key)) return null
  return params ? tt(key, params) : tt(key)
}

export function getErrorMessage(error: unknown, fallback?: string): string {
  const resolvedFallback = fallback ?? tt('error.operationFailed')
  if (!isApiError(error)) {
    return resolvedFallback
  }

  const localized = resolveErrorCode(error.code)
  if (localized) return localized
  return error.message ?? resolvedFallback
}

export function getVerifyErrorMessage(result: {
  error_code?: string
  error_params?: Record<string, unknown>
}): string {
  if (result.error_code) {
    const localized = resolveErrorCode(result.error_code, result.error_params)
    if (localized) return localized
  }
  return tt('training.verifyNeedOllama')
}

export function showApiError(error: unknown, fallback?: string): void {
  toast.error(getErrorMessage(error, fallback ?? tt('error.operationFailed')))
}
