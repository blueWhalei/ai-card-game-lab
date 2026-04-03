import axios from 'axios'
import type { ApiError } from './types'

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
})

apiClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const apiError: ApiError = error.response?.data ?? {
      code: 'NETWORK_ERROR',
      message: error.message,
    }
    return Promise.reject(apiError)
  },
)
