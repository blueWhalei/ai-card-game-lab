export interface GameProgress {
  phase: string
  round: number | null
  player_id: string | null
}

type Translate = (key: string, values?: Record<string, unknown>) => string

function seatSuffix(
  progress: GameProgress,
  t: Translate,
  playerName: (id: string) => string,
): string {
  if (!progress.player_id) return ''
  return t('gamesTab.progressSeat', { name: playerName(progress.player_id) })
}

export function formatGameProgress(
  progress: GameProgress | null | undefined,
  t: Translate,
  playerName: (id: string) => string,
): string {
  const phase = progress?.phase ?? 'queued'
  if (!progress || phase === 'queued') {
    return t('gamesTab.progressQueued')
  }
  if (phase === 'bidding') {
    return `${t('gamesTab.progressBidding')}${seatSuffix(progress, t, playerName)}`
  }
  const n = progress.round ?? 0
  const base =
    phase === 'endgame'
      ? t('gamesTab.progressEndgame', { n })
      : t('gamesTab.progressPlaying', { n })
  return `${base}${seatSuffix(progress, t, playerName)}`
}
