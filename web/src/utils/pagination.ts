export const PAGE_SIZE_OPTIONS = [10, 20, 50] as const
export type PageSizeOption = (typeof PAGE_SIZE_OPTIONS)[number]
export const DEFAULT_PAGE_SIZE: PageSizeOption = 20

export function parsePageSize(
  raw: unknown,
  fallback: PageSizeOption = DEFAULT_PAGE_SIZE,
): PageSizeOption {
  const n = typeof raw === 'string' ? Number.parseInt(raw, 10) : typeof raw === 'number' ? raw : Number.NaN
  return (PAGE_SIZE_OPTIONS as readonly number[]).includes(n) ? (n as PageSizeOption) : fallback
}
