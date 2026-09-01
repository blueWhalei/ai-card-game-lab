export function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined' || !window.matchMedia) return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/** Ease-out cubic in [0, 1]. */
export function easeOutCubic(t: number): number {
  const x = Math.min(1, Math.max(0, t))
  return 1 - (1 - x) ** 3
}

export function tweenNumber(from: number, to: number, t: number): number {
  return from + (to - from) * easeOutCubic(t)
}
