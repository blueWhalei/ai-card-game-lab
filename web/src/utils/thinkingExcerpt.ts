/** First line of a live thought, short enough to sit on a seat. */
export function thinkingExcerpt(text: string, max = 72): string {
  const oneLine = text.replace(/\s+/g, ' ').trim()
  if (!oneLine) return ''
  if (oneLine.length <= max) return oneLine
  return `${oneLine.slice(0, max).trimEnd()}…`
}
