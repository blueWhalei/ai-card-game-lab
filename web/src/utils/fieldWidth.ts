/** Compact field sizing for selects (longest label) and inputs (placeholder). */

export const FIELD_MIN_PX = 72
export const FIELD_MAX_PX = 384

/** Trigger padding-x + chevron + gap + border + slack. */
export const SELECT_CHROME_PX = 52

/** Input padding-x + border + slack. */
export const INPUT_CHROME_PX = 28

/** Extra room for native number spinners. */
export const NUMBER_EXTRA_PX = 22

const EXPLICIT_WIDTH =
  /(?:^|\s)(?:w-full|min-w-full|flex-1|flex-auto|w-\d+|w-\[[^\]]+\])(?:\s|$)/

export function classNameToString(className: unknown): string {
  if (typeof className === 'string') return className
  if (Array.isArray(className)) return className.filter((x) => typeof x === 'string').join(' ')
  return ''
}

/** Caller already asked for a stretch or fixed Tailwind width — do not auto-size. */
export function hasExplicitWidth(className: unknown): boolean {
  return EXPLICIT_WIDTH.test(classNameToString(className))
}

export function computeFieldWidth(contentPx: number, chromePx: number): number {
  const raw = Math.ceil(Math.max(0, contentPx)) + chromePx
  return Math.min(FIELD_MAX_PX, Math.max(FIELD_MIN_PX, raw))
}

/** Relative width: CJK ≈ 1em, ASCII ≈ 0.55em. Used when canvas is unavailable. */
export function estimateEmWidth(text: string): number {
  let w = 0
  for (const ch of text) {
    const code = ch.codePointAt(0) ?? 0
    w += code <= 0x7f ? 0.55 : 1
  }
  return w
}

export function widestText(texts: readonly string[]): string {
  let best = ''
  let bestW = -1
  for (const text of texts) {
    if (!text) continue
    const w = estimateEmWidth(text)
    if (w > bestW) {
      bestW = w
      best = text
    }
  }
  return best
}

let measureCtx: CanvasRenderingContext2D | null = null

export function measureTextPx(text: string, font: string): number {
  if (!text) return 0
  if (typeof document === 'undefined') {
    return estimateEmWidth(text) * 16
  }
  if (!measureCtx) {
    measureCtx = document.createElement('canvas').getContext('2d')
  }
  if (!measureCtx) {
    return estimateEmWidth(text) * 16
  }
  measureCtx.font = font
  return measureCtx.measureText(text).width
}

export function fontFromElement(el: HTMLElement | null, fallbackPx = 16): string {
  if (el && typeof getComputedStyle === 'function') {
    const font = getComputedStyle(el).font
    if (font && font !== 'inherit') return font
  }
  return `400 ${fallbackPx}px "IBM Plex Sans", "Noto Sans SC Variable", sans-serif`
}

export function fallbackFontPx(className: unknown): number {
  const s = classNameToString(className)
  if (/\btext-xs\b/.test(s)) return 12
  if (/\btext-sm\b/.test(s)) return 14
  return 16
}

export function measureWidestPx(texts: readonly string[], font: string): number {
  let max = 0
  for (const text of texts) {
    if (!text) continue
    const w = measureTextPx(text, font)
    if (w > max) max = w
  }
  return max
}
