<script setup lang="ts">
import {
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogOverlay,
  AlertDialogPortal,
  AlertDialogRoot,
  AlertDialogTitle,
} from 'reka-ui'
import Button from './Button.vue'
import { confirmState, finishConfirm } from './confirm'

function onOpenChange(open: boolean): void {
  if (!open) finishConfirm(false)
}
</script>

<template>
  <AlertDialogRoot :open="confirmState.open" @update:open="onOpenChange">
    <AlertDialogPortal>
      <AlertDialogOverlay class="fixed inset-0 z-[60] bg-black/40" />
      <AlertDialogContent
        class="fixed top-1/2 left-1/2 z-[60] w-[min(92vw,400px)] -translate-x-1/2 -translate-y-1/2 rounded-ink-md border border-ink-border bg-ink-surface p-5 shadow-[var(--ink-shadow-md)] focus:outline-none"
      >
        <AlertDialogTitle class="text-lg font-semibold text-ink-text">
          {{ confirmState.title }}
        </AlertDialogTitle>
        <AlertDialogDescription class="mt-2 text-sm text-ink-text-secondary">
          {{ confirmState.message }}
        </AlertDialogDescription>
        <div class="mt-5 flex justify-end gap-2">
          <Button variant="secondary" @click="finishConfirm(false)">
            {{ confirmState.cancelText }}
          </Button>
          <Button
            :variant="confirmState.danger ? 'danger' : 'primary'"
            @click="finishConfirm(true)"
          >
            {{ confirmState.confirmText }}
          </Button>
        </div>
      </AlertDialogContent>
    </AlertDialogPortal>
  </AlertDialogRoot>
</template>
