<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { experimentApi } from '@/api/experimentApi'
import UiButton from '@/components/ui/Button.vue'

const props = withDefaults(
  defineProps<{
    experimentId: string
    /** Tab to open on the experiment detail when returning. */
    returnTab?: 'decisions' | 'traces' | 'games' | 'training'
    /** Show a control that clears experiment scope on the current tool page. */
    clearable?: boolean
  }>(),
  {
    returnTab: 'games',
    clearable: false,
  },
)

const emit = defineEmits<{
  clear: []
}>()

const { t } = useI18n()
const router = useRouter()
const name = ref('')

function shortId(id: string): string {
  if (id.length <= 18) return id
  return `${id.slice(0, 8)}…${id.slice(-4)}`
}

async function loadName(id: string): Promise<void> {
  try {
    const res = await experimentApi.get(id)
    name.value = res.data?.name ?? ''
  } catch {
    name.value = ''
  }
}

function goBack(): void {
  const tab = props.returnTab === 'games' ? undefined : props.returnTab
  void router.push({
    path: `/experiments/${props.experimentId}`,
    query: tab ? { tab } : undefined,
  })
}

watch(
  () => props.experimentId,
  (id) => {
    void loadName(id)
  },
)

onMounted(() => {
  void loadName(props.experimentId)
})
</script>

<template>
  <div
    class="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-ink-md border border-ink-border bg-ink-surface-muted/50 px-3 py-2"
  >
    <p class="min-w-0 truncate text-sm text-ink-text-secondary" :title="experimentId">
      {{
        t('experiment.contextBar', {
          name: name.trim() || shortId(experimentId),
        })
      }}
    </p>
    <div class="flex shrink-0 flex-wrap items-center gap-1.5">
      <UiButton
        v-if="clearable"
        variant="ghost"
        size="sm"
        type="button"
        @click="emit('clear')"
      >
        {{ t('filter.clearScope') }}
      </UiButton>
      <UiButton variant="secondary" size="sm" type="button" @click="goBack">
        <Icon icon="lucide:arrow-left" class="mr-1.5 h-3.5 w-3.5" />
        {{ t('experiment.backToExperiment') }}
      </UiButton>
    </div>
  </div>
</template>
