import { apiClient } from './client'
import type { ApiResponse } from './types'

export interface ArchiveStats {
  total_games: number
  total_rounds: number
  total_traces: number
  total_decisions: number
  oldest_game: string | null
  archive_files: number
  archive_size_bytes: number
}

export interface ArchiveFile {
  filename: string
  size_bytes: number
  created_at: string
  games_count: number
}

export interface ArchiveRequest {
  days_old: number
  game_type?: string
  dry_run: boolean
}

export interface ArchiveResult {
  archived_games: number
  archived_rounds: number
  archived_traces: number
  archived_decisions: number
  archive_file: string | null
  freed_bytes: number
}

export interface CleanupRequest {
  days_old: number
  game_type?: string
  dry_run: boolean
}

export interface CleanupResult {
  deleted_games: number
  deleted_rounds: number
  deleted_traces: number
  deleted_decisions: number
  deleted_jsonl_files: number
  freed_bytes: number
}

export async function getArchiveStats(): Promise<ArchiveStats> {
  const res = await apiClient.get<never, ApiResponse<ArchiveStats>>('/api/v1/system/archive/stats')
  return res.data
}

export async function listArchives(): Promise<ArchiveFile[]> {
  const res = await apiClient.get<never, ApiResponse<ArchiveFile[]>>('/api/v1/system/archive/list')
  return res.data
}

export async function archiveOldGames(request: ArchiveRequest): Promise<ArchiveResult> {
  const res = await apiClient.post<never, ApiResponse<ArchiveResult>>(
    '/api/v1/system/archive',
    request,
  )
  return res.data
}

export async function deleteArchive(filename: string): Promise<void> {
  await apiClient.delete(`/api/v1/system/archive/${filename}`)
}

export async function cleanupOldData(request: CleanupRequest): Promise<CleanupResult> {
  const res = await apiClient.post<never, ApiResponse<CleanupResult>>(
    '/api/v1/system/cleanup',
    request,
  )
  return res.data
}
