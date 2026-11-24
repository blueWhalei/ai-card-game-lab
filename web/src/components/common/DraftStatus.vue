<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { draftDirty, useDraftStore, type DraftSession } from '@/stores/useDraftStore'
import { downloadJson } from '@/utils/jsonFile'
import UiButton from '@/components/ui/Button.vue'

const props = defineProps<{ session: DraftSession }>()
const store = useDraftStore()
const { t } = useI18n()
const status = computed(() => {
  if (props.session.loading) return 'loading'
  if (props.session.error) return 'error'
  if (props.session.saving) return 'saving'
  if (draftDirty(props.session)) return 'pending'
  return props.session.updatedAt ? 'saved' : 'ready'
})
async function reload(): Promise<void> {
  if (draftDirty(props.session) && !window.confirm(t('draftStorage.reloadConfirm'))) return
  await store.reload(props.session)
}
function discard(): void {
  if (window.confirm(t('draftStorage.discardConfirm'))) store.discard(props.session)
}
</script>

<template>
  <div class="space-y-2 text-caption" aria-live="polite">
    <p
      :role="session.error ? 'alert' : 'status'"
      :class="session.error ? 'text-ink-danger' : 'text-ink-text-secondary'"
    >
      {{ t(`draftStorage.${status}`) }}
    </p>
    <p v-if="session.error" class="text-ink-danger">{{ session.error }}</p>
    <div v-if="session.error" class="flex flex-wrap gap-2">
      <UiButton
        v-if="!session.content || draftDirty(session)"
        size="sm"
        variant="secondary"
        :disabled="session.saving || session.loading"
        @click="session.content ? store.flush(session) : reload()"
        >{{ t('common.retry') }}</UiButton
      >
      <UiButton
        v-if="session.content"
        size="sm"
        variant="ghost"
        @click="downloadJson(`draft-${session.id}.json`, session.content)"
        >{{ t('draftStorage.export') }}</UiButton
      >
      <UiButton
        v-if="session.content"
        size="sm"
        variant="ghost"
        :disabled="session.saving || session.loading"
        @click="reload"
        >{{ t('draftStorage.reload') }}</UiButton
      >
      <UiButton
        v-if="session.content"
        size="sm"
        variant="ghost"
        :disabled="session.saving || session.loading"
        @click="discard"
        >{{ t('draftStorage.discard') }}</UiButton
      >
    </div>
  </div>
</template>
