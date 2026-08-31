/** Merge id lists in first-seen order, skipping blanks and duplicates. */
export function mergeUniqueIds(
  ...groups: Array<Iterable<string | null | undefined>>
): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  for (const group of groups) {
    for (const id of group) {
      if (!id || seen.has(id)) continue
      seen.add(id)
      out.push(id)
    }
  }
  return out
}
