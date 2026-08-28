<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { dataApi } from '@/api/dataApi'
import { trainingApi } from '@/api/trainingApi'
import { decisionApi } from '@/api/decision'
import UiButton from '@/components/ui/Button.vue'
import UiBadge from '@/components/ui/Badge.vue'
import { showApiError } from '@/utils/error'
import { cn } from '@/lib/cn'

type StageStatus = 'idle' | 'ready' | 'done' | 'attention'

type Stage = {
  id: string
  title: string
  blurb: string
  status: StageStatus
  meta: string
  ctaLabel: string
  ctaPath: string
}

const router = useRouter()
const loading = ref(true)
const stages = ref<Stage[]>([])

const statusLabel: Record<StageStatus, string> = {
  idle: '待开始',
  ready: '可进行',
  done: '已就绪',
  attention: '需关注',
}

const statusVariant: Record<StageStatus, 'muted' | 'accent' | 'success' | 'warning'> = {
  idle: 'muted',
  ready: 'accent',
  done: 'success',
  attention: 'warning',
}

const nextCta = computed(() => {
  const order = stages.value
  const attention = order.find((s) => s.status === 'attention' || s.status === 'ready')
  return attention ?? order[0]
})

async function load(): Promise<void> {
  loading.value = true
  try {
    const [statsRes, tasksRes, modelsRes, decisionListRes] = await Promise.all([
      dataApi.stats(),
      trainingApi.listTasks({ page: 1, page_size: 5 }),
      trainingApi.listModels(),
      decisionApi.list({ train_usable: true, limit: 1 }).catch(() => null),
    ])

    const stats = statsRes.data
    const tasks = tasksRes.data.items
    const models = modelsRes.data
    const games = stats.total_games ?? 0
    const hasUsable = Array.isArray(decisionListRes?.data) && decisionListRes.data.length > 0
    const running = tasks.some((t: { status: string }) =>
      ['pending', 'exporting', 'training'].includes(t.status),
    )
    const completed =
      tasks.some((t: { status: string }) => t.status === 'completed') || models.length > 0

    stages.value = [
      {
        id: 'collect',
        title: '采集',
        blurb: 'AI 对局产生行为轨迹',
        status: games > 0 ? 'done' : 'ready',
        meta: games > 0 ? `${games} 局` : '尚无对局',
        ctaLabel: '去对局',
        ctaPath: '/game',
      },
      {
        id: 'data',
        title: '数据',
        blurb: '决策点清洗与可训练筛选',
        status: hasUsable ? 'done' : games > 0 ? 'ready' : 'idle',
        meta: hasUsable ? '已有 train_usable 决策' : '导出 ChatML 前先筛 train_usable',
        ctaLabel: '决策点',
        ctaPath: '/decisions',
      },
      {
        id: 'train',
        title: '训练',
        blurb: 'SFT / LoRA 或 Mock 演练',
        status: running ? 'attention' : completed ? 'done' : hasUsable ? 'ready' : 'idle',
        meta: running ? '任务进行中' : completed ? `${models.length} 个模型` : '等待数据集',
        ctaLabel: '训练台',
        ctaPath: '/training',
      },
      {
        id: 'deploy',
        title: '部署',
        blurb: 'GGUF / Ollama 验证闭环',
        status: models.length > 0 ? 'ready' : 'idle',
        meta: models.length > 0 ? '可导出与验证' : '完成训练后可用',
        ctaLabel: '查看模型',
        ctaPath: '/training',
      },
    ]
  } catch (e) {
    showApiError(e, '加载管道状态失败')
    stages.value = [
      {
        id: 'collect',
        title: '采集',
        blurb: 'AI 对局产生行为轨迹',
        status: 'ready',
        meta: '从对局开始',
        ctaLabel: '去对局',
        ctaPath: '/game',
      },
      {
        id: 'data',
        title: '数据',
        blurb: '决策点清洗与可训练筛选',
        status: 'idle',
        meta: '—',
        ctaLabel: '决策点',
        ctaPath: '/decisions',
      },
      {
        id: 'train',
        title: '训练',
        blurb: 'SFT / LoRA 或 Mock 演练',
        status: 'idle',
        meta: '—',
        ctaLabel: '训练台',
        ctaPath: '/training',
      },
      {
        id: 'deploy',
        title: '部署',
        blurb: 'GGUF / Ollama 验证闭环',
        status: 'idle',
        meta: '—',
        ctaLabel: '查看模型',
        ctaPath: '/training',
      },
    ]
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="page-container space-y-8">
    <section class="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div class="max-w-3xl">
        <p class="text-base text-ink-text-muted">养得起自己的 AI 牌手</p>
        <p class="mt-1 text-base leading-relaxed text-ink-text-secondary">
          独立开发者工具链：大模型采集 → 清洗 → SFT → 本地部署。先跑通管道，再追求牌力。
        </p>
      </div>
      <UiButton v-if="nextCta" size="lg" @click="router.push(nextCta.ctaPath)">
        下一步：{{ nextCta.ctaLabel }}
        <Icon icon="lucide:arrow-right" class="h-4 w-4" />
      </UiButton>
    </section>

    <section class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <article
        v-for="(stage, i) in stages"
        :key="stage.id"
        :class="
          cn(
            'rounded-ink-md border border-ink-border bg-ink-surface p-5 shadow-[var(--ink-shadow)] transition-all duration-500',
            stage.status === 'done' && 'border-ink-success/30',
            stage.status === 'attention' && 'border-ink-accent/40',
            loading && 'opacity-60',
          )
        "
        :style="{ transitionDelay: `${i * 60}ms` }"
      >
        <div class="flex items-center justify-between gap-2">
          <h2 class="text-base font-semibold text-ink-text">{{ stage.title }}</h2>
          <UiBadge :variant="statusVariant[stage.status]">{{ statusLabel[stage.status] }}</UiBadge>
        </div>
        <p class="mt-2 text-base leading-relaxed text-ink-text-secondary">{{ stage.blurb }}</p>
        <p class="mt-3 text-sm text-ink-text-muted">{{ stage.meta }}</p>
        <button
          type="button"
          class="mt-4 text-base font-medium text-ink-primary hover:underline"
          @click="router.push(stage.ctaPath)"
        >
          {{ stage.ctaLabel }} →
        </button>
      </article>
    </section>

    <section class="rounded-ink-md border border-dashed border-ink-border bg-ink-paper-elevated/60 p-5">
      <h2 class="text-base font-semibold text-ink-text">一小时闭环</h2>
      <p class="mt-1 text-base leading-relaxed text-ink-text-secondary">
        使用仓库脚本跑通采集 → 导出 → 训练 → 验证。详见
        <code class="rounded bg-ink-surface-muted px-1.5 py-0.5 text-sm">docs/E2E_PIPELINE.md</code>
        与
        <code class="rounded bg-ink-surface-muted px-1.5 py-0.5 text-sm">scripts/e2e_pipeline</code>。
      </p>
      <div class="mt-4 flex flex-wrap gap-2">
        <UiButton variant="secondary" @click="router.push('/game')">创建对局</UiButton>
        <UiButton variant="secondary" @click="router.push('/decisions')">导出决策点</UiButton>
        <UiButton variant="secondary" @click="router.push('/training')">启动训练</UiButton>
      </div>
    </section>
  </div>
</template>
