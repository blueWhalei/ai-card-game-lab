<script setup lang="ts">
import AppNav from '@/components/common/AppSidebar.vue'
</script>

<template>
  <div class="min-h-screen bg-[#f5f5f7]">
    <AppNav />
    <main>
      <RouterView />
    </main>
  </div>
</template>
