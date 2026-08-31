import { tt } from '@/i18n'

/** Game type display name mapping */
export function gameTypeLabel(id: string): string {
  const key = `game.type.${id}`
  const translated = tt(key)
  return translated === key ? id : translated
}

/** @deprecated use gameTypeLabel — kept for existing imports */
export const GAME_TYPE_MAP: Record<string, string> = {
  get doudizhu() {
    return tt('game.type.doudizhu')
  },
}

/** Game status variant (not translated). */
export const GAME_STATUS_VARIANT: Record<string, string> = {
  created: 'info',
  running: 'success',
  paused: 'warning',
  finished: 'danger',
  failed: 'danger',
  cancelled: 'info',
  interrupted: 'warning',
}

export function gameStatusLabel(status: string): string {
  const key = `game.status.${status}`
  const translated = tt(key)
  return translated === key ? status : translated
}

/** Game status → { label, type } mapping */
export const GAME_STATUS_MAP: Record<string, { label: string; type: string }> = new Proxy(
  {} as Record<string, { label: string; type: string }>,
  {
    get(_target, status: string) {
      const type = GAME_STATUS_VARIANT[status]
      if (!type && type !== '') return undefined
      return { label: gameStatusLabel(status), type: type ?? '' }
    },
  },
)

export const TRAINING_STATUS_VARIANT: Record<string, string> = {
  pending: 'info',
  exporting: 'warning',
  training: '',
  completed: 'success',
  failed: 'danger',
  cancelled: 'info',
}

export function trainingStatusLabel(status: string): string {
  const key = `training.status.${status}`
  const translated = tt(key)
  return translated === key ? status : translated
}

export const TRAINING_STATUS_MAP: Record<string, { label: string; type: string }> = new Proxy(
  {} as Record<string, { label: string; type: string }>,
  {
    get(_target, status: string) {
      const type = TRAINING_STATUS_VARIANT[status]
      if (type === undefined) return undefined
      return { label: trainingStatusLabel(status), type }
    },
  },
)

export function templateKeyLabel(key: string): string {
  if (key === 'doudizhu_playing') return tt('prompt.keyPlaying')
  if (key === 'doudizhu_bidding') return tt('prompt.keyBidding')
  return key
}

/** Prompt template key labels — must match registry keys used at runtime */
export const TEMPLATE_KEY_LABELS: Record<string, string> = {
  get doudizhu_playing() {
    return tt('prompt.keyPlaying')
  },
  get doudizhu_bidding() {
    return tt('prompt.keyBidding')
  },
}

/** Prompt template key options for select dropdowns */
export function templateKeyOptions(): { value: string; label: string }[] {
  return [
    { value: 'doudizhu_playing', label: tt('prompt.keyPlayingOpt') },
    { value: 'doudizhu_bidding', label: tt('prompt.keyBiddingOpt') },
  ]
}
