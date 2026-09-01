import { onUnmounted, ref, watch, type Ref } from 'vue'
import { prefersReducedMotion, tweenNumber } from '@/utils/tweenNumber'

export function useTweenNumber(source: Ref<number>, durationMs = 280): Ref<number> {
  const display = ref(source.value)
  let frame = 0

  function stop(): void {
    if (frame) cancelAnimationFrame(frame)
    frame = 0
  }

  watch(
    source,
    (to) => {
      stop()
      const from = display.value
      if (from === to || prefersReducedMotion() || typeof requestAnimationFrame === 'undefined') {
        display.value = to
        return
      }
      const started = performance.now()
      const tick = (now: number): void => {
        const t = (now - started) / durationMs
        display.value = tweenNumber(from, to, t)
        if (t < 1) {
          frame = requestAnimationFrame(tick)
        } else {
          display.value = to
          frame = 0
        }
      }
      frame = requestAnimationFrame(tick)
    },
    { immediate: true },
  )

  onUnmounted(stop)
  return display
}
