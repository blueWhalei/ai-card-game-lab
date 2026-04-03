export interface CardDisplayProps {
  cards: string[]
  selected?: string[]
  showCount?: boolean
  interactive?: boolean
  compact?: boolean
  /** 'default' 60x84 | 'table' 48x67 | 'mini' 36x50 */
  size?: 'default' | 'table' | 'mini'
  playing?: boolean
}

export interface PlayerInfoProps {
  id: string
  name: string
  role: string
  cardsLeft: number
  isCurrentPlayer?: boolean
  isThinking?: boolean
  showRole?: boolean
  showCardsLeft?: boolean
  responseTimeMs?: number
}
