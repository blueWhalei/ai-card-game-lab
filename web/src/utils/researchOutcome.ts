import type { PrimaryMetric } from '@/api/promptDesignApi'

type Seat = { id: string; name: string }
type Translate = (key: string, params?: Record<string, string>) => string

export function seatLabel(id: string, seats: Seat[] = []): string {
  const index = seats.findIndex((seat) => seat.id === id)
  return index < 0 ? id : `#${index + 1} ${seats[index]!.name || id}`
}

export function metricLabel(t: Translate, metric: PrimaryMetric, seats?: Seat[]): string {
  return metric.kind === 'landlord_win_rate'
    ? t('promptDesign.tableMetric')
    : t('promptDesign.seatMetric', { seat: seatLabel(metric.player_id, seats) })
}
