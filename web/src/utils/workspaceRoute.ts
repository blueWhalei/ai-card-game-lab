import type { RouteLocationNormalizedLoaded, Router } from 'vue-router'

declare module 'vue-router' {
  interface RouteMeta {
    /** Query keys representing a durable research location, never form actions. */
    desktopResume?: readonly string[]
  }
}

export function workspaceRoute(
  router: Router,
  route: Pick<RouteLocationNormalizedLoaded, 'path' | 'query' | 'meta'>,
): string | null {
  const keys = route.meta.desktopResume
  if (!keys) return null
  const query: Record<string, string> = {}
  for (const key of keys) {
    const value = route.query[key]
    if (typeof value === 'string' && value.length <= 512) query[key] = value
  }
  const path = router.resolve({ path: route.path, query }).fullPath
  return path.length <= 4096 ? path : null
}

export function restoredWorkspaceRoute(router: Router, saved: string): string {
  if (
    !saved.startsWith('/') ||
    saved.startsWith('//') ||
    saved.includes('\\') ||
    saved.includes('#') ||
    [...saved].some((char) => char.charCodeAt(0) < 32 || char.charCodeAt(0) === 127)
  ) {
    throw new Error('Invalid workspace location')
  }
  const route = router.resolve(saved)
  if (workspaceRoute(router, route) !== saved) throw new Error('Unsupported workspace location')
  return saved
}
