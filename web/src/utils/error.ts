import { ElMessage } from 'element-plus'

import type { ApiError } from '@/api/types'

const API_ERROR_MESSAGES: Record<string, string> = {
  NETWORK_ERROR: '网络连接失败，请稍后重试',
  AI_RATE_LIMIT_EXCEEDED: 'AI 服务调用过于频繁，请稍后再试',
  AI_TIMEOUT: 'AI 服务响应超时，请稍后再试',
  AI_PROVIDER_UNAVAILABLE: 'AI 服务暂时不可用，请稍后再试',
  AI_PROVIDER_ERROR: 'AI 服务调用失败，请稍后再试',
}

function isApiError(error: unknown): error is ApiError {
  return typeof error === 'object' && error !== null && 'message' in error && 'code' in error
}

export function getErrorMessage(error: unknown, fallback = '操作失败'): string {
  if (!isApiError(error)) {
    return fallback
  }

  return API_ERROR_MESSAGES[error.code] ?? error.message ?? fallback
}

export function showApiError(error: unknown, fallback = '操作失败'): void {
  ElMessage.error(getErrorMessage(error, fallback))
}
