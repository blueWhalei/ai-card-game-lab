export const CARD_DISPLAY: Record<string, string> = {
  S: '♠',
  H: '♥',
  D: '♦',
  C: '♣',
}

export const RANK_DISPLAY: Record<string, string> = {
  '3': '3',
  '4': '4',
  '5': '5',
  '6': '6',
  '7': '7',
  '8': '8',
  '9': '9',
  T: '10',
  J: 'J',
  Q: 'Q',
  K: 'K',
  A: 'A',
  '2': '2',
  BJ: '小王',
  RJ: '大王',
}

export const SUIT_DISPLAY: Record<string, string> = {
  S: '♠',
  H: '♥',
  D: '♦',
  C: '♣',
}

export const RANK_ORDER = ['3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A', '2', 'BJ', 'RJ']

export function getCardInfo(card: string): { rank: string; suit: string; isJoker: boolean } {
  if (card === 'BJ') {
    return { rank: '小王', suit: '', isJoker: true }
  }
  if (card === 'RJ') {
    return { rank: '大王', suit: '', isJoker: true }
  }
  const suit = card[0] ?? ''
  const rank = card.slice(1)
  return { rank: RANK_DISPLAY[rank] || rank, suit: SUIT_DISPLAY[suit] || '', isJoker: false }
}

export function isRedSuit(card: string): boolean {
  if (card === 'RJ') return true
  if (card === 'BJ') return false
  const suit = card[0] ?? ''
  return suit === 'H' || suit === 'D'
}

export const isRedCard = (card: string): boolean => {
  return card.startsWith('H') || card.startsWith('D') || card === 'RJ'
}

export function displayCard(card: string): string {
  if (card === 'BJ') return '🃏小'
  if (card === 'RJ') return '🃏大'
  const suit = card[0] ?? ''
  const rank = card.slice(1)
  return `${CARD_DISPLAY[suit] ?? ''}${RANK_DISPLAY[rank] ?? rank}`
}

export function formatMs(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`
}

export function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return `${n}`
}
