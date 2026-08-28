<script setup lang="ts">
import UiDialog from '@/components/ui/Dialog.vue'
import UiButton from '@/components/ui/Button.vue'
import UiBadge from '@/components/ui/Badge.vue'

defineProps<{
  modelValue: boolean
  winner: {
    name?: string
    id: string
    role?: string
    totalRounds?: number
  } | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  back: []
}>()

function onBack(): void {
  emit('update:modelValue', false)
  emit('back')
}
</script>

<template>
  <UiDialog
    :open="modelValue"
    title="对局结束"
    @update:open="emit('update:modelValue', $event)"
  >
    <div v-if="winner" class="py-2 text-center">
      <h3 class="mb-3 text-xl font-semibold text-ink-text">
        {{ winner.name || winner.id }} 获胜
      </h3>
      <UiBadge :variant="winner.role === 'landlord' ? 'danger' : 'success'">
        {{ winner.role === 'landlord' ? '地主' : '农民' }}
      </UiBadge>
      <p class="mt-4 text-sm text-ink-text-muted">总轮次：{{ winner.totalRounds }}</p>
    </div>
    <template #footer>
      <UiButton @click="onBack">返回列表</UiButton>
    </template>
  </UiDialog>
</template>
