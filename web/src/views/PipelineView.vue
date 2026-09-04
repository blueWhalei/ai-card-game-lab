<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import ExperimentContextBar from '@/components/common/ExperimentContextBar.vue'
import { cn } from '@/lib/cn'
import {
  PIPELINE_SECTIONS,
  pipelinePath,
  pipelineScopeQuery,
  pipelineSectionOf,
  type PipelineSection,
} from '@/utils/pipeline'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const experimentId = computed(() => {
  const v = route.query.experiment_id
  return typeof v === 'string' && v ? v : undefined
})

const current = computed(() => pipelineSectionOf(route.path))

const sections = computed(() =>
  PIPELINE_SECTIONS.map((id) => ({
    id,
    to: { path: pipelinePath(id), query: pipelineScopeQuery(route.query) },
    label: sectionLabel(id),
  })),
)

function sectionLabel(id: PipelineSection): string {
  const keys: Record<PipelineSection, string> = {
    data: 'nav.data',
    decisions: 'nav.decisions',
    training: 'nav.training',
    traces: 'nav.traces',
  }
  return t(keys[id])
}

function clearScope(): void {
  const query = { ...route.query }
  delete query.experiment_id
  void router.replace({ path: route.path, query })
}
</script>

<template>
  <div>
    <div class="w-full max-w-[1680px] px-6 pt-4 md:px-8 xl:px-10">
      <ExperimentContextBar
        v-if="experimentId"
        :experiment-id="experimentId"
        clearable
        @clear="clearScope"
      />

      <nav
        class="flex flex-wrap gap-ink-6 border-b border-ink-border"
        :aria-label="t('nav.analyze')"
      >
        <RouterLink
          v-for="section in sections"
          :key="section.id"
          :to="section.to"
          :class="
            cn(
              '-mb-px border-b-2 pb-ink-2 text-body transition-colors',
              current === section.id
                ? 'border-ink-primary font-medium text-ink-primary'
                : 'border-transparent text-ink-text-secondary hover:text-ink-text',
            )
          "
        >
          {{ section.label }}
        </RouterLink>
      </nav>
    </div>
    <RouterView />
  </div>
</template>
