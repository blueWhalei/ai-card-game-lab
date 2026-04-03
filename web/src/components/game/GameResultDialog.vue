<script setup lang="ts">
defineProps<{
  modelValue: boolean
  winner: {
    name?: string
    id: string
    role?: string
    totalRounds?: number
  } | null
}>()

defineEmits<{
  'update:modelValue': [value: boolean]
  back: []
}>()
</script>

<template>
  <el-dialog :model-value="modelValue" title="对局结束" width="400px" center @update:model-value="$emit('update:modelValue', $event)">
    <div v-if="winner" class="py-4 text-center">
      <div class="mb-4 text-5xl">🏆</div>
      <h3 class="mb-3 text-xl font-semibold text-[#1d1d1f]">{{ winner.name || winner.id }} 获胜！</h3>
      <span class="inline-block rounded-full px-4 py-1.5 text-sm font-medium" :class="winner.role === 'landlord' ? 'bg-red-50 text-[#ff3b30]' : 'bg-[#e8f8ee] text-[#34c759]'">
        {{ winner.role === 'landlord' ? '地主' : '农民' }}
      </span>
      <p class="mt-4 text-sm text-[#86868b]">总轮次：{{ winner.totalRounds }}</p>
    </div>
    <template #footer>
      <button class="apple-btn" @click="$emit('update:modelValue', false); $emit('back')">返回列表</button>
    </template>
  </el-dialog>
</template>
