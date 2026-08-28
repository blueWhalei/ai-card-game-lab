<script setup lang="ts">
import UiEmpty from '@/components/ui/Empty.vue'

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
  <UiEmpty :title="title" :description="description">
    <slot name="action" />
  </UiEmpty>
</template>
