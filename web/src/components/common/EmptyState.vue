<script setup lang="ts">
interface Props {
  title?: string
  description?: string
}

withDefaults(defineProps<Props>(), {
  title: '暂无数据',
  description: '还没有任何记录',
})
</script>

<template>
  <div class="flex flex-col items-center justify-center py-20">
    <div class="mb-4 text-5xl opacity-30">📭</div>
    <h3 class="mb-1 text-base font-semibold text-[#1d1d1f]">{{ title }}</h3>
    <p class="text-sm text-[#86868b]">{{ description }}</p>
    <div class="mt-4">
      <slot name="action" />
    </div>
  </div>
</template>
