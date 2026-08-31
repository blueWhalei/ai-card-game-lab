import { computed, nextTick, onMounted, ref, watch, type Ref, type StyleValue } from 'vue'
import {
  computeFieldWidth,
  fallbackFontPx,
  fontFromElement,
  measureWidestPx,
} from '@/utils/fieldWidth'

export function useFieldWidth(opts: {
  enabled: () => boolean
  texts: () => readonly string[]
  chromePx: number
  fontSource: Ref<HTMLElement | null>
  className?: () => unknown
}): { style: Ref<StyleValue | undefined> } {
  const widthPx = ref<number | null>(null)

  async function update(): Promise<void> {
    if (!opts.enabled()) {
      widthPx.value = null
      return
    }
    await nextTick()
    const root = opts.fontSource.value
    const typed =
      root?.matches?.('button, input, textarea')
        ? root
        : (root?.querySelector?.('button, input, textarea') ?? root)
    const el = typed instanceof HTMLElement ? typed : root
    const fontPx = fallbackFontPx(opts.className?.())
    const font = fontFromElement(el, fontPx)
    const content = measureWidestPx(opts.texts(), font)
    widthPx.value = computeFieldWidth(content, opts.chromePx)
  }

  watch(
    () => [opts.enabled(), opts.texts().join('\u0001')] as const,
    () => {
      void update()
    },
    { immediate: true },
  )

  onMounted(() => {
    void update()
    if (typeof document !== 'undefined' && document.fonts) {
      void document.fonts.ready.then(() => update())
    }
  })

  return {
    style: computed<StyleValue | undefined>(() => {
      if (widthPx.value == null) return undefined
      return {
        width: `${widthPx.value}px`,
        maxWidth: 'min(24rem, 100%)',
      }
    }),
  }
}
