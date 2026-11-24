<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useDesktopLifecycle } from '@/stores/useDesktopLifecycle'
import UiDialog from '@/components/ui/Dialog.vue'
import UiButton from '@/components/ui/Button.vue'

const lifecycle = useDesktopLifecycle()
const { t } = useI18n()
const removeGuard = useRouter().beforeEach(() => !lifecycle.locked)
let disposed = false
let disconnect: (() => void) | undefined
onMounted(async () => {
  const cleanup = await lifecycle.connect()
  if (disposed) cleanup()
  else disconnect = cleanup
})
onBeforeUnmount(() => {
  disposed = true
  disconnect?.()
  removeGuard()
})
</script>

<template>
  <UiDialog
    v-if="lifecycle.locked || lifecycle.failure"
    :open="true"
    :title="t(lifecycle.failure ? 'desktopClose.blockedTitle' : 'desktopClose.title')"
    @update:open="!$event && lifecycle.cancel()"
  >
    <p :role="lifecycle.failure ? 'alert' : 'status'" class="text-body text-ink-text-secondary">
      {{
        lifecycle.failure
          ? t(`desktopClose.${lifecycle.failure}`)
          : t(`desktopClose.${lifecycle.phase}`)
      }}
    </p>
    <template #footer>
      <UiButton variant="secondary" @click="lifecycle.cancel()">{{
        t('desktopClose.continue')
      }}</UiButton>
    </template>
  </UiDialog>
</template>
