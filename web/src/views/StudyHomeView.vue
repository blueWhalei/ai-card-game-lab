<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Icon } from '@iconify/vue'
import { studyApi, type StudySummary } from '@/api/studyApi'
import { showApiError } from '@/utils/error'
import { formatDateTime } from '@/utils/format'
import UiButton from '@/components/ui/Button.vue'
import UiInput from '@/components/ui/Input.vue'
import UiTextarea from '@/components/ui/Textarea.vue'
import UiDialog from '@/components/ui/Dialog.vue'
import UiSkeletonList from '@/components/ui/SkeletonList.vue'

const { t } = useI18n()
const router = useRouter()
const studies = ref<StudySummary[]>([])
const selectedId = ref('')
const search = ref('')
const loading = ref(true)
const failed = ref(false)
const more = ref(false)
const createOpen = ref(false)
const creating = ref(false)
const title = ref('')
const question = ref('')
const filtered = computed(() => {
  const query = search.value.trim().toLocaleLowerCase()
  return studies.value.filter((s) => `${s.title} ${s.question}`.toLocaleLowerCase().includes(query))
})
const selected = computed(
  () => filtered.value.find((s) => s.id === selectedId.value) ?? filtered.value[0],
)
async function load(append = false): Promise<void> {
  loading.value = true
  failed.value = false
  try {
    const { data } = await studyApi.list(append ? studies.value.length : 0)
    studies.value = append ? [...studies.value, ...data] : data
    more.value = data.length === 50
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}
async function create(): Promise<void> {
  if (!title.value.trim() || creating.value) return
  creating.value = true
  try {
    const { data } = await studyApi.create(title.value.trim(), question.value.trim())
    createOpen.value = false
    await router.push(`/research/${data.id}`)
  } catch (error) {
    showApiError(error, t('study.createFailed'))
  } finally {
    creating.value = false
  }
}
onMounted(() => void load())
</script>

<template>
  <div class="page-container space-y-ink-8">
    <header class="flex flex-wrap items-end justify-between gap-ink-4">
      <div>
        <p class="mb-2 text-caption text-ink-primary">CardLab / {{ t('study.home') }}</p>
        <h1 class="text-headline font-semibold">{{ t('study.title') }}</h1>
        <p class="mt-2 text-body text-ink-text-secondary">{{ t('study.subtitle') }}</p>
      </div>
      <div class="flex gap-2">
        <UiButton variant="secondary" @click="router.push('/experiments?create=1')">{{
          t('study.quickRun')
        }}</UiButton
        ><UiButton @click="createOpen = true"
          ><Icon icon="lucide:plus" class="mr-1 h-4 w-4" />{{ t('study.create') }}</UiButton
        >
      </div>
    </header>
    <div v-if="failed" role="alert" class="space-y-3 py-8">
      <p>{{ t('study.loadFailed') }}</p>
      <UiButton variant="secondary" @click="load()">{{ t('common.retry') }}</UiButton>
    </div>
    <UiSkeletonList v-else-if="loading && !studies.length" :rows="5" />
    <section
      v-else-if="!studies.length"
      class="max-w-3xl border-l-2 border-ink-primary py-ink-8 pl-ink-6"
    >
      <Icon icon="lucide:notebook-pen" class="mb-6 h-8 w-8 text-ink-primary" />
      <h2 class="text-title font-medium">{{ t('study.emptyTitle') }}</h2>
      <p class="my-4 max-w-xl text-body leading-relaxed text-ink-text-secondary">
        {{ t('study.emptyHint') }}
      </p>
      <UiButton @click="createOpen = true">{{ t('study.create') }}</UiButton>
    </section>
    <div v-else class="grid gap-ink-8 lg:grid-cols-[minmax(280px,2fr)_minmax(0,3fr)]">
      <section :aria-label="t('study.recent')" class="min-w-0 space-y-4">
        <label class="block"
          ><span class="mb-2 block text-caption text-ink-text-secondary">{{
            t('study.recent')
          }}</span
          ><UiInput
            v-model="search"
            class="w-full"
            :placeholder="t('study.search')"
            :aria-label="t('study.search')"
        /></label>
        <p v-if="!filtered.length" class="py-6 text-body text-ink-text-muted">
          {{ t('study.noMatch') }}
        </p>
        <div class="divide-y divide-ink-border">
          <button
            v-for="study in filtered"
            :key="study.id"
            type="button"
            :aria-pressed="selected?.id === study.id"
            class="w-full border-l-2 px-4 py-5 text-left transition-colors focus-visible:outline-2 focus-visible:outline-ink-primary"
            :class="
              selected?.id === study.id
                ? 'border-ink-primary bg-ink-primary-muted'
                : 'border-transparent hover:bg-ink-surface-muted'
            "
            @click="selectedId = study.id"
          >
            <span class="block break-words text-lead font-medium">{{ study.title }}</span
            ><span class="mt-2 block text-caption text-ink-text-muted"
              >{{ t('study.runs', { n: study.run_count }) }} ·
              {{ formatDateTime(study.last_activity_at) }}</span
            >
          </button>
        </div>
        <UiButton v-if="more" variant="ghost" :loading="loading" @click="load(true)">{{
          t('study.more')
        }}</UiButton>
      </section>
      <section
        v-if="selected"
        class="min-w-0 self-start border-t border-ink-border pt-6 lg:sticky lg:top-8 lg:border-t-0 lg:border-l lg:pl-8"
        aria-live="polite"
      >
        <p class="text-caption text-ink-text-muted">{{ t('study.question') }}</p>
        <h2 class="mt-4 break-words text-headline font-medium">{{ selected.title }}</h2>
        <p
          class="mt-5 whitespace-pre-wrap break-words text-lead leading-relaxed text-ink-text-secondary"
        >
          {{ selected.question || t('study.noQuestion') }}
        </p>
        <UiButton class="mt-8" @click="router.push(`/research/${selected.id}`)"
          >{{ t('study.open') }}<Icon icon="lucide:arrow-right" class="ml-2 h-4 w-4"
        /></UiButton>
      </section>
    </div>
    <footer class="border-t border-ink-border pt-4">
      <RouterLink
        to="/experiments"
        class="text-body text-ink-primary underline-offset-4 hover:underline"
        >{{ t('study.library') }} →</RouterLink
      >
    </footer>
    <UiDialog
      v-model:open="createOpen"
      :title="t('study.create')"
      :description="t('study.createHint')"
    >
      <form class="space-y-4" @submit.prevent="create">
        <label class="block space-y-2"
          ><span class="text-body">{{ t('study.name') }}</span
          ><UiInput
            v-model="title"
            :maxlength="120"
            :placeholder="t('study.namePlaceholder')"
            :disabled="creating"
            required
        /></label>
        <label class="block space-y-2"
          ><span class="text-body">{{ t('study.question') }}</span
          ><UiTextarea
            v-model="question"
            :maxlength="2000"
            :rows="4"
            :placeholder="t('study.questionPlaceholder')"
            :disabled="creating"
        /></label>
        <UiButton type="submit" :loading="creating" :disabled="!title.trim()">{{
          t('study.create')
        }}</UiButton>
      </form>
    </UiDialog>
  </div>
</template>
