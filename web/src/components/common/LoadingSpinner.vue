<script setup lang="ts">
interface Props {
  text?: string
}

withDefaults(defineProps<Props>(), {
  text: '加载中...',
})
</script>

<template>
  <div class="flex flex-col items-center justify-center py-12">
    <el-icon class="is-loading mb-2 text-3xl text-blue-500">
      <svg viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg">
        <path
          d="M512 64a32 32 0 0 1 32 32v192a32 32 0 0 1-64 0V96a32 32 0 0 1 32-32z"
          fill="currentColor"
        />
      </svg>
    </el-icon>
    <span class="text-sm text-gray-500">{{ text }}</span>
  </div>
</template>
